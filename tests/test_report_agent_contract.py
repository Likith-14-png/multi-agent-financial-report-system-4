from backend.orchestration.contract import ReportResult, validate_analysis_context
from report_agent import ReportAgent


def build_analysis_contract():
    return {
        "metadata": {
            "analysis_id": "analysis-123",
            "document_id": "document-456",
            "company_name": "ABB",
            "report_year": 2025,
            "chunk_id": "chunk-7",
        },
        "extraction": {
            "metrics": [
                {"metric": "Revenue", "value": "$15.3 billion", "unit": "billion", "year": 2025, "source": "ABB annual report", "chunk_id": "chunk-7"},
                {"metric": "Operating Income", "value": "$2.1 billion", "unit": "billion", "year": 2025, "source": "ABB annual report", "chunk_id": "chunk-8"},
                {"metric": "Total Assets", "value": "$22.6 billion", "unit": "billion", "year": 2025, "source": "ABB annual report", "chunk_id": "chunk-9"},
                {"metric": "Total Liabilities", "value": "$9.8 billion", "unit": "billion", "year": 2025, "source": "ABB annual report", "chunk_id": "chunk-10"},
            ]
        },
        "research": {
            "answer": "ABB grew revenue and maintained cash generation.",
            "sources": [
                {"snippet": "Revenue remained resilient.", "source_file": "abb_2025_report.txt", "chunk_id": "chunk-7"},
                {"snippet": "Operating income improved.", "source_file": "abb_2025_report.txt", "chunk_id": "chunk-8"},
            ],
        },
        "red_flags": {
            "overall_risk": "Moderate",
            "total_flags": 1,
            "flags": [{
                "category": "liquidity",
                "severity": "medium",
                "title": "Balance sheet risk",
                "description": "Debt exposure requires monitoring.",
                "recommendation": "Review leverage and liquidity.",
                "evidence": ["chunk-10"],
            }],
            "model_used": "offline-fallback",
        },
        "comparison": {
            "comparison_type": "year_over_year",
            "records": [{
                "metric": "Revenue",
                "previous_year": 2024,
                "current_year": 2025,
                "previous_value": 13.8,
                "current_value": 15.3,
                "absolute_change": 1.5,
                "percentage_change": 10.87,
                "direction": "increase",
                "source_chunks": ["chunk-7"],
            }],
            "summary": {"metrics_compared": 1, "increased": 1, "decreased": 0, "unchanged": 0},
        },
    }


def test_report_agent_accepts_canonical_contract_and_preserves_values():
    analysis = build_analysis_contract()

    report = ReportAgent().generate(analysis)

    assert report["metadata"]["analysis_id"] == "analysis-123"
    assert report["metadata"]["company_name"] == "ABB"
    assert report["metadata"]["report_year"] == 2025
    assert report["report_status"] == "complete"
    assert report["executive_summary"]
    assert report["financial_metrics"][0]["metric"] == "Revenue"
    assert report["financial_metrics"][0]["value"] == "$15.3 billion"
    assert report["risk_assessment"]["overall_risk"] == "Moderate"
    assert report["comparison"]["records"][0]["metric"] == "Revenue"
    assert report["research_findings"][0]["finding"] == "ABB grew revenue and maintained cash generation."
    assert report["recommendations"][0]


def test_report_agent_normalizes_duplicate_red_flag_evidence_fields():
    report = ReportAgent().generate({
        "metadata": {"analysis_id": "analysis-123", "document_id": "document-456", "company_name": "ABB", "report_year": 2025},
        "extraction": {"metrics": []},
        "research": {"answer": "ABB grew revenue.", "sources": []},
        "red_flags": {
            "overall_risk": "Medium",
            "total_flags": 1,
            "flags": [{
                "category": "liquidity",
                "title": "Balance sheet risk",
                "description": "Debt exposure requires monitoring.",
                "evidence": "Debt exposure requires monitoring.",
                "recommendation": "Review leverage and liquidity.",
            }],
        },
        "comparison": {"comparison_type": "single_year", "records": [], "summary": {}},
    })

    assert report["evidence"][0]["snippet"] == "Debt exposure requires monitoring."
    assert "evidence" not in report["evidence"][0]


def test_report_agent_preserves_upstream_source_chunks_on_findings():
    report = ReportAgent().generate({
        "metadata": {"analysis_id": "analysis-123", "document_id": "document-456", "company_name": "ABB", "report_year": 2025},
        "extraction": {"metrics": []},
        "research": {
            "answer": "ABB grew revenue.",
            "sources": [
                {"snippet": "Revenue improved.", "source_file": "abb_2025_report.txt", "chunk_id": "chunk-1", "source_chunks": ["chunk-1", "chunk-1"]},
                {"snippet": "Liquidity remained stable.", "source_file": "abb_2025_report.txt", "chunk_id": "chunk-2", "source_chunks": ["chunk-2", "chunk-3", "chunk-3"]},
            ],
        },
        "red_flags": {"flags": []},
        "comparison": {"comparison_type": "single_year", "records": [], "summary": {}},
    })

    findings = report["research_findings"]
    assert findings[0]["source_chunks"] == [] or findings[0]["source_chunks"] == ["chunk-1"]
    assert any(finding["source_chunks"] == ["chunk-1"] for finding in findings)
    assert any(finding["source_chunks"] == ["chunk-2", "chunk-3"] for finding in findings)


def test_report_agent_missing_metadata_reports_failed():
    report = ReportAgent().generate({
        "metadata": {"company_name": "ABB"},
        "extraction": {"metrics": []},
        "research": {"answer": "", "sources": []},
        "red_flags": {},
        "comparison": {},
    })

    assert report["report_status"] == "failed"


def test_report_agent_validates_canonical_contract():
    model = validate_analysis_context(build_analysis_contract())
    assert model.metadata.company_name == "ABB"
    assert model.metadata.report_year == 2025

    report_model = ReportResult.model_validate({
        "metadata": {"analysis_id": "analysis-123", "document_id": "document-456", "company_name": "ABB", "report_year": 2025},
        "executive_summary": "Summary",
        "financial_metrics": [],
        "research_findings": [],
        "risk_assessment": {"overall_risk": "Low", "total_flags": 0, "flags": []},
        "comparison": {"comparison_type": "single_year", "records": [], "summary": {}},
        "evidence": [],
        "recommendations": [],
        "report_status": "complete",
    })
    assert report_model.report_status == "complete"
