from __future__ import annotations

from typing import List, Dict, Any

from app.config import DEFAULT_TOP_K
from app.services.chroma_service import ChromaService
from app.utils.logger import get_logger
from app.utils import metrics as metrics

logger = get_logger(__name__)


class RetrievalService:
    """Retrieve relevant report chunks from ChromaDB."""

    def __init__(self, chroma_service: ChromaService | None = None) -> None:
        self.chroma_service = chroma_service or ChromaService()

    def retrieve(self, collection_name: str, company_name: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        metrics.RETRIEVAL_REQUESTS_TOTAL.inc()
        if not collection_name:
            raise ValueError("Collection name is required")
        if not company_name:
            raise ValueError("Company name is required")
        if not self.chroma_service.collection_exists(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")

        query_text = f"{company_name} financial report risks financial statements performance"
        results = self.chroma_service.query(collection_name=collection_name, query_text=query_text, top_k=top_k or DEFAULT_TOP_K)
        logger.info("Retrieved %s chunks for company %s from collection %s", len(results), company_name, collection_name)
        return results
