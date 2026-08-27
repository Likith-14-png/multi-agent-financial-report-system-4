import pytest
from pathlib import Path
from typing import Dict, Any

from extraction_agent import (
    parse_financial_number,
    extract_table_header_units,
    extract_report_metrics,
    _extract_company_name,
)
from compare import compare_company_metrics
from backend.orchestration.contract import ExtractionResponse


# ---------------------------------------------------------------------------
# 1. Universal Currency & Multiplier Parsing Tests
# ---------------------------------------------------------------------------

def test_indian_rupee_crore_parsing():
    """Verify parsing of Indian Rupee and Crore amounts."""
    cases = [
        ("Revenue from operations: ₹240,893 crore", 240893.0, "INR", "crore", "₹240,893 crore"),
        ("Operating profit: ₹59,311 crore", 59311.0, "INR", "crore", "₹59,311 crore"),
        ("Profit before tax: ₹61,997 crore", 61997.0, "INR", "crore", "₹61,997 crore"),
        ("Profit for the year: ₹46,099 crore", 46099.0, "INR", "crore", "₹46,099 crore"),
        ("Total assets: ₹1,46,449 crore", 146449.0, "INR", "crore", "₹1,46,449 crore"),
        ("Total liabilities: ₹55,130 crore", 55130.0, "INR", "crore", "₹55,130 crore"),
        ("Total equity: ₹91,319 crore", 91319.0, "INR", "crore", "₹91,319 crore"),
        ("Borrowings: Rs. 55,130 crore", 55130.0, "INR", "crore", "Rs. 55,130 crore"),
        ("Liabilities: INR 55,130 crore", 55130.0, "INR", "crore", "INR 55,130 crore"),
    ]
    for text, expected_num, expected_curr, expected_unit, expected_raw in cases:
        parsed = parse_financial_number(text)
        assert parsed is not None, f"Failed to parse: {text}"
        assert parsed["numeric_value"] == expected_num, f"Numeric mismatch for {text}"
        assert parsed["currency"] == expected_curr, f"Currency mismatch for {text}"
        assert parsed["unit"] == expected_unit, f"Unit mismatch for {text}"
        assert parsed["raw_value"] == expected_raw, f"Raw value mismatch for {text}"


def test_western_and_european_currency_parsing():
    """Verify parsing of USD, EUR, and GBP amounts."""
    cases = [
        ("Consolidated revenue: US$29.1 billion", 29.1, "USD", "billion", "$29.1 billion"),
        ("Net sales: $15.3 billion", 15.3, "USD", "billion", "$15.3 billion"),
        ("Operating profit: €5.2 billion", 5.2, "EUR", "billion", "€5.2 billion"),
        ("Capex: £4.5 million", 4.5, "GBP", "million", "£4.5 million"),
    ]
    for text, expected_num, expected_curr, expected_unit, expected_raw in cases:
        parsed = parse_financial_number(text)
        assert parsed is not None, f"Failed to parse: {text}"
        assert parsed["numeric_value"] == expected_num
        assert parsed["currency"] == expected_curr
        assert parsed["unit"] == expected_unit
        assert parsed["raw_value"] == expected_raw


def test_number_formatting_and_comma_groups():
    """Verify parsing of Indian 2-digit comma grouping and Western 3-digit comma grouping."""
    assert parse_financial_number("₹1,46,449 crore")["numeric_value"] == 146449.0
    assert parse_financial_number("₹14,64,490 lakh")["numeric_value"] == 1464490.0
    assert parse_financial_number("$146,449 million")["numeric_value"] == 146449.0
    assert parse_financial_number("$1,234,567 thousand")["numeric_value"] == 1234567.0


def test_table_header_units_inheritance():
    """Verify table header extraction and inheritance."""
    curr, unit = extract_table_header_units("Statement of Profit and Loss (₹ in crore)")
    assert curr == "INR"
    assert unit == "crore"

    curr2, unit2 = extract_table_header_units("Balance Sheet (in lakhs)")
    assert curr2 == "INR"
    assert unit2 == "lakh"

    curr3, unit3 = extract_table_header_units("Income Statement (in USD millions)")
    assert curr3 == "USD"
    assert unit3 == "million"

    # Cell inheriting header
    cell_parsed = parse_financial_number("59,311", inherited_currency="INR", inherited_unit="crore")
    assert cell_parsed["currency"] == "INR"
    assert cell_parsed["unit"] == "crore"
    assert cell_parsed["numeric_value"] == 59311.0
    assert cell_parsed["raw_value"] == "₹59,311 crore"


