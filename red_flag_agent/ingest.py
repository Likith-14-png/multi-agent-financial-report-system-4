from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.extraction_ingestion_service import ExtractionIngestionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a PDF or TXT document into the shared ChromaDB collection")
    parser.add_argument("--file", required=True, help="Path to the PDF or TXT file to ingest")
    parser.add_argument("--company", required=True, help="Company name stored in document metadata")
    parser.add_argument("--collection", required=True, help="Chroma collection name")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1

    service = ExtractionIngestionService()
    try:
        result = service.ingest_file(file_path=file_path, company=args.company, collection_name=args.collection)
    except Exception as exc:  # pragma: no cover - exercised in CLI path
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Collection name: {result['collection_name']}")
    print(f"Number of inserted chunks: {result['inserted_chunks']}")
    print(f"Number of skipped duplicate chunks: {result.get('skipped_duplicate_chunks', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
