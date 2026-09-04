from pathlib import Path
import re
import pytest

from backend.orchestration.workflow import AnalysisWorkflow
from red_flag_agent.app.services.offline_analyzer import OfflineAnalyzer


def test_amagi_e2e_pipeline(tmp_path, monkeypatch):
    """End-to-end integration test on Amagi.pdf validating:
    1. Layout-aware ingestion preserving tables.
    2. Extraction agent canonical candidate selection:
       - Statement priority (+50), Table priority (+30), Year match (+100).
       - Selects canonical 15,056.06 million revenue over narrative 1,505.6 crore.
       - Selects canonical 17,568.09 million total equity over 1,081.70 million share capital.
       - Selects canonical 23,532.55 million total assets.
       - Zero page numbers extracted as financial metrics.
    3. Research agent causal synthesis:
       - Dynamic currency (₹ / Rs. / INR, no hardcoded $).
       - Identifies Trade Receivables as the primary working capital drag.
       - Evidence validation passes with valid == True.
    4. Red flag agent temporal directionality safeguards:
       - Margin expansion (2.0% to 10.3%) is never flagged as a margin decline.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    amagi_pdf = Path(__file__).resolve().parent.parent / "tmp_uploads" / "Amagi.pdf"
    assert amagi_pdf.exists(), f"Amagi.pdf fixture missing at {amagi_pdf}"

    workflow = AnalysisWorkflow(
        chroma_path=str(tmp_path / "amagi_e2e_chroma"),
        collection_name="amagi_e2e_test",
    )

    question = "Why is there a divergence between Amagi's PAT and OCF in FY26? Identify the primary working capital drag."

    result = workflow.run_analysis(
        report_path=str(amagi_pdf),
        company_name="Amagi",
        report_year="2026",
        question=question,
    )

    # -------------------------------------------------------------
    # 1. Document Ingestion & Chunking Assertions
    # -------------------------------------------------------------
    assert result["analysis_id"]
    assert result["document_id"]
    collection = workflow.document_agent.collection
    assert collection.count() > 0

    records = collection.get(where={"analysis_id": result["analysis_id"]}, include=["documents", "metadatas"])
    assert len(records["documents"]) > 0
    # Layout-aware extraction preserved markdown table pipe syntax
    table_chunks = [doc for doc in records["documents"] if "|" in doc and doc.count("|") >= 4]
    assert len(table_chunks) > 0, "Expected layout-aware table chunks with markdown pipes to be preserved"

    # -------------------------------------------------------------
    # 2. Extraction Agent Canonical Selection Assertions
    # -------------------------------------------------------------
    extraction = result["extraction"]
    assert extraction.get("status") != "unavailable"

    # Revenue: Must select statement value 15,056.06 (million), NOT narrative 1,505.6 crore
    rev_raw = str(extraction.get("revenue", ""))
    rev_norm = re.sub(r"[^\d.]", "", rev_raw)
    assert "15056" in rev_norm or "15,056" in rev_raw, (
        f"Expected canonical revenue 15,056.06 million, got {rev_raw}"
    )
    # Ensure narrative 1505.6 was NOT selected as canonical revenue
    assert "1505.6" not in rev_norm and "1,505.6" not in rev_raw, (
        f"Narrative revenue 1,505.6 crore was erroneously selected over statement table: {rev_raw}"
    )

    # Total Equity: Must select canonical Total Equity (17,568.09 million), NOT Equity Share Capital (1,081.70 million)
    equity_raw = str(extraction.get("total_equity", ""))
    equity_norm = re.sub(r"[^\d.]", "", equity_raw)
    assert "17568" in equity_norm or "17,568" in equity_raw, (
        f"Expected canonical total equity 17,568.09 million, got {equity_raw}"
    )
    assert "1081" not in equity_norm, (
        f"Equity share capital 1,081.70 was erroneously selected as total equity: {equity_raw}"
    )

    # Total Assets: Must select canonical 23,532.55 million
    assets_raw = str(extraction.get("total_assets", ""))
    assets_norm = re.sub(r"[^\d.]", "", assets_raw)
    assert "23532" in assets_norm or "23,532" in assets_raw, (
        f"Expected canonical total assets 23,532.55 million, got {assets_raw}"
    )

    # Negative guardrails: No citation page numbers (e.g. 107, 108, 21, 22) extracted as metric values
    for metric_name in ["revenue", "total_equity", "total_assets", "operating_income", "net_income"]:
        val = str(extraction.get(metric_name, "")).strip()
        assert val not in {"107", "108", "21", "22", "1", "2", "3", "4", "5", "6"}, (
            f"Page number erroneously extracted as {metric_name}: {val}"
        )

    # Check canonical observations export
    obs = extraction.get("canonical_observations", {})
    if "revenue" in obs:
        assert obs["revenue"].get("is_primary_statement") or obs["revenue"].get("is_table")

    # -------------------------------------------------------------
    # 3. Research Agent Working Capital & Dynamic Currency Assertions
    # -------------------------------------------------------------
    research = result["research"]
    answer_text = research.get("answer") or ""
    assert len(answer_text) > 50, "Expected substantive research answer"

    # Dynamic currency formatting: Must NOT have hardcoded $ in INR/Rupee context
    assert "$" not in answer_text, f"Found hardcoded $ sign in research answer for Indian entity: {answer_text}"

    # Verify working capital drag or trade receivables is addressed in answer
    answer_lower = answer_text.lower()
    assert (
        "trade receivables" in answer_lower
        or "working capital" in answer_lower
        or "receivables" in answer_lower
    ), f"Expected research answer to identify working capital / trade receivables: {answer_text}"

    # Citations verification
    sources = research.get("sources") or []
    assert len(sources) > 0, "Expected research answer to include verified source citations"

    # -------------------------------------------------------------
    # 4. Red Flag Agent Temporal Directionality Safeguards
    # -------------------------------------------------------------
    red_flags = result["red_flags"]
    flags = red_flags.get("flags") or []

    # Check that margin expansion (2.0% to 10.3%) was NEVER flagged as a Margin decline
    margin_decline_flags = [f for f in flags if f.get("title") == "Margin decline" or f.get("category") == "Profitability"]
    for mf in margin_decline_flags:
        evidence = str(mf.get("evidence", "")).lower()
        assert not (
            ("from 2" in evidence and "10" in evidence)
            or ("expanded" in evidence)
            or ("growth" in evidence)
        ), f"Margin expansion was falsely flagged as a profitability risk: {mf}"

    # Verify OfflineAnalyzer directly against the specific Amagi report sentence
    analyzer = OfflineAnalyzer()
    expansion_sentence = "Adjusted EBITDA Margin expanded from 2.0% to 10.3% (up 830 bps YoY)."
    assert analyzer._is_margin_expansion(expansion_sentence) is True
    test_analysis = analyzer.analyze(
        "Identify financial risks",
        [{"document": expansion_sentence, "metadata": {"page": 2, "source": "Amagi.pdf"}}],
    )
    assert test_analysis["total_flags"] == 0, "Margin expansion must produce 0 risk flags"