# ---------------------------------------------------------------------------
# 2. Multi-Factor Traceability & Anti-Hallucination Tests
# ---------------------------------------------------------------------------

def test_esg_chunk_rejection_for_financial_metrics():
    """Verify that ESG sustainability chunks are never assigned to EPS, liabilities, or equity."""
    tcs_text = """
    Tata Consultancy Services Limited (TCS) Annual Report 2024
    Statement of Profit and Loss:
    Revenue from operations: ₹240,893 crore
    Operating income (EBIT): ₹59,311 crore
    Profit before tax: ₹61,997 crore
    Profit for the year: ₹46,099 crore
    Basic earnings per share: ₹125.88
    Diluted earnings per share: ₹125.88

    Balance Sheet:
    Total assets: ₹1,46,449 crore
    Total liabilities: ₹55,130 crore
    Total equity: ₹91,319 crore

    Operating & Financial Performance Review:
    Performance trend EPS: ₹127.74
    Consolidated revenue: US$29.1 billion
    """

    chunk_records = [
        {
            "chunk_id": "chunk-0-cover",
            "page_start": 1,
            "section_title": "Corporate Overview",
            "text": "Tata Consultancy Services Limited (TCS) Annual Report 2024.",
        },
        {
            "chunk_id": "chunk-1-esg-sustainability",
            "page_start": 2,
            "section_title": "ESG and Sustainability Highlights",
            "text": (
                "Average learning hours per employee: 87.1 hrs.\n"
                "Achieved a reduction of 80% in absolute Scope 1 and Scope 2 emissions.\n"
                "Environmental Policy Standards (EPS) and initiatives deployed across campus.\n"
                "Diversity and equity programs expanded."
            ),
        },
        {
            "chunk_id": "chunk-2-financial-statements",
            "page_start": 72,
            "section_title": "Statement of Profit and Loss",
            "text": (
                "Statement of Profit and Loss for the year ended March 31, 2024 (₹ in crore):\n"
                "Revenue from operations: ₹240,893 crore\n"
                "Operating income (EBIT): ₹59,311 crore\n"
                "Profit before tax: ₹61,997 crore\n"
                "Profit for the year: ₹46,099 crore\n"
                "Basic earnings per share: ₹125.88\n"
                "Diluted earnings per share: ₹125.88"
            ),
        },
        {
            "chunk_id": "chunk-3-balance-sheet",
            "page_start": 74,
            "section_title": "Balance Sheet",
            "text": (
                "Balance Sheet as at March 31, 2024 (₹ in crore):\n"
                "Total assets: ₹1,46,449 crore\n"
                "Total liabilities: ₹55,130 crore\n"
                "Total equity: ₹91,319 crore"
            ),
        },
        {
            "chunk_id": "chunk-4-mda-performance",
            "page_start": 38,
            "section_title": "Operating & Financial Review",
            "text": (
                "Operating & Financial Performance Review:\n"
                "Performance trend EPS: ₹127.74\n"
                "Consolidated revenue: US$29.1 billion"
            ),
        },
    ]

    result = extract_report_metrics(
        tcs_text,
        metadata={"company_name": "Tata Consultancy Services Limited (TCS)", "report_year": "2024"},
        chunk_records=chunk_records,
    )

    # 1. Check Canonical Top-Level Values
    assert result["revenue"] == "₹240,893 crore"
    assert result["operating_income"] == "₹59,311 crore"
    assert result["pretax_income"] == "₹61,997 crore"
    assert result["net_income"] == "₹46,099 crore"
    assert result["total_assets"] == "₹1,46,449 crore"
    assert result["total_liabilities"] == "₹55,130 crore"
    assert result["total_equity"] == "₹91,319 crore"
    assert result["basic_eps"] == "₹125.88"
    assert result["diluted_eps"] == "₹125.88"
    assert result["trend_eps"] == "₹127.74"

    # 2. Check Traceability: Assert ESG chunk is NEVER chosen for financial metrics
    trace = result["traceability"]
    assert trace["eps"]["source_chunk_id"] != "chunk-1-esg-sustainability"
    assert trace["eps"]["source_chunk_id"] == "chunk-2-financial-statements"
    assert trace["total_liabilities"]["source_chunk_id"] == "chunk-3-balance-sheet"
    assert trace["total_equity"]["source_chunk_id"] == "chunk-3-balance-sheet"
    assert "Scope 1" not in trace["eps"]["evidence"]


