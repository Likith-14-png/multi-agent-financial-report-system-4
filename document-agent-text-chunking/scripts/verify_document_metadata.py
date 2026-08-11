#!/usr/bin/env python3
"""Audit and optionally migrate the financial research Chroma collection."""

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, Set

import chromadb

from document_agent import DocumentAgent, DocumentAgentConfig
from shared_chroma_path import resolve_chroma_db_path

COLLECTION_NAME = "financial_research_2024"
ENTERPRISE_FIELDS: Set[str] = {
    "company_name",
    "document_id",
    "doc_type",
    "company_index",
    "document_title",
    "report_year",
    "report_period",
    "financial_year",
    "page_number",
    "page_start",
    "page_end",
    "page_numbers",
    "section_title",
    "section_type",
    "financial_entities",
    "semantic_tags",
    "document_version",
    "previous_chunk_id",
    "next_chunk_id",
    "is_table",
    "is_financial_table",
    "is_chart",
}


def collection_path() -> Path:
    """Resolve the same database directory used by the viewer and agent."""
    scripts_dir = Path(__file__).resolve().parent
    return resolve_chroma_db_path(
        script_file=__file__,
        workspace_root=scripts_dir.parent.parent,
    ).resolve()


def inspect_collection(db_path: Path) -> Dict[str, Any]:
    """Return one stored chunk and the enterprise fields missing from it."""
    client = chromadb.PersistentClient(path=str(db_path))
    collection_names = [collection.name for collection in client.list_collections()]
    if COLLECTION_NAME not in collection_names:
        return {
            "db_path": str(db_path),
            "collection": COLLECTION_NAME,
            "collection_exists": False,
            "count": 0,
            "metadata": {},
            "missing_fields": sorted(ENTERPRISE_FIELDS),
        }

    collection = client.get_collection(COLLECTION_NAME)
    data = collection.get(limit=1, include=["metadatas"])
    metadata = (data.get("metadatas") or [{}])[0]
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "db_path": str(db_path),
        "collection": COLLECTION_NAME,
        "collection_exists": True,
        "count": collection.count(),
        "metadata": metadata,
        "missing_fields": sorted(ENTERPRISE_FIELDS.difference(metadata)),
    }


def print_report(report: Dict[str, Any]) -> None:
    """Print an audit report without suppressing unknown metadata keys."""
    print(f"VERIFY | db_path={report['db_path']}")
    print(f"VERIFY | collection={report['collection']}")
    print(f"VERIFY | collection_exists={report['collection_exists']}")
    print(f"VERIFY | count={report['count']}")
    print("VERIFY | metadata:")
    for key, value in sorted(report["metadata"].items()):
        print(f"  {key}: {value}")
    print(f"VERIFY | missing_enterprise_fields={report['missing_fields']}")


def migrate(db_path: Path, document_path: Path) -> Dict[str, Any]:
    """Recreate the configured collection and ingest the supplied PDF."""
    client = chromadb.PersistentClient(path=str(db_path))
    existing_names = [collection.name for collection in client.list_collections()]
    if COLLECTION_NAME in existing_names:
        client.delete_collection(COLLECTION_NAME)
        print(f"MIGRATE | deleted_collection={COLLECTION_NAME}")

    config = DocumentAgentConfig(
        db_path=str(db_path),
        collection_name=COLLECTION_NAME,
        overwrite=False,
        enable_document_versioning=True,
    )
    agent = DocumentAgent(config)
    result = agent.ingest_document(str(document_path))
    print(f"MIGRATE | ingestion_result={result}")
    if result["status"] != "success" or result["chunks"] == 0:
        raise RuntimeError(f"Migration ingestion failed: {result}")
    return inspect_collection(db_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Delete and recreate the configured collection before re-ingestion.",
    )
    parser.add_argument(
        "--document",
        type=Path,
        default=Path(__file__).resolve().parent / "demo_data" / "2024_Annual_Report.pdf",
        help="PDF to ingest when --migrate is supplied.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = collection_path()
    report = migrate(db_path, args.document) if args.migrate else inspect_collection(db_path)
    print_report(report)
    if report["missing_fields"]:
        return 1
    print("VERIFY | status=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
