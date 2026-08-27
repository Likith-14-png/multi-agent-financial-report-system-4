from extraction_agent import (
    _find_observation_conflicts,
    _provenance_score,
    extract_report_metrics,
    select_canonical_observation,
)
import pytest


def _observation(value, year=2026, context="income_statement_audited", section="Income Statement", page=1, metric="revenue"):
    return {
        "metric_name": metric,
        "raw_value": f"₹{value} million",
        "numeric_value": value,
        "currency": "INR",
        "unit": "million",
        "report_year": year,
        "statement_context": context,
        "source_section": section,
        "source_page": page,
        "source_chunk_id": f"chunk-{page}",
        "canonical_label": "Revenue",
    }


def test_primary_statement_beats_accounting_notes_and_keeps_supporting_observation():
    statement = _observation(187472, section="Consolidated Income Statement", page=1)
    notes = _observation(187472, context="disclosure", section="Accounting Notes", page=9)
    selected = select_canonical_observation([notes, statement], "revenue", target_year=2026)

    assert selected["source_page"] == 1
    assert selected["numeric_value"] == 187472
    assert len([notes, statement]) == 2
    assert _provenance_score(statement, 2026) > _provenance_score(notes, 2026)


def test_exact_requested_year_beats_better_source_from_another_year():
    old_statement = _observation(176320, year=2025, page=1)
    target_notes = _observation(187472, year=2026, context="disclosure", section="Accounting Notes", page=9)

    selected = select_canonical_observation([old_statement, target_notes], "revenue", target_year=2026)

    assert selected["report_year"] == 2026
    assert selected["numeric_value"] == 187472


def test_different_years_do_not_create_a_conflict():
    observations = [_observation(176320, year=2025), _observation(187472, year=2026)]

    assert _find_observation_conflicts(observations) == {}


def test_genuine_same_year_value_conflict_remains_visible():
    observations = [_observation(187472), _observation(190000, context="disclosure", section="Accounting Notes", page=9)]

    conflicts = _find_observation_conflicts(observations)

    assert len(conflicts["revenue"]) == 2
    assert {item["numeric_value"] for item in conflicts["revenue"]} == {187472, 190000}


def test_segment_observation_remains_separate_from_consolidated_revenue():
    consolidated = _observation(187472, section="Consolidated Income Statement")
    segment = _observation(45000, context="segment_metrics", section="Digital Services", metric="software_revenue")

    assert select_canonical_observation([consolidated], "revenue", target_year=2026) is consolidated
    assert select_canonical_observation([segment], "software_revenue", target_year=2026) is segment
    assert _find_observation_conflicts([consolidated, segment]) == {}


def test_reference_values_are_ignored_by_extraction():
    text = """
    Expected Cross-Document Checks:
    Revenue: ₹999,999 million

    Income Statement:
    Revenue: ₹187,472 million
    """
    result = extract_report_metrics(text, metadata={"company_name": "Test Co", "report_year": 2026})

    assert result["revenue"] == "₹187,472 million"
    assert result["traceability"]["revenue"]["value"] == "₹187,472 million"


def test_balance_sheet_statement_beats_notes():
    statement = _observation(185000, section="Balance Sheet", page=2, metric="total_assets")
    notes = _observation(185000, context="disclosure", section="Accounting Notes", page=10, metric="total_assets")

    assert select_canonical_observation([notes, statement], "total_assets", target_year=2026)["source_page"] == 2


def test_cash_flow_statement_beats_notes():
    statement = _observation(14200, section="Cash Flow Statement", page=3, metric="operating_cash_flow")
    notes = _observation(14200, context="disclosure", section="Notes", page=11, metric="operating_cash_flow")

    assert select_canonical_observation([notes, statement], "operating_cash_flow", target_year=2026)["source_page"] == 3


