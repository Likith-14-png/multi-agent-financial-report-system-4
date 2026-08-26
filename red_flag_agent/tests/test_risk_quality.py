from app.models.response import RedFlagAnalysisResponse
from app.utils.constants import RISK_CATEGORIES
from app.services.offline_analyzer import OfflineAnalyzer


def _chunk(text, metadata=None):
    return [{"document": text, "metadata": metadata or {}}]


def test_genuine_risk_generates_meaningful_flag():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Operating cash flow declined to $1.1 billion from $1.8 billion, creating liquidity pressure.", {
            "page_number": "14", "chunk_id": "risk-chunk", "source_file": "annual-report.pdf",
        }),
    )

    assert result["total_flags"] >= 1
    flag = next(item for item in result["flags"] if item["category"] == "Cash Flow")
    assert "$1.1 billion" in flag["evidence"]
    assert flag["page"] == 14
    assert flag["source_file"] == "annual-report.pdf"
    assert flag["source_chunk"] == "risk-chunk"


def test_normal_disclosures_and_keyword_only_phrases_are_rejected():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Accounting policies are described in the report. Foreign currency transactions are translated. Currency risk."),
    )

    assert result["flags"] == []


def test_rule_title_is_never_used_as_evidence():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Debt increase. Currency risk. Accounting risk."),
    )

    assert result["flags"] == []


def test_quantitative_evidence_is_preferred_over_generic_risk_language():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        [{
            "document": "Debt increase. Borrowings - non-current increased from $10 million in FY2024 to $15 million in FY2025.",
            "metadata": {"page": 12, "source_file": "report.pdf", "chunk_id": "debt-12"},
        }],
    )

    flag = next(item for item in result["flags"] if item["title"] == "Debt increase")
    assert "$10 million" in flag["evidence"]
    assert "FY2025" in flag["evidence"]
    assert flag["page"] == 12
    assert flag["source_chunk"] == "debt-12"


def test_explicit_risk_disclosure_is_preserved_as_evidence():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Currency risk. The source identifies interest rates, foreign currency exchange rates and other market changes as drivers of market risk.", {
            "page": 10, "source_file": "report.pdf", "chunk_id": "market-10",
        }),
    )

    flag = next(item for item in result["flags"] if item["title"] == "Currency or FX risk")
    assert flag["evidence"].startswith("The source identifies interest rates")
    assert flag["evidence"] != "Currency risk"
    assert flag["page"] == 10
    assert flag["source_chunk"] == "market-10"


def test_currency_and_interest_rate_risks_use_market_category():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk(
            "Foreign currency exchange rates create volatility risk. Interest rates are rising, creating borrowing pressure.",
            {"page": 10},
        ),
    )

    assert {flag["title"]: flag["category"] for flag in result["flags"]} == {
        "Currency or FX risk": "Market",
        "Interest-rate risk": "Market",
    }
    assert "Market" in RISK_CATEGORIES


def test_existing_debt_profitability_categories_and_schema_remain_valid():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Total debt increased to $42 billion. Operating margin fell to 13% from 18%."),
    )

    categories_by_title = {flag["title"]: flag["category"] for flag in result["flags"]}
    assert categories_by_title["Debt increase"] == "Debt"
    assert categories_by_title["Margin decline"] == "Profitability"
    response = RedFlagAnalysisResponse.model_validate(result)
    assert response.flags


def test_stronger_evidence_has_higher_confidence_and_severity():
    analyzer = OfflineAnalyzer()
    weak = analyzer.analyze("What are the risks?", _chunk("The company reported higher debt this year."))["flags"]
    strong = analyzer.analyze("What are the risks?", _chunk("The company disclosed a material debt increase to $42 billion, creating refinancing pressure."))["flags"]

    assert weak and strong
    assert strong[0]["confidence"] > weak[0]["confidence"]
    assert 0 <= weak[0]["confidence"] <= 1
    assert 0 <= strong[0]["confidence"] <= 1
    assert strong[0]["severity"] in {"High", "Critical"}


def test_duplicate_evidence_is_consolidated_by_risk_and_context():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Debt increased materially. Borrowings rose to $42 billion. Leverage is higher.", {"section_title": "Liquidity", "page": 4}),
    )

    debt_flags = [flag for flag in result["flags"] if flag["category"] == "Debt"]
    assert len(debt_flags) == 1
    assert "$42 billion" in debt_flags[0]["evidence"]


def test_independent_risks_remain_separate():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Operating margin declined to 12% from 18%. A major customer concentration creates revenue dependence."),
    )

    assert {flag["category"] for flag in result["flags"]} >= {"Profitability", "Revenue"}


def test_explicit_negations_do_not_create_flags():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("The company reported no material weakness, no significant litigation, no liquidity pressure, and no debt increase."),
    )

    assert result["flags"] == []


def test_nested_source_provenance_is_preserved():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Operating margin fell to 10% from 15%.", {
            "provenance": {"source_file": "filing.pdf", "chunk_id": "nested-chunk", "source_page": "22"},
        }),
    )

    flag = result["flags"][0]
    assert flag["page"] == 22
    assert flag["source_file"] == "filing.pdf"
    assert flag["source_chunk"] == "nested-chunk"


def test_api_response_shape_and_numeric_evidence_remain_valid():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        _chunk("Operating cash flow declined to -€2.4 million from €1.2 million."),
    )

    response = RedFlagAnalysisResponse.model_validate(result)
    assert response.flags[0].evidence.find("-€2.4 million") >= 0
    assert response.flags[0].source_file is None
    assert response.flags[0].source_chunk is None
    assert set(response.flags[0].model_dump()) >= {
        "category", "severity", "title", "description", "reason", "evidence",
        "page", "recommendation", "confidence",
    }