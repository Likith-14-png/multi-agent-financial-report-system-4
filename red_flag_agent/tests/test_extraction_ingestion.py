from pathlib import Path

from app.services.extraction_ingestion_service import ExtractionIngestionService


def test_ingest_text_file_creates_collection_and_skips_duplicates(tmp_path: Path) -> None:
    source_path = tmp_path / "sample_report.txt"
    source_path.write_text(
        "Acme Corp annual report. Revenue increased significantly this year.\n\n"
        "Cash flow remained strong and liabilities stayed manageable.",
        encoding="utf-8",
    )

    persist_dir = tmp_path / "chroma"
    service = ExtractionIngestionService(persist_directory=str(persist_dir))

    first_result = service.ingest_file(
        file_path=str(source_path),
        company="Acme Corp",
        collection_name="test_collection",
    )

    assert first_result["inserted_chunks"] > 0
    assert first_result["collection_name"] == "test_collection"
    assert service.chroma_service.collection_exists("test_collection")

    stored = service.chroma_service.get_collection("test_collection").get(include=["metadatas"])
    assert stored["metadatas"]
    assert stored["metadatas"][0]["company"] == "Acme Corp"
    assert stored["metadatas"][0]["source_file"] == str(source_path)

    second_result = service.ingest_file(
        file_path=str(source_path),
        company="Acme Corp",
        collection_name="test_collection",
    )

    assert second_result["inserted_chunks"] == 0
    assert second_result["duplicates_skipped"] is True
