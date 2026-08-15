from __future__ import annotations

import time
from typing import Any, Dict, List

from app.prompts.red_flag_prompt import build_red_flag_prompt
from app.services.gemini_service import GeminiService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RedFlagCrew:
    """Orchestrates LLM-based red-flag analysis."""

    def __init__(self, gemini_service: GeminiService | None = None) -> None:
        self.gemini_service = gemini_service

    def analyze(self, company_name: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = time.time()
        if not self.gemini_service:
            raise ValueError("Gemini service is required")

        logger.info("Starting analysis for company %s", company_name)

        try:
            prompt = build_red_flag_prompt()
            result = self.gemini_service.analyze(prompt, context_chunks)
            parsed = self._parse_result(result)
        except Exception as exc:
            logger.exception("Analysis failed")
            raise RuntimeError(f"Analysis failed: {exc}") from exc

        execution_time = round(time.time() - start_time, 3)
        parsed.setdefault("execution_time", execution_time)
        parsed.setdefault("model_used", "gemini")
        return parsed

    def _parse_result(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, str):
            try:
                return self._decode_json_string(result)
            except Exception as exc:
                raise ValueError("Invalid JSON from CrewAI") from exc
        if isinstance(result, dict):
            return result
        try:
            return self._decode_json_string(str(result))
        except Exception as exc:
            raise ValueError("Invalid JSON from CrewAI") from exc

    def _decode_json_string(self, value: str) -> Dict[str, Any]:
        import json

        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON returned by CrewAI") from exc
