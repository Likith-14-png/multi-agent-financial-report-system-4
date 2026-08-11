import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from document_agent import resolve_chroma_db_path
from document_agent_refactored import DocumentAgent, DocumentAgentConfig, discover_supported_files


def test_ingest_sample_text_file(tmp_path):
    db_path = tmp_path / "chroma_db"
    config = DocumentAgentConfig(
        db_path=str(db_path),
        collection_name="test_collection",
        chunk_size=800,
        chunk_overlap=150,
        overwrite=True,
    )
    agent = DocumentAgent(config)

    sample_path = Path(__file__).resolve().parents[1] / "scripts" / "demo_data" / "2024_Annual_Report.pdf"
    result = agent.ingest_document(str(sample_path))

    assert result["status"] == "success"
    assert result["chunks"] >= 1
    assert result["analysis_id"]
    assert result["collection"] == "test_collection"
    assert agent.get_collection_stats()["total_chunks"] >= 1


def test_duplicate_document_is_skipped(tmp_path):
    db_path = tmp_path / "chroma_db"
    config = DocumentAgentConfig(
        db_path=str(db_path),
        collection_name="test_collection_duplicates",
        chunk_size=800,
        chunk_overlap=150,
        overwrite=False,
    )
    agent = DocumentAgent(config)

    sample_path = Path(__file__).resolve().parents[1] / "scripts" / "demo_data" / "2024_Annual_Report.pdf"
    analysis_id = agent.create_analysis()
    first = agent.ingest_document(str(sample_path), analysis_id=analysis_id)
    second = agent.ingest_document(str(sample_path), analysis_id=analysis_id)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["duplicates_skipped"] is True
    assert second["chunks"] == 0


def test_same_document_can_be_indexed_in_new_analysis(tmp_path):
    db_path = tmp_path / "chroma_db"
    config = DocumentAgentConfig(
        db_path=str(db_path),
        collection_name="test_collection_duplicate_across_analyses",
        chunk_size=800,
        chunk_overlap=150,
        overwrite=False,
    )
    agent = DocumentAgent(config)

    sample_path = Path(__file__).resolve().parents[1] / "scripts" / "demo_data" / "2024_Annual_Report.pdf"
    first = agent.ingest_document(str(sample_path), analysis_id="analysis-one")
    second = agent.ingest_document(str(sample_path), analysis_id="analysis-two")

    assert first["status"] == "success"
    assert first["chunks"] >= 1
    assert second["status"] == "success"
    assert second["duplicates_skipped"] is False
    assert second["chunks"] == first["chunks"]
    assert agent.get_documents_by_analysis("analysis-one")["total_chunks"] == first["chunks"]
    assert agent.get_documents_by_analysis("analysis-two")["total_chunks"] == second["chunks"]


def test_duplicate_content_with_different_filename_is_skipped(tmp_path):
    db_path = tmp_path / "chroma_db"
    config = DocumentAgentConfig(
        db_path=str(db_path),
        collection_name="test_collection_renamed_duplicates",
        chunk_size=800,
        chunk_overlap=150,
        overwrite=True,
    )
    agent = DocumentAgent(config)

    first_path = tmp_path / "original_report.txt"
    second_path = tmp_path / "renamed_report.txt"
    report_text = "Revenue increased substantially during the financial year. " * 5
    first_path.write_text(report_text, encoding="utf-8")
    second_path.write_text(report_text, encoding="utf-8")

    analysis_id = agent.create_analysis()
    first = agent.ingest_document(str(first_path), analysis_id=analysis_id)
    second = agent.ingest_document(str(second_path), analysis_id=analysis_id)

    assert first["status"] == "success"
    assert first["chunks"] >= 1
    assert second["status"] == "success"
    assert second["duplicates_skipped"] is True
    assert second["chunks"] == 0
    assert agent.get_collection_stats()["total_chunks"] == first["chunks"]


def test_discover_supported_files_from_directory(tmp_path):
    demo_dir = tmp_path / "demo_data"
    demo_dir.mkdir()
    (demo_dir / "first.txt").write_text("first document", encoding="utf-8")
    (demo_dir / "second.pdf").write_text("second document", encoding="utf-8")
    (demo_dir / "ignore.csv").write_text("ignored", encoding="utf-8")

    discovered = discover_supported_files(demo_dir)

    assert [path.name for path in discovered] == ["first.txt", "second.pdf"]


def test_resolve_chroma_db_path_prefers_workspace_root(tmp_path):
    workspace_root = tmp_path / "workspace"
    project_root = workspace_root / "document-agent-text-chunking"
    project_root.mkdir(parents=True)
    (workspace_root / "enterprise_chroma_db").mkdir()
    (project_root / "enterprise_chroma_db").mkdir()

    resolved_path = resolve_chroma_db_path(
        script_file=project_root / "scripts" / "document_agent.py",
        workspace_root=workspace_root,
    )

    assert resolved_path == workspace_root / "enterprise_chroma_db"
