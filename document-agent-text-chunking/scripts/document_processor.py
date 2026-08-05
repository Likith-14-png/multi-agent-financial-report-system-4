"""Legacy function API backed by the reusable DocumentAgent engine."""

from pathlib import Path
from typing import Any, Dict, List

from document_agent import DocumentAgent, DocumentAgentConfig


def _text_agent() -> DocumentAgent:
    return DocumentAgent(DocumentAgentConfig(collection_name="financial_research"))


def extract_text_from_file(file_path: str) -> str:
    """Extract clean text from a supported PDF or TXT file."""
    text, _ = _text_agent().extract_text(Path(file_path))
    return text


def split_text_into_chunks(text: str, chunk_size: int = 800, chunk_overlap: int = 125) -> List[str]:
    """Split text semantically while preserving the historical function name."""
    agent = _text_agent()
    agent.config.chunk_size = chunk_size
    agent.config.chunk_overlap = chunk_overlap
    return agent.chunk_text(text)


def document_agent(file_path: str) -> Dict[str, Any]:
    """Ingest one document using the production engine."""
    agent = _text_agent()
    result = agent.ingest_document(file_path)
    return {
        "document": result["document"],
        "chunks_count": result["chunks"],
        "vector_db": "ChromaDB",
        "collection": result["collection"],
        "status": "Vectorized and Stored" if result["status"] == "success" else result["status"],
        "analysis_id": result["analysis_id"],
        "duplicates_skipped": result["duplicates_skipped"],
        "error": result["error"],
    }