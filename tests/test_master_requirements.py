import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction-agent"))

from compare import compare_company_metrics
from extraction_agent import extract_report_metrics
from app.services.offline_analyzer import OfflineAnalyzer


def test_extraction_preserves_canonical_value_and_material_weakness_negation():
    result = extract_report_metrics(
        "No material weakness was identified. Revenue was $520 million. Operating margin was 19.0%.",
        metadata={"company_name": "TCS", "report_year": "2024", "currency": "USD"},
        enable_llm=False,
    )

    assert result["material_weakness"]["status"] == "none_identified"
    assert result["financial_values"]["revenue"]["value"] == 520.0
    assert result["financial_values"]["revenue"]["display_value"] == "$520 million"
    assert result["financial_values"]["operating_margin"]["unit_scale"] == "percent"


def test_reported_nil_is_zero_and_not_missing():
    result = extract_report_metrics("Total debt: NIL.", metadata={"company_name": "TCS", "report_year": "2024"}, enable_llm=False)
    assert result["total_debt"] == "NIL"
    assert result["financial_values"]["total_debt"]["value"] == 0.0
    assert result["financial_values"]["total_debt"]["status"] == "reported_zero"


def test_comparison_rejects_currency_mismatch_without_conversion():
    result = compare_company_metrics(
        {"company_name": "TCS", "value": "₹267,021 crore", "currency": "INR"},
        {"company_name": "Apex", "value": "$520 million", "currency": "USD"},
        metric_name="Revenue",
    )
    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None


def test_comparison_rejects_non_equivalent_metric_names():
    result = compare_company_metrics(
        {"company_name": "TCS", "metric": "Revenue", "value": "₹267,021 crore", "currency": "INR", "document_id": "doc-a"},
        {"company_name": "Apex", "metric": "Net Income", "value": "$520 million", "currency": "USD", "document_id": "doc-b"},
    )
    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None


def test_comparison_rejects_mismatched_report_periods():
    result = compare_company_metrics(
        {"company_name": "TCS", "metric": "Revenue", "value": "₹267,021 crore", "currency": "INR", "report_year": 2024},
        {"company_name": "Apex", "metric": "Revenue", "value": "$520 million", "currency": "USD", "report_year": 2025},
    )
    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None


def test_comparison_normalizes_same_currency_indian_scales():
    result = compare_company_metrics(
        {"company_name": "A", "value": "₹2 crore", "currency": "INR"},
        {"company_name": "B", "value": "₹20 million", "currency": "INR"},
        metric_name="Revenue",
    )
    assert result["comparison_status"] == "equal"
    assert result["difference"] == 0.0


def test_offline_analyzer_does_not_flag_unrelated_decline():
    result = OfflineAnalyzer().analyze("PPA decline was disclosed; revenue remained stable.", [{"document": "PPA decline was disclosed; revenue remained stable."}])
    assert not any(flag["category"] == "performance" for flag in result["flags"])