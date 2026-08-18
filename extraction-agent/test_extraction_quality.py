from __future__ import annotations

from pathlib import Path

from extraction_agent import extract_report_metrics


ABB_REPORT = Path(__file__).resolve().parents[1] / "data" / "abb_2025_report.txt"
ABB_TEXT = ABB_REPORT.read_text(encoding="utf-8")


def test_company_name_is_exact_from_metadata():
    result = extract_report_metrics(ABB_TEXT, metadata={"company_name": "ABB", "report_year": "2025"})
    assert result["company_name"] == "ABB"
    assert result["report_year"] == "2025"


def test_company_name_is_exact_from_header_when_no_metadata():
    result = extract_report_metrics(ABB_TEXT)
    assert result["company_name"] == "ABB"


def test_revenue_and_operating_income_are_exact_values():
    result = extract_report_metrics(ABB_TEXT)
    assert result["revenue"] == "$15.3 billion"
    assert result["operating_income"] == "$2.1 billion"


def test_total_assets_and_liabilities_are_exact_values():
    result = extract_report_metrics(ABB_TEXT)
    assert result["total_assets"] == "$22.6 billion"
    assert result["total_liabilities"] == "$9.8 billion"


def test_missing_values_are_null_not_invented():
    result = extract_report_metrics(ABB_TEXT)
    assert result["net_income"] is None
    assert result["cash_flow"] is None
    assert result["eps"] is None


def test_surrounding_sentence_is_not_included_in_values():
    result = extract_report_metrics(ABB_TEXT)
    assert "driven by strong demand" not in result["revenue"]
    assert "and total liabilities" not in result["total_assets"]


def test_metadata_fields_remain_intact():
    metadata = {
        "analysis_id": "analysis-123",
        "document_id": "doc-456",
        "company_name": "ABB",
        "report_year": "2025",
        "chunk_id": "chunk-789",
    }
    result = extract_report_metrics(ABB_TEXT, metadata=metadata)
    assert result["analysis_id"] == "analysis-123"
    assert result["document_id"] == "doc-456"
    assert result["company_name"] == "ABB"
    assert result["report_year"] == "2025"
    assert result["chunk_id"] == "chunk-789"


def test_multiple_financial_metrics_in_same_paragraph():
    text = (
        "Revenue increased 14% to $15.3 billion. Operating income increased to $2.1 billion. "
        "Total assets were $22.6 billion and total liabilities were $9.8 billion."
    )
    result = extract_report_metrics(text)
    assert result["revenue"] == "$15.3 billion"
    assert result["operating_income"] == "$2.1 billion"
    assert result["total_assets"] == "$22.6 billion"
    assert result["total_liabilities"] == "$9.8 billion"


def test_percentage_and_currency_values_are_normalized():
    text = "Revenue increased 14% to $15.3 billion and operating income improved 8% to $2.1 billion."
    result = extract_report_metrics(text)
    assert result["revenue"] == "$15.3 billion"
    assert result["operating_income"] == "$2.1 billion"


def test_million_and_billion_units_are_preserved():
    text = "Revenue was $7.5 million and total assets reached $4.2 billion."
    result = extract_report_metrics(text)
    assert result["revenue"] == "$7.5 million"
    assert result["total_assets"] == "$4.2 billion"


def test_values_with_commas_are_preserved():
    text = "Revenue reached $1,250.5 million and total liabilities were $12,000.0 million."
    result = extract_report_metrics(text)
    assert result["revenue"] == "$1,250.5 million"
    assert result["total_liabilities"] == "$12,000.0 million"


def test_negative_fiancial_values_are_supported():
    text = "Operating loss was -$1.2 billion and net income was -$0.4 billion."
    result = extract_report_metrics(text)
    assert result["operating_income"] == "-$1.2 billion"
    assert result["net_income"] == "-$0.4 billion"


def test_decimal_values_are_preserved():
    text = "Total assets were $22.64 billion and total liabilities were $9.81 billion."
    result = extract_report_metrics(text)
    assert result["total_assets"] == "$22.64 billion"
    assert result["total_liabilities"] == "$9.81 billion"