def test_multiple_revenue_observations_coexistence():
    """Verify that both ₹240,893 crore and US$29.1 billion coexist in detailed_metrics."""
    text = (
        "Statement of Profit and Loss:\nRevenue from operations: ₹240,893 crore\n"
        "Global Highlights:\nConsolidated revenue: US$29.1 billion"
    )
    result = extract_report_metrics(text, metadata={"company_name": "TCS", "report_year": "2024"})

    detailed = result["detailed_metrics"]
    raw_values = [d.get("raw_value") for d in detailed if d.get("normalized_name") == "revenue"]
    assert "₹240,893 crore" in raw_values
    assert "$29.1 billion" in raw_values or "US$29.1 billion" in raw_values

    # Top-level canonical remains audited operating revenue
    assert result["revenue"] == "₹240,893 crore"


def test_company_name_balanced_parentheses():
    """Verify that company names with legal parentheses retain closing parentheses."""
    text1 = "Tata Consultancy Services Limited (TCS) Annual Report 2024"
    text2 = "ABB Ltd. (ABB) Annual Report 2025"

    assert _extract_company_name(text1, metadata={"company_name": "Tata Consultancy Services Limited (TCS)"}) == "Tata Consultancy Services Limited (TCS)"
    assert _extract_company_name(text2, metadata={"company_name": "ABB Ltd. (ABB)"}) == "ABB Ltd. (ABB)"


# ---------------------------------------------------------------------------
# 3. Downstream Consumer Non-Regression Tests
# ---------------------------------------------------------------------------

def test_extraction_response_contract_pydantic_validation():
    """Verify that the extraction result successfully validates against Pydantic ExtractionResponse."""
    tcs_text = "Revenue from operations: ₹240,893 crore\nOperating income: ₹59,311 crore"
    res = extract_report_metrics(tcs_text, metadata={"analysis_id": "test-123", "document_id": "doc-456"})
    resp_obj = ExtractionResponse.model_validate(res)
    assert resp_obj.analysis_id == "test-123"
    assert resp_obj.revenue == "₹240,893 crore"
    assert len(resp_obj.detailed_metrics) > 0


def test_internal_extraction_fields_are_excluded_from_public_model_serialization():
    res = extract_report_metrics(
        "Revenue was $10 million.",
        metadata={"analysis_id": "test-123", "document_id": "doc-456"},
        enable_llm=False,
    )
    public_payload = ExtractionResponse.model_validate(res).model_dump(exclude_none=True)

    assert "yearly_metrics" not in public_payload
    assert "detailed_metrics" not in public_payload
    assert "observations" not in public_payload
    assert "traceability" not in public_payload
    assert res["observations"]
    assert res["observations"][0]["numeric_value"] == 10.0


def test_compare_company_metrics_with_new_extraction():
    """Verify that comparison agent can parse extracted string metrics without error."""
    company_a = {
        "company_name": "TCS",
        "report_year": "2024",
        "revenue": "₹240,893 crore",
        "operating_income": "₹59,311 crore",
        "net_income": "₹46,099 crore",
    }
    company_b = {
        "company_name": "Infosys",
        "report_year": "2024",
        "revenue": "₹153,670 crore",
        "operating_income": "₹31,747 crore",
        "net_income": "₹26,233 crore",
    }
    comparison = compare_company_metrics(company_a, company_b)
    assert comparison is not None
    assert "difference" in comparison
    assert comparison["company_a"]["value"] == 240893.0
    assert comparison["company_b"]["value"] == 153670.0
    assert comparison["unit"] == "crore"
    assert comparison["difference"] == -87223.0
