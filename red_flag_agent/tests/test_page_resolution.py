from app.services.offline_analyzer import OfflineAnalyzer


def test_resolves_each_supported_page_field():
    analyzer = OfflineAnalyzer()
    for field in ("page_number", "source_page", "page_start", "page"):
        assert analyzer._resolve_page({field: 12}) == 12


def test_page_field_priority_is_deterministic():
    metadata = {"page_number": 4, "source_page": 5, "page_start": 6, "page": 7}

    assert OfflineAnalyzer._resolve_page(metadata) == 4


def test_nested_provenance_metadata_is_supported():
    metadata = {
        "provenance": {"page_number": "18"},
        "source_metadata": {"source_page": 19},
        "source": {"page_start": 20, "page": 21},
    }

    assert OfflineAnalyzer._resolve_page(metadata) == 18
    assert OfflineAnalyzer._resolve_page({"source_metadata": {"source_page": "19"}}) == 19
    assert OfflineAnalyzer._resolve_page({"source": {"page": "21"}}) == 21


def test_invalid_page_values_are_skipped():
    metadata = {
        "page_number": True,
        "source_page": "not-a-page",
        "page_start": 0,
        "page": -3,
        "provenance": {"page": " 22 "},
    }

    assert OfflineAnalyzer._resolve_page(metadata) == 22


def test_missing_page_metadata_returns_none():
    assert OfflineAnalyzer._resolve_page({"chunk_id": "chunk-1"}) is None
    assert OfflineAnalyzer._resolve_page(None) is None


def test_analyze_uses_resolved_page_without_changing_response_shape():
    chunks = [{
        "document": "Operating margin declined materially.",
        "metadata": {"source_metadata": {"source_page": "27"}},
    }]

    result = OfflineAnalyzer().analyze("What are the risks?", chunks)

    assert result["flags"][0]["page"] == 27


def test_selected_evidence_and_provenance_come_from_the_same_chunk():
    chunks = [
        {
            "document": "A significant customer concentration risk was identified.",
            "metadata": {"page": 9, "source_file": "report.pdf", "chunk_id": "page-9"},
        },
        {
            "document": "Moderate; customer concentration exists.",
            "metadata": {"page": 10, "source_file": "report.pdf", "chunk_id": "page-10"},
        },
    ]

    result = OfflineAnalyzer().analyze("What are the risks?", chunks)

    flag = next(item for item in result["flags"] if item["title"] == "Customer concentration")
    assert flag["evidence"] == "A significant customer concentration risk was identified."
    assert flag["page"] == 9
    assert flag["source_file"] == "report.pdf"
    assert flag["source_chunk"] == "page-9"


def test_customer_concentration_evidence_on_page_10_gets_page_10():
    chunks = [
        {
            "document": "Customer concentration exists.",
            "metadata": {"page": 9, "source_file": "report.pdf", "chunk_id": "page-9"},
        },
        {
            "document": "Moderate; customer concentration exists, creating significant revenue dependence.",
            "metadata": {"page": 10, "source_file": "report.pdf", "chunk_id": "page-10"},
        },
    ]

    result = OfflineAnalyzer().analyze("What are the risks?", chunks)

    flag = next(item for item in result["flags"] if item["title"] == "Customer concentration")
    assert flag["page"] == 10
    assert flag["source_file"] == "report.pdf"
    assert flag["source_chunk"] == "page-10"
    assert "significant revenue dependence" in flag["evidence"]


def test_missing_or_invalid_page_metadata_returns_null_for_that_evidence_chunk():
    result = OfflineAnalyzer().analyze(
        "What are the risks?",
        [{
            "document": "Customer concentration exists, creating revenue dependence.",
            "metadata": {"page": "unknown", "source_file": "report.pdf", "chunk_id": "no-page"},
        }],
    )

    flag = next(item for item in result["flags"] if item["title"] == "Customer concentration")
    assert flag["page"] is None
    assert flag["source_file"] == "report.pdf"
    assert flag["source_chunk"] == "no-page"