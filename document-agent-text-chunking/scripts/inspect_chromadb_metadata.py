#!/usr/bin/env python3
"""Read-only inspection utility for the financial research ChromaDB collection."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import chromadb

from shared_chroma_path import resolve_chroma_db_path

COLLECTION_NAME = "financial_research_v1"
SAMPLE_TEXT_LIMIT = 300


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _format_value(value: Any) -> str:
    if value is None:
        return "<None>"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value) if value else "<empty>"
    if isinstance(value, dict):
        return str(value)
    return str(value)


def inspect_collection(collection: Any) -> Dict[str, Any]:
    data = collection.get(include=["documents", "metadatas"])
    ids = _coerce_list(data.get("ids", []))
    documents = _coerce_list(data.get("documents", []))
    metadatas = _coerce_list(data.get("metadatas", []))

    records: List[Dict[str, Any]] = []
    for index, chunk_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        document_text = documents[index] if index < len(documents) else ""
        if not isinstance(metadata, dict):
            metadata = {}
        records.append({"id": chunk_id, "document": document_text, "metadata": metadata})

    metadata_keys = []
    seen_keys = set()
    for record in records:
        for key in record["metadata"].keys():
            if key not in seen_keys:
                seen_keys.add(key)
                metadata_keys.append(key)

    by_analysis: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        analysis_id = record["metadata"].get("analysis_id") or "<unknown>"
        by_analysis[str(analysis_id)].append(record)

    unique_docs = {record["metadata"].get("doc_hash") for record in records if record["metadata"].get("doc_hash")}
    unique_sources = {record["metadata"].get("source") for record in records if record["metadata"].get("source")}
    unique_companies = {record["metadata"].get("company_name") for record in records if record["metadata"].get("company_name")}
    unique_years = {record["metadata"].get("report_year") or record["metadata"].get("financial_year") for record in records if record["metadata"].get("report_year") or record["metadata"].get("financial_year")}

    missing_keys = []
    for key in metadata_keys:
        if any(key not in record["metadata"] for record in records):
            missing_keys.append(key)

    return {
        "collection_name": collection.name,
        "record_count": len(records),
        "unique_documents": len(unique_docs),
        "unique_analysis_sessions": len(by_analysis),
        "source_files": sorted(unique_sources),
        "companies": sorted(unique_companies),
        "report_years": sorted(str(year) for year in unique_years if year is not None),
        "metadata_keys": metadata_keys,
        "missing_keys": missing_keys,
        "records": records,
        "by_analysis": by_analysis,
    }


def print_report(report: Dict[str, Any]) -> None:
    print("=" * 80)
    print("ChromaDB Metadata Inspection")
    print("=" * 80)
    print(f"Collection Name        : {report['collection_name']}")
    print(f"Total Chunks           : {report['record_count']}")
    print(f"Total Unique Documents : {report['unique_documents']}")
    print(f"Total Unique Analysis Sessions: {report['unique_analysis_sessions']}")
    print("Source Files           :")
    for item in report["source_files"] or ["<none>"]:
        print(f"  - {item}")
    print("Companies              :")
    for item in report["companies"] or ["<none>"]:
        print(f"  - {item}")
    print("Report Years           :")
    for item in report["report_years"] or ["<none>"]:
        print(f"  - {item}")

    print("\n" + "=" * 80)
    print("Metadata Schema")
    print("=" * 80)
    if report["metadata_keys"]:
        for key in report["metadata_keys"]:
            print(f"- {key}")
    else:
        print("<no metadata keys found>")

    print("\n" + "=" * 80)
    print("Sample Chunk")
    print("=" * 80)
    if report["records"]:
        sample = report["records"][0]
        text_preview = (sample["document"] or "")[:SAMPLE_TEXT_LIMIT]
        print(f"Chunk ID      : {sample['id']}")
        print(f"Document Text : {text_preview}")
        print("Complete Metadata:")
        for key, value in sample["metadata"].items():
            print(f"  {key}: {_format_value(value)}")
    else:
        print("<no chunks found>")

    print("\n" + "=" * 80)
    print("All Metadata Fields by Chunk")
    print("=" * 80)
    for record in report["records"]:
        print("-" * 52)
        print(f"Chunk ID: {record['id']}")
        print("Metadata")
        print("---------")
        for key in report["metadata_keys"]:
            value = record["metadata"].get(key)
            print(f"{key:<24} : {_format_value(value)}")
        print("-" * 52)

    print("\n" + "=" * 80)
    print("Unique Analysis IDs")
    print("=" * 80)
    for analysis_id in sorted(report["by_analysis"].keys()):
        analysis_records = report["by_analysis"][analysis_id]
        documents = {record["metadata"].get("doc_hash") for record in analysis_records if record["metadata"].get("doc_hash")}
        companies = {record["metadata"].get("company_name") for record in analysis_records if record["metadata"].get("company_name")}
        sources = {record["metadata"].get("source") for record in analysis_records if record["metadata"].get("source")}
        print(f"Analysis ID: {analysis_id}")
        print(f"  Documents: {len(documents)}")
        print(f"  Chunks   : {len(analysis_records)}")
        print(f"  Companies: {', '.join(sorted(companies)) if companies else '<none>'}")
        print(f"  Sources  : {', '.join(sorted(sources)) if sources else '<none>'}")

    print("\n" + "=" * 80)
    print("Metadata Keys Missing From Any Chunk")
    print("=" * 80)
    if report["missing_keys"]:
        for key in report["missing_keys"]:
            print(f"- {key}")
    else:
        print("<no missing metadata keys>")


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    db_path = resolve_chroma_db_path(__file__, project_root.parent).resolve()
    client = chromadb.PersistentClient(path=str(db_path))

    collection_names = [collection.name for collection in client.list_collections()]
    if COLLECTION_NAME not in collection_names:
        print(f"Collection '{COLLECTION_NAME}' was not found at {db_path}.")
        raise SystemExit(1)

    collection = client.get_collection(COLLECTION_NAME)
    report = inspect_collection(collection)
    print_report(report)


if __name__ == "__main__":
    main()