def test_table_values_respect_fy2024_and_fy2025_headers():
    text = """
    Metric
    FY2024
    FY2025
    Change
    Revenue
    $13.8 billion
    $15.3 billion
    +$1.5 billion
    Operating Income
    $1.8 billion
    $2.1 billion
    +$0.3 billion
    Net Income
    $1.2 billion
    $1.5 billion
    +$0.3 billion
    Total Assets
    $20.4 billion
    $22.6 billion
    +$2.2 billion
    Total Liabilities
    $9.1 billion
    $9.8 billion
    +$0.7 billion
    Operating Cash Flow
    $1.6 billion
    $1.9 billion
    +$0.3 billion
    """
    result = extract_report_metrics(text, metadata={"company_name": "Nova Tech Systems Ltd.", "report_year": "2025"})

    expected_current = {
        "Revenue": "$15.3 billion",
        "Operating Income": "$2.1 billion",
        "Net Income": "$1.5 billion",
        "Total Assets": "$22.6 billion",
        "Total Liabilities": "$9.8 billion",
        "Cash Flow": "$1.9 billion",
    }

    for metric_name, current_value in expected_current.items():
        assert result["yearly_metrics"][metric_name][0]["year"] == 2024
        assert result["yearly_metrics"][metric_name][1]["year"] == 2025
        assert result["yearly_metrics"][metric_name][0]["value"] in {"$13.8 billion", "$1.8 billion", "$1.2 billion", "$20.4 billion", "$9.1 billion", "$1.6 billion"}
        assert result["yearly_metrics"][metric_name][1]["value"] == current_value

    assert result["revenue"] == "$15.3 billion"
    assert result["operating_income"] == "$2.1 billion"
    assert result["net_income"] == "$1.5 billion"
    assert result["total_assets"] == "$22.6 billion"
    assert result["total_liabilities"] == "$9.8 billion"
    assert result["cash_flow"] == "$1.9 billion"

    assert result["yearly_metrics"]["Revenue"][0]["value"] == "$13.8 billion"
    assert result["yearly_metrics"]["Revenue"][1]["value"] == "$15.3 billion"
    assert result["yearly_metrics"]["Operating Income"][0]["value"] == "$1.8 billion"
    assert result["yearly_metrics"]["Operating Income"][1]["value"] == "$2.1 billion"
    assert result["yearly_metrics"]["Net Income"][0]["value"] == "$1.2 billion"
    assert result["yearly_metrics"]["Net Income"][1]["value"] == "$1.5 billion"
    assert result["yearly_metrics"]["Total Assets"][0]["value"] == "$20.4 billion"
    assert result["yearly_metrics"]["Total Assets"][1]["value"] == "$22.6 billion"
    assert result["yearly_metrics"]["Total Liabilities"][0]["value"] == "$9.1 billion"
    assert result["yearly_metrics"]["Total Liabilities"][1]["value"] == "$9.8 billion"
    assert result["yearly_metrics"]["Cash Flow"][0]["value"] == "$1.6 billion"
    assert result["yearly_metrics"]["Cash Flow"][1]["value"] == "$1.9 billion"

    assert "Revenue 2025 = 13.8" not in str(result)
    assert "Operating Income 2025 = 1.8" not in str(result)
    assert "Net Income 2025 = 1.2" not in str(result)
    assert "Total Assets 2025 = 20.4" not in str(result)
    assert "Total Liabilities 2025 = 9.1" not in str(result)
    assert "Cash Flow 2025 = 1.6" not in str(result)


def test_growth_percentage_is_not_treated_as_the_metric_value():
    text = (
        "Revenue increased 12.5% to $18.4 billion in 2026 from $16.35 billion in 2025. "
        "Operating income was $3.0 billion in 2026 and $2.5 billion in 2025. "
        "Net income was $2.2 billion in 2026 and $1.8 billion in 2025. "
        "Operating cash flow was $2.8 billion in 2026 and $2.3 billion in 2025."
    )
    result = extract_report_metrics(text, metadata={"company_name": "Orion Digital Infrastructure Ltd.", "report_year": "2026"})

    assert result["revenue"] == "$18.4 billion"
    assert result["operating_income"] == "$3.0 billion"
    assert result["net_income"] == "$2.2 billion"
    assert result["cash_flow"] == "$2.8 billion"

    assert result["yearly_metrics"]["Revenue"][0]["value"] == "$16.35 billion"
    assert result["yearly_metrics"]["Revenue"][1]["value"] == "$18.4 billion"
    assert result["yearly_metrics"]["Operating Income"][0]["value"] == "$2.5 billion"
    assert result["yearly_metrics"]["Operating Income"][1]["value"] == "$3.0 billion"
    assert result["yearly_metrics"]["Net Income"][0]["value"] == "$1.8 billion"
    assert result["yearly_metrics"]["Net Income"][1]["value"] == "$2.2 billion"
    assert result["yearly_metrics"]["Cash Flow"][0]["value"] == "$2.3 billion"
    assert result["yearly_metrics"]["Cash Flow"][1]["value"] == "$2.8 billion"


def test_yearly_metrics_follow_actual_fy_headers_and_keep_current_year_last():
    text = (
        "Orion Digital Infrastructure Ltd. Mock Annual Financial Report — FY2026\n"
        "For the years ended December 31, 2026 and December 31, 2025\n"
        "Metric\n"
        "FY2026\n"
        "FY2025\n"
        "Revenue\n"
        "$18.4 billion\n"
        "$16.35 billion\n"
        "Operating Income\n"
        "$3.0 billion\n"
        "$2.5 billion\n"
    )

    result = extract_report_metrics(text, metadata={"company_name": "Orion Digital Infrastructure Ltd.", "report_year": "2026"})

    revenue_series = result["yearly_metrics"]["Revenue"]
    assert [item["year"] for item in revenue_series] == [2025, 2026]
    assert [item["value"] for item in revenue_series] == ["$16.35 billion", "$18.4 billion"]
    assert result["revenue"] == "$18.4 billion"