@pytest.mark.parametrize(
    ("metric", "primary_section", "supporting_section"),
    [
        ("revenue", "Consolidated Income Statement", "Accounting Notes"),
        ("operating_income", "Consolidated Income Statement", "Management Summary"),
        ("net_income", "Consolidated Income Statement", "Verification Checklist"),
        ("total_assets", "Consolidated Balance Sheet", "Accounting Notes"),
        ("total_liabilities", "Consolidated Balance Sheet", "Risk Indicators"),
        ("total_equity", "Consolidated Balance Sheet", "Narrative Summary"),
        ("operating_cash_flow", "Consolidated Cash Flow Statement", "Management Summary"),
    ],
)
def test_primary_statement_wins_duplicate_value_for_core_metric(metric, primary_section, supporting_section):
    statement = _observation(187472, section=primary_section, page=2, metric=metric)
    supporting = _observation(187472, context="disclosure", section=supporting_section, page=9, metric=metric)

    selected = select_canonical_observation([supporting, statement], metric, target_year=2026)

    assert selected is statement
    assert selected["raw_value"] == "₹187472 million"
    assert selected["source_page"] == 2
    assert selected["source_chunk_id"] == "chunk-2"


def test_nested_chunk_metadata_keeps_selected_occurrence_provenance_synchronized():
    text = "Consolidated Income Statement\nRevenue: ₹187,472 million\nAccounting Notes and Risk Indicators\nRevenue: ₹187,472 million"
    chunks = [
        {
            "chunk_id": "primary-chunk",
            "page_start": 2,
            "page_end": 3,
            "text": "Consolidated Income Statement\nRevenue: ₹187,472 million",
            "metadata": {
                "source_file": "primary.pdf",
                "section_title": "Consolidated Income Statement",
                "page_start": 2,
                "page_end": 3,
                "chunk_id": "primary-chunk",
            },
        },
        {
            "chunk_id": "notes-chunk",
            "page_start": 9,
            "page_end": 10,
            "text": "Accounting Notes and Risk Indicators\nRevenue: ₹187,472 million",
            "metadata": {
                "source_file": "notes.pdf",
                "section_title": "Accounting Notes and Risk Indicators",
                "page_start": 9,
                "page_end": 10,
                "chunk_id": "notes-chunk",
            },
        },
    ]

    result = extract_report_metrics(
        text,
        metadata={"company_name": "Example Co", "report_year": "2026"},
        chunk_records=chunks,
        enable_llm=False,
    )
    revenue = result["financial_values"]["revenue"]

    assert revenue["display_value"] == "₹187,472 million"
    assert revenue["source_chunk"] == "primary-chunk"
    assert revenue["source_file"] == "primary.pdf"
    assert revenue["source_page"] == 2
    assert revenue["source_page_end"] == 3
    assert revenue["section"] == "Consolidated Income Statement"
    assert revenue["evidence"]
    assert "187,472" in revenue["evidence"]


@pytest.mark.parametrize(
    ("value", "primary_page", "primary_chunk", "notes_page", "notes_chunk"),
    [
        (187472, 2, "statement-a", 14, "notes-z"),
        (92310, 8, "statement-k", 3, "notes-b"),
    ],
)
def test_duplicate_revenue_occurrences_rank_primary_statement_independent_of_value_and_location(
    value, primary_page, primary_chunk, notes_page, notes_chunk,
):
    raw_value = f"₹{value:,} million"
    text = f"Consolidated Income Statement\nRevenue: {raw_value}\nAccounting Notes\nRevenue: {raw_value}"
    chunks = [
        {
            "chunk_id": primary_chunk,
            "page_start": primary_page,
            "text": f"Consolidated Income Statement\nRevenue: {raw_value}",
            "metadata": {
                "source_file": "primary-statement.txt",
                "section_title": "Consolidated Income Statement",
            },
        },
        {
            "chunk_id": notes_chunk,
            "page_start": notes_page,
            "text": f"Accounting Notes\nRevenue: {raw_value}",
            "metadata": {
                "source_file": "accounting-notes.txt",
                "section_title": "Accounting Notes",
            },
        },
    ]

    result = extract_report_metrics(
        text,
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        chunk_records=chunks,
        enable_llm=False,
    )
    revenue = result["financial_values"]["revenue"]
    selected = result["traceability"]["revenue"]

    assert result["revenue"] == raw_value
    assert revenue["display_value"] == raw_value
    assert revenue["source_chunk"] == primary_chunk
    assert revenue["source_file"] == "primary-statement.txt"
    assert revenue["source_page"] == primary_page
    assert revenue["section"] == "Consolidated Income Statement"
    assert revenue["currency"] == "INR"
    assert revenue["unit_scale"] == "million"
    assert revenue["period"] == 2026
    assert selected["value"] == raw_value
    assert selected["source_chunk_id"] == primary_chunk
    assert selected["source_file"] == "primary-statement.txt"
    assert selected["page_number"] == primary_page
    assert selected["currency"] == "INR"
    assert selected["unit"] == "million"
    assert selected["year"] == 2026


def test_separated_primary_revenue_table_occurrence_beats_single_line_notes_occurrence():
    value = "₹731,904 million"
    primary_chunk = {
        "chunk_id": "statement-table-42",
        "page_start": 17,
        "page_end": 18,
        "text": f"Consolidated Income Statement\nRevenue\n{value}\nGross profit\n₹100 million",
        "metadata": {
            "source_file": "synthetic-primary-report.pdf",
            "section_title": "Working Capital",
        },
    }
    notes_chunk = {
        "chunk_id": "notes-table-88",
        "page_start": 29,
        "page_end": 30,
        "text": f"Accounting Notes and Risk Indicators\nFY2027 Revenue = {value}",
        "metadata": {
            "source_file": "synthetic-notes-report.pdf",
            "section_title": "Accounting Notes and Risk Indicators",
        },
    }

    result = extract_report_metrics(
        f"{primary_chunk['text']}\n{notes_chunk['text']}",
        metadata={"company_name": "Synthetic Co", "report_year": 2027},
        chunk_records=[primary_chunk, notes_chunk],
        enable_llm=False,
    )
    revenue = result["financial_values"]["revenue"]

    assert result["revenue"] == value
    assert revenue["source_chunk"] == "statement-table-42"
    assert revenue["source_file"] == "synthetic-primary-report.pdf"
    assert revenue["source_page"] == 17
    assert revenue["section"] == "Consolidated Income Statement"
    assert revenue["evidence"] == f"Revenue {value}"


def test_mixed_statement_chunk_uses_metric_occurrence_section():
    text = """Consolidated Income Statement
Revenue: ₹187,472 million
Gross Profit: ₹44,612 million
Balance Sheet
Total Assets: ₹185,000 million
Total Liabilities: ₹107,000 million
Total Equity: ₹78,000 million
Total Debt: ₹60,000 million
Cash Flow Statement
Operating Cash Flow: ₹14,200 million
Free Cash Flow: ₹8,900 million"""
    result = extract_report_metrics(
        text,
        metadata={"company_name": "Example Co", "report_year": "2026"},
        chunk_records=[{"chunk_id": "mixed", "page_start": 1, "page_end": 3, "text": text, "metadata": {"source_file": "report.pdf"}}],
        enable_llm=False,
    )

    assert result["financial_values"]["revenue"]["section"] == "Consolidated Income Statement"
    assert result["financial_values"]["total_assets"]["section"] == "Balance Sheet"
    assert result["financial_values"]["total_liabilities"]["section"] == "Balance Sheet"
    assert result["financial_values"]["total_equity"]["section"] == "Balance Sheet"
    assert result["financial_values"]["operating_cash_flow"]["section"] == "Cash Flow Statement"
    assert result["financial_values"]["free_cash_flow"]["section"] == "Cash Flow Statement"
    assert result["financial_values"]["total_debt"]["section"] == "Balance Sheet"


def test_operating_cash_flow_does_not_fabricate_generic_cash_flow_provenance():
    result = extract_report_metrics(
        "Cash Flow Statement\nOperating Cash Flow: ₹14,200 million",
        metadata={"company_name": "Example Co", "report_year": "2026"},
        chunk_records=[{"chunk_id": "cash-flow", "page_start": 4, "text": "Cash Flow Statement\nOperating Cash Flow: ₹14,200 million", "metadata": {"source_file": "report.pdf"}}],
        enable_llm=False,
    )

    assert result["cash_flow"] is None
    assert result["financial_values"]["cash_flow"]["display_value"] is None
    assert result["financial_values"]["operating_cash_flow"]["section"] == "Cash Flow Statement"


