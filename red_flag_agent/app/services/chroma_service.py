from __future__ import annotations

import os
from typing import Any, List, Dict

import chromadb
from chromadb.config import Settings

from app.config import CHROMA_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ChromaService:
    """Local ChromaDB persistence and retrieval service."""

    def __init__(self, persist_directory: str | None = None) -> None:
        self.persist_directory = persist_directory or CHROMA_DIR
        os.makedirs(self.persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_directory, settings=Settings(anonymized_telemetry=False))

    def get_collection(self, name: str):
        return self.client.get_or_create_collection(name=name)

    def add_documents(self, collection_name: str, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
        collection = self.get_collection(collection_name)
        collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def query(self, collection_name: str, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        collection = self.get_collection(collection_name)
        results = collection.query(query_texts=[query_text], n_results=top_k)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        output: List[Dict[str, Any]] = []
        for idx, doc in enumerate(documents):
            output.append(
                {
                    "document": doc,
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    "distance": distances[idx] if idx < len(distances) else None,
                }
            )
        return output

    def collection_exists(self, collection_name: str) -> bool:
        try:
            self.client.get_collection(name=collection_name)
            return True
        except Exception:
            return False
