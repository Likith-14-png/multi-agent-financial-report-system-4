from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from app.config import CHROMA_DIR, DEFAULT_COLLECTION_NAME
from app.services.chroma_service import ChromaService
from app.utils.logger import get_logger
from app.utils import metrics as metrics

logger = get_logger(__name__)

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = WORKSPACE_ROOT / "document-agent-text-chunking" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class ExtractionIngestionService:
    """Extract text from files, chunk it, and ingest it into the shared ChromaDB collection."""

    def __init__(self, persist_directory: str | None = None) -> None:
        self.chroma_service = ChromaService(persist_directory=persist_directory or CHROMA_DIR)

    def ingest_file(
        self,
        file_path: str | Path,
        company: str,
        collection_name: str | None = None,
        page: int | None = None,
        section: str | None = None,
    ) -> Dict[str, Any]:
        metrics.INGESTION_REQUESTS_TOTAL.inc()
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        collection_name = collection_name or DEFAULT_COLLECTION_NAME
        extracted_text = self._extract_text(path)
        chunks = self._split_text_into_chunks(extracted_text)

        if not chunks:
            return {
                "collection_name": collection_name,
                "inserted_chunks": 0,
                "duplicates_skipped": True,
                "status": "no_content",
            }

        collection = self.chroma_service.get_collection(collection_name)
        existing = collection.get(where={"source_file": str(path)}, limit=1, include=["metadatas"])
        if existing.get("ids"):
            logger.info("Skipping duplicate ingestion for %s in collection %s", path, collection_name)
            return {
                "collection_name": collection_name,
                "inserted_chunks": 0,
                "duplicates_skipped": True,
                "skipped_duplicate_chunks": len(chunks),
                "status": "duplicate",
            }

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        for index, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append(
                {
                    "company": company,
                    "page": page if page is not None else 1,
                    "section": section or self._infer_section(chunk),
                    "source_file": str(path),
                }
            )
            ids.append(self._build_chunk_id(path, company, index))

        self.chroma_service.add_documents(collection_name, documents, metadatas, ids)
        logger.info("Inserted %s chunks into collection %s", len(documents), collection_name)
        return {
            "collection_name": collection_name,
            "inserted_chunks": len(documents),
            "duplicates_skipped": False,
            "skipped_duplicate_chunks": 0,
            "status": "success",
        }

    def _extract_text(self, file_path: Path) -> str:
        try:
            from document_processor import extract_text_from_file

            text = extract_text_from_file(str(file_path))
            if text and text.strip():
                return text.strip()
        except Exception as exc:  # pragma: no cover - fallback for minimal environments
            logger.warning("Document processor extraction unavailable, using plain-text fallback: %s", exc)

        return file_path.read_text(encoding="utf-8", errors="ignore").strip()

    def _split_text_into_chunks(self, text: str) -> List[str]:
        try:
            from document_processor import split_text_into_chunks

            chunks = split_text_into_chunks(text)
            if chunks:
                return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
        except Exception as exc:  # pragma: no cover - fallback for minimal environments
            logger.warning("Document processor chunking unavailable, using basic chunking fallback: %s", exc)

        return self._fallback_split_text(text)

    def _fallback_split_text(self, text: str) -> List[str]:
        if not text.strip():
            return []
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        chunks: List[str] = []
        current: List[str] = []
        current_length = 0
        for paragraph in paragraphs:
            paragraph_length = len(paragraph)
            if current and current_length + paragraph_length > 1200:
                combined = "\n\n".join(current).strip()
                if combined:
                    chunks.append(combined)
                current = [paragraph]
                current_length = paragraph_length
            else:
                current.append(paragraph)
                current_length += paragraph_length

        if current:
            combined = "\n\n".join(current).strip()
            if combined:
                chunks.append(combined)
        return chunks

    @staticmethod
    def _infer_section(chunk: str) -> str:
        if re.search(r"(?i)\b(assets|liabilities|cash flow|income|revenue|equity|balance sheet)\b", chunk):
            return "financials"
        if re.search(r"(?i)\b(risk|uncertainty|material|litigation|regulatory)\b", chunk):
            return "risk"
        return "content"

    @staticmethod
    def _build_chunk_id(file_path: Path, company: str, index: int) -> str:
        payload = f"{file_path.resolve()}::{company}::{index}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest an extraction output into the shared ChromaDB collection")
    parser.add_argument("file_path", help="Path to a PDF or TXT file to ingest")
    parser.add_argument("--company", required=True, help="Company name for metadata")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME, help="Chroma collection name")
    args = parser.parse_args()

    service = ExtractionIngestionService()
    result = service.ingest_file(file_path=args.file_path, company=args.company, collection_name=args.collection)
    print(f"collection name: {result['collection_name']}")
    print(f"number of inserted chunks: {result['inserted_chunks']}")


if __name__ == "__main__":
    main()