@pytest.mark.parametrize(
    ("value", "cash_page", "cash_chunk", "mixed_page", "mixed_chunk"),
    [
        (14200, 41, "cash-flow-a", 7, "balance-sheet-z"),
        (87654, 6, "cash-flow-k", 53, "balance-sheet-b"),
    ],
)
def test_operating_cash_flow_uses_local_cash_flow_occurrence_over_mixed_chunk_metadata(
    value, cash_page, cash_chunk, mixed_page, mixed_chunk,
):
    raw_value = f"₹{value:,} million"
    cash_flow_chunk = {
        "chunk_id": cash_chunk,
        "page_start": cash_page,
        "page_end": cash_page,
        "section_title": "Consolidated Balance Sheet",
        "text": f"Consolidated Cash Flow\nOperating Cash Flow\n{raw_value}",
        "metadata": {
            "source_file": "cash-flow-source.pdf",
            "section_title": "Consolidated Balance Sheet",
        },
    }
    mixed_chunk_record = {
        "chunk_id": mixed_chunk,
        "page_start": mixed_page,
        "page_end": mixed_page,
        "section_title": "Consolidated Balance Sheet",
        "text": f"Consolidated Balance Sheet\nOperating Cash Flow\n{raw_value}",
        "metadata": {
            "source_file": "mixed-source.pdf",
            "section_title": "Consolidated Balance Sheet",
        },
    }

    result = extract_report_metrics(
        f"{cash_flow_chunk['text']}\n{mixed_chunk_record['text']}",
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        chunk_records=[cash_flow_chunk, mixed_chunk_record],
        enable_llm=False,
    )
    operating_cash_flow = result["financial_values"]["operating_cash_flow"]

    assert result["operating_cash_flow"] == raw_value
    assert operating_cash_flow["display_value"] == raw_value
    assert operating_cash_flow["source_chunk"] == cash_chunk
    assert operating_cash_flow["source_file"] == "cash-flow-source.pdf"
    assert operating_cash_flow["source_page"] == cash_page
    assert operating_cash_flow["section"] == "Consolidated Cash Flow"
    assert operating_cash_flow["evidence"] == f"Operating Cash Flow {raw_value}"
    assert operating_cash_flow["currency"] == "INR"
    assert operating_cash_flow["unit_scale"] == "million"
    assert operating_cash_flow["period"] == 2026


@pytest.mark.parametrize(
    ("value", "cash_page", "cash_chunk", "other_page", "other_chunk"),
    [
        (8900, 23, "fcf-cash-a", 4, "fcf-other-z"),
        (64231, 5, "fcf-cash-k", 31, "fcf-other-b"),
    ],
)
def test_free_cash_flow_uses_matching_cash_flow_evidence_and_provenance(
    value, cash_page, cash_chunk, other_page, other_chunk,
):
    raw_value = f"₹{value:,} million"
    cash_flow_chunk = {
        "chunk_id": cash_chunk,
        "page_start": cash_page,
        "page_end": cash_page,
        "section_title": "Consolidated Balance Sheet",
        "text": f"Consolidated Cash Flow\nFree Cash Flow\n{raw_value}",
        "metadata": {
            "source_file": "fcf-cash-flow.pdf",
            "section_title": "Consolidated Balance Sheet",
        },
    }
    other_chunk = {
        "chunk_id": other_chunk,
        "page_start": other_page,
        "page_end": other_page,
        "section_title": "Consolidated Balance Sheet",
        "text": f"Consolidated Balance Sheet\nFree Cash Flow\n{raw_value}",
        "metadata": {
            "source_file": "fcf-other-section.pdf",
            "section_title": "Consolidated Balance Sheet",
        },
    }

    result = extract_report_metrics(
        f"{cash_flow_chunk['text']}\n{other_chunk['text']}",
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        chunk_records=[cash_flow_chunk, other_chunk],
        enable_llm=False,
    )
    free_cash_flow = result["financial_values"]["free_cash_flow"]

    assert result["free_cash_flow"] == raw_value
    assert free_cash_flow["display_value"] == raw_value
    assert free_cash_flow["evidence"] == f"Free Cash Flow {raw_value}"
    assert free_cash_flow["source_chunk"] == cash_chunk
    assert free_cash_flow["source_file"] == "fcf-cash-flow.pdf"
    assert free_cash_flow["source_page"] == cash_page
    assert free_cash_flow["section"] == "Consolidated Cash Flow"
    assert free_cash_flow["currency"] == "INR"
    assert free_cash_flow["unit_scale"] == "million"
    assert free_cash_flow["period"] == 2026


def test_operating_cash_flow_does_not_create_generic_cash_flow():
    result = extract_report_metrics(
        "Consolidated Cash Flow\nOperating Cash Flow: $41 million",
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        enable_llm=False,
    )

    assert result["operating_cash_flow"] == "$41 million"
    assert result["cash_flow"] is None
    assert result["financial_values"]["cash_flow"]["display_value"] is None
    assert result["financial_values"]["cash_flow"]["evidence"] is None
    assert result["financial_values"]["cash_flow"]["provenance"]["chunk_id"] is None


