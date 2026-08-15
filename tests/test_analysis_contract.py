from backend.orchestration.contract import AnalysisContext, AnalysisMetadata, validate_analysis_context


def test_valid_complete_contract():
    payload = {
        "metadata": {
            "analysis_id": "analysis-1",
            "document_id": "document-1",
            "company_name": "ABB",
            "report_year": 2025,
            "chunk_id": "chunk-1",
        },
        "extraction": {"metrics": [{"metric": "Revenue", "value": 15.3, "unit": "billion"}]},
        "research": {"answer": "Revenue grew.", "evidence": [{"text": "Revenue", "chunk_id": "chunk-1"}]},
        "red_flags": {"overall_risk": "Low", "total_flags": 0, "flags": []},
        "comparison": {"comparison_type": "single_year", "records": [{"metric": "Revenue", "current_value": 15.3, "direction": "unavailable"}]},
        "report": {"company_name": "ABB", "report_year": 2025},
    }

    model = validate_analysis_context(payload)
    assert model.metadata.analysis_id == "analysis-1"
    assert model.metadata.company_name == "ABB"
    assert model.report["company_name"] == "ABB"


def test_missing_analysis_id_raises():
    payload = {
        "metadata": {"document_id": "document-1", "company_name": "ABB", "report_year": 2025},
        "extraction": {},
        "research": {},
        "red_flags": {},
        "comparison": {},
        "report": {},
    }

    try:
        validate_analysis_context(payload)
        assert False, "Expected validation error"
    except Exception:
        pass


def test_missing_document_id_raises():
    payload = {
        "metadata": {"analysis_id": "analysis-1", "company_name": "ABB", "report_year": 2025},
        "extraction": {},
        "research": {},
        "red_flags": {},
        "comparison": {},
        "report": {},
    }

    try:
        validate_analysis_context(payload)
        assert False, "Expected validation error"
    except Exception:
        pass


def test_missing_company_name_raises():
    payload = {
        "metadata": {"analysis_id": "analysis-1", "document_id": "document-1", "report_year": 2025},
        "extraction": {},
        "research": {},
        "red_flags": {},
        "comparison": {},
        "report": {},
    }

    try:
        validate_analysis_context(payload)
        assert False, "Expected validation error"
    except Exception:
        pass


def test_invalid_report_year_raises():
    payload = {
        "metadata": {"analysis_id": "analysis-1", "document_id": "document-1", "company_name": "ABB", "report_year": "invalid"},
        "extraction": {},
        "research": {},
        "red_flags": {},
        "comparison": {},
        "report": {},
    }

    try:
        validate_analysis_context(payload)
        assert False, "Expected validation error"
    except Exception:
        pass


def test_json_serialization_round_trip():
    payload = {
        "metadata": {"analysis_id": "analysis-1", "document_id": "document-1", "company_name": "ABB", "report_year": 2025},
        "extraction": {},
        "research": {},
        "red_flags": {},
        "comparison": {},
        "report": {},
    }

    model = AnalysisContext.model_validate(payload)
    serialized = model.model_dump(mode="json")
    assert serialized["metadata"]["company_name"] == "ABB"
    assert serialized["metadata"]["report_year"] == 2025
