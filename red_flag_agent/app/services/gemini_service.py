from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
except Exception:  # pragma: no cover - fallback for minimal environments
    genai = None
    types = None
    genai_errors = None

from app.config import (
    GEMINI_API_KEY,
    MODEL_NAME,
    REQUEST_TIMEOUT_SECONDS,
    GEMINI_MAX_RETRIES,
    GEMINI_BACKOFF_BASE,
    GEMINI_BACKOFF_MAX,
)
import time
import random
from app.services.offline_analyzer import OfflineAnalyzer
from app.utils.logger import get_logger
from app.utils import metrics as metrics

logger = get_logger(__name__)


class GeminiService:
    """Thin wrapper around Gemini for reasoning-only analysis."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", GEMINI_API_KEY or "")
        self.model_name = model_name or MODEL_NAME
        self.client = None
        self.offline_analyzer = OfflineAnalyzer()
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is missing; Gemini analysis will use the offline fallback")
            return
        if genai is None or types is None:
            logger.warning("google-genai package is not installed; Gemini analysis will use the offline fallback")
            return
        self.client = genai.Client(api_key=self.api_key)

    def analyze(self, prompt: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is missing; using offline fallback analyzer")
            return self.offline_analyzer.analyze(prompt, context_chunks)

        context_text = "\n\n".join(
            [f"Chunk {index + 1}: {chunk.get('document', '')}\nMetadata: {json.dumps(chunk.get('metadata', {}), ensure_ascii=False)}"
             for index, chunk in enumerate(context_chunks)]
        )
        full_prompt = f"{prompt}\n\nContext:\n{context_text}"
        logger.info("Sending prompt to Gemini with %s context chunks", len(context_chunks))

        # Retry loop: exponential backoff with jitter. Configurable via `app.config`.
        max_retries = GEMINI_MAX_RETRIES
        backoff_base = GEMINI_BACKOFF_BASE
        backoff_max = GEMINI_BACKOFF_MAX

        last_exc: Optional[Exception] = None
        for attempt in range(0, max_retries + 1):
            try:
                if self.client is None:
                    raise RuntimeError("google-genai package is not installed")
                metrics.GEMINI_REQUESTS_TOTAL.inc()
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                text = getattr(response, "text", "") or ""
                if not text:
                    raise ValueError("Gemini returned empty response")

                # Try tolerant JSON extraction from the returned text
                parsed = self._parse_json_text(text)
                if parsed is None:
                    raise ValueError("Invalid JSON returned by Gemini")
                # Success
                return parsed
            except Exception as exc:
                last_exc = exc
                if self._is_permanent_model_error(exc):
                    logger.error("Gemini model '%s' is unavailable; using offline fallback without retrying: %s", self.model_name, exc)
                    metrics.GEMINI_FALLBACK_TOTAL.inc()
                    return self.offline_analyzer.analyze(prompt, context_chunks)
                # If we have remaining attempts, sleep with exponential backoff + jitter then retry
                if attempt < max_retries:
                    metrics.GEMINI_RETRIES_TOTAL.inc()
                    # exponential backoff
                    wait = min(backoff_base * (2 ** attempt), backoff_max)
                    # add jitter up to 50% of wait
                    jitter = random.uniform(0, wait * 0.5)
                    sleep_for = wait + jitter
                    logger.warning(
                        "Gemini attempt %s/%s failed (%s), retrying in %.2fs",
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                # no more retries, fall back
                logger.warning("Gemini analysis failed after %s attempts; falling back: %s", attempt + 1, exc)
                metrics.GEMINI_FALLBACK_TOTAL.inc()
                return self.offline_analyzer.analyze(prompt, context_chunks)

    @staticmethod
    def _is_permanent_model_error(exc: Exception) -> bool:
        code = getattr(exc, "code", None)
        if code == 404:
            return True
        text = str(exc).lower()
        return "model" in text and ("not found" in text or "no longer available" in text)

    def _parse_json_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Attempt to extract a JSON object from `text` robustly.

        Strategies:
        - Direct json.loads
        - Extract content inside triple-backtick code fences
        - Find first balanced JSON object/array using brace matching
        - Return None if parsing fails
        """
        text = text.strip()
        # 1) Direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2) Extract code fence content ```...``` if present
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # 3) Find first balanced JSON object/array by scanning for { or [ and matching
        for start_char in ("{", "["):
            start_idx = text.find(start_char)
            if start_idx == -1:
                continue
            end_idx = self._find_matching_brace(text, start_idx)
            if end_idx is None:
                continue
            candidate = text[start_idx : end_idx + 1]
            try:
                return json.loads(candidate)
            except Exception:
                continue

        return None

    def _find_matching_brace(self, text: str, start_idx: int) -> Optional[int]:
        """Return index of matching closing brace/bracket for the char at start_idx."""
        pairs = {"{": "}", "[": "]"}
        open_ch = text[start_idx]
        if open_ch not in pairs:
            return None
        close_ch = pairs[open_ch]
        stack = []
        for idx in range(start_idx, len(text)):
            ch = text[idx]
            if ch == open_ch:
                stack.append(ch)
            elif ch == close_ch:
                stack.pop()
                if not stack:
                    return idx
        return None