def test_explicit_generic_cash_flow_keeps_independent_provenance():
    value = "$73 million"
    chunk = {
        "chunk_id": "generic-cash-flow-17",
        "page_start": 12,
        "page_end": 12,
        "section_title": "Liquidity Summary",
        "text": f"Liquidity Summary\nCash Flow: {value}",
        "metadata": {
            "source_file": "generic-cash-flow-report.pdf",
            "section_title": "Liquidity Summary",
        },
    }

    result = extract_report_metrics(
        chunk["text"],
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        chunk_records=[chunk],
        enable_llm=False,
    )
    cash_flow = result["financial_values"]["cash_flow"]

    assert result["cash_flow"] == value
    assert cash_flow["display_value"] == value
    assert cash_flow["evidence"] == f"Cash Flow: {value}"
    assert cash_flow["source_page"] == 12
    assert cash_flow["source_chunk"] == "generic-cash-flow-17"
    assert cash_flow["source_file"] == "generic-cash-flow-report.pdf"
    assert cash_flow["section"] == "Liquidity Summary"
    assert cash_flow["currency"] == "USD"
    assert cash_flow["unit_scale"] == "million"
    assert cash_flow["period"] == 2026


def test_generic_metric_pages_follow_their_embedded_occurrence_page():
    text = """Page 2
Consolidated Income Statement
Gross Profit: $41 million
Operating Income: $12 million
Page 3
Consolidated Balance Sheet
Total Assets: $91 million
Total Liabilities: $57 million
Total Equity: $34 million
Page 7
Debt and Liquidity
Total Debt: $22 million"""
    chunk = {
        "chunk_id": "mixed-pages-42",
        "page_start": 1,
        "page_end": 7,
        "section_title": "Consolidated Balance Sheet",
        "text": text,
        "metadata": {"source_file": "mixed-pages-report.pdf"},
    }

    result = extract_report_metrics(
        text,
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        chunk_records=[chunk],
        enable_llm=False,
    )

    assert result["financial_values"]["gross_profit"]["source_page"] == 2
    assert result["financial_values"]["operating_income"]["source_page"] == 2
    assert result["financial_values"]["total_assets"]["source_page"] == 3
    assert result["financial_values"]["total_liabilities"]["source_page"] == 3
    assert result["financial_values"]["total_equity"]["source_page"] == 3
    assert result["financial_values"]["total_debt"]["source_page"] == 7
    assert result["financial_values"]["total_assets"]["evidence"]


def test_generic_metric_page_falls_back_to_chunk_page_without_embedded_marker():
    chunk = {
        "chunk_id": "no-page-marker-9",
        "page_start": 11,
        "page_end": 11,
        "section_title": "Consolidated Balance Sheet",
        "text": "Total Assets: $73 million",
        "metadata": {"source_file": "no-page-marker-report.pdf"},
    }

    result = extract_report_metrics(
        chunk["text"],
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        chunk_records=[chunk],
        enable_llm=False,
    )

    assert result["financial_values"]["total_assets"]["source_page"] == 11


def test_total_debt_uses_local_debt_liquidity_section_over_aggregate_metadata():
    value = "$418 million"
    text = f"""Page 2
Consolidated Balance Sheet
Total Assets: $900 million
Page 8
Debt, Liquidity and Capital Structure
Gross Debt: {value}"""
    chunk = {
        "chunk_id": "debt-local-73",
        "page_start": 1,
        "page_end": 8,
        "section_title": "Consolidated Balance Sheet",
        "text": text,
        "metadata": {
            "source_file": "debt-local-report.pdf",
            "section_title": "Consolidated Balance Sheet",
        },
    }

    result = extract_report_metrics(
        text,
        metadata={"company_name": "Synthetic Co", "report_year": 2026},
        chunk_records=[chunk],
        enable_llm=False,
    )
    debt = result["financial_values"]["total_debt"]

    assert debt["display_value"] == value
    assert debt["source_page"] == 8
    assert debt["source_chunk"] == "debt-local-73"
    assert debt["source_file"] == "debt-local-report.pdf"
    assert debt["section"] == "Debt, Liquidity and Capital Structure"
    assert debt["evidence"] == f"Gross Debt: {value}"