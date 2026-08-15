from __future__ import annotations

from typing import List

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - fallback for minimal environments
    genai = None
    types = None

from app.config import EMBEDDING_MODEL, GEMINI_API_KEY
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generate embeddings for report chunks using Gemini embeddings."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing")
        self.model_name = model_name or EMBEDDING_MODEL
        self.client = None
        if genai is None or types is None:
            logger.warning("google-genai package is not installed; embedding generation is unavailable")
            return
        self.client = genai.Client(api_key=self.api_key)

    def embed_text(self, text: str) -> List[float]:
        if self.client is None:
            raise RuntimeError("google-genai package is not installed")
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        values = getattr(response, "embeddings", None)
        if not values:
            raise ValueError("Embedding generation returned no values")
        return values[0].values

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(text) for text in texts]
