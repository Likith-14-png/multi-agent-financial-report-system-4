from __future__ import annotations

from pathlib import Path

import pytest

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


def test_company_name_rejects_financial_unit_fragment():
    result = extract_report_metrics(
        "I million\nExample Holdings Ltd.\nRevenue was $10 million.",
        enable_llm=False,
    )
    assert result["company_name"] == "Example Holdings Ltd"


def test_metric_observations_keep_context_specific_values_separate():
    text = (
        "Statement of Operations\n"
        "Consolidated Revenue: $100 million\n"
        "Segment Revenue: $40 million\n"
        "Operating Income: -$5 million\n"
        "Interest Expense: $2 million\n"
        "Balance Sheet\n"
        "Total Assets: $500 million\n"
        "Cash: $80 million\n"
        "Total Liabilities: $300 million\n"
        "Debt: $200 million\n"
        "Cash Flow Statement\n"
        "Operating Cash Flow: -$10 million\n"
        "Free Cash Flow: $6 million"
    )
    result = extract_report_metrics(text, metadata={"company_name": "Example Corp", "report_year": "2025"}, enable_llm=False)
    observations = result["observations"]

    assert result["revenue"] == "$100 million"
    assert result["operating_cash_flow"] == "-$10 million"
    assert any(item["metric_name"] == "segment_revenue" and item["raw_value"] == "$40 million" for item in observations)
    assert not any(item["metric_name"] == "revenue" and item["raw_value"] == "$40 million" for item in observations)
    assert not any(item["metric_name"] == "operating_cash_flow" and item["raw_value"] == "$6 million" for item in observations)
    assert not any(item["metric_name"] == "total_assets" and item["raw_value"] == "$80 million" for item in observations)


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


def test_source_currency_and_units_are_preserved_without_usd_guessing():
    result = extract_report_metrics(
        "Revenue was ₹267,021 crore. Earnings per share (EPS): ₹145.99. Cash was ₹85 lakh.",
        metadata={"company_name": "TATA CONSULTANCY SERVICES", "report_year": "2026"},
        enable_llm=False,
    )
    assert result["revenue"] == "₹267,021 crore"
    assert result["eps"] == "₹145.99"
    assert result["financial_values"]["revenue"]["currency"] == "INR"
    assert result["financial_values"]["revenue"]["unit_scale"] == "crore"
    assert result["financial_values"]["eps"]["metric_type"] == "per_share"
    assert result["financial_values"]["eps"]["currency"] == "INR"


def test_nil_and_missing_debt_have_distinct_statuses():
    nil_result = extract_report_metrics("Total Debt: NIL.", metadata={"report_year": "2024"}, enable_llm=False)
    missing_result = extract_report_metrics("Revenue was $10 million.", metadata={"report_year": "2024"}, enable_llm=False)
    assert nil_result["financial_values"]["total_debt"]["value"] == 0.0
    assert nil_result["financial_values"]["total_debt"]["status"] == "reported_zero"
    assert missing_result["financial_values"]["total_debt"]["value"] is None
    assert missing_result["financial_values"]["total_debt"]["status"] == "available" or missing_result["financial_values"]["total_debt"]["status"] == "not_found"


def test_generic_cash_flow_is_not_operating_cash_flow():
    result = extract_report_metrics("Cash flow was discussed without an operating classification.", metadata={"report_year": "2024"}, enable_llm=False)
    assert result["operating_cash_flow"] is None


def test_yearly_value_does_not_substitute_requested_year():
    result = extract_report_metrics(
        "Revenue for FY2025 was $410 million.",
        metadata={"company_name": "Apex Materials Ltd", "report_year": "2026"},
        enable_llm=False,
    )
    assert result["revenue"] is None


def test_metric_traceability_requires_value_and_preserves_chunk_evidence():
    chunks = [{
        "chunk_id": "chunk-revenue",
        "page_start": 2,
        "text": "Revenue for FY2024 was $520 million.",
        "metadata": {"source_file": "helios_energy.pdf"},
    }]
    result = extract_report_metrics(
        chunks[0]["text"],
        metadata={"company_name": "Helios Energy", "report_year": "2024", "source_file": "helios_energy.pdf"},
        chunk_records=chunks,
        enable_llm=False,
    )
    revenue = result["financial_values"]["revenue"]
    assert revenue["source_file"] == "helios_energy.pdf"
    assert revenue["source_page"] == 2
    assert revenue["source_chunk"] == "chunk-revenue"
    assert "Revenue" in revenue["evidence"] and "$520 million" in revenue["evidence"]


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


def test_indian_annual_report_preserves_context_and_selects_statement_values():
    text = """
    Wipro Enterprises Private Limited | Fiscal year ended 31 March 2025
    All amounts are in ₹ million.
    Sales & Other Income (Consolidated)
    187,472
    171,592
    Profit Before Tax
    21,336
    24,708
    Profit for the year
    15,925
    19,031
    Basic and diluted EPS
    32.98
    39.41
    Revenue from operations
    179,633
    162,980
    Net cash from operating activities
    11,407
    14,995
    """
    result = extract_report_metrics(
        text,
        metadata={"company_name": "of 15", "report_year": "2025"},
        enable_llm=False,
    )

    assert result["company_name"] == "Wipro Enterprises Private Limited"
    assert result["revenue"] == "₹187,472 million"
    assert result["pretax_income"] == "₹21,336 million"
    assert result["net_income"] == "₹15,925 million"
    assert result["eps"] == "₹32.98"
    assert result["operating_cash_flow"] == "₹11,407 million"
    assert result["financial_values"]["revenue"]["currency"] == "INR"
    assert result["financial_values"]["revenue"]["unit_scale"] == "million"
    assert result["financial_values"]["eps"]["metric_type"] == "per_share"


@pytest.mark.parametrize(
    ("currency", "symbol"),
    [("USD", "$"), ("EUR", "€"), ("GBP", "£")],
)
def test_revenue_priority_and_currency_generalize_across_documents(currency, symbol):
    text = f"""
    Global Manufacturing plc | Fiscal year ended 31 December 2025
    Consolidated Revenue
    {symbol}100 million
    Segment Revenue
    {symbol}12 million
    Revenue growth was 10% year over year.
    """
    result = extract_report_metrics(
        text,
        metadata={"company_name": "Global Manufacturing plc", "report_year": "2025"},
        enable_llm=False,
    )

    assert result["revenue"] == f"{symbol}100 million"
    assert result["financial_values"]["revenue"]["currency"] == currency
    assert result["financial_values"]["revenue"]["unit_scale"] == "million"
