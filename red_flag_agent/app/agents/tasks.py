from __future__ import annotations

from typing import Any, Dict, List

try:
    from crewai import Task as CrewAITask
except Exception:  # pragma: no cover - fallback for minimal environments
    class CrewAITask:  # type: ignore[override]
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

from app.prompts.red_flag_prompt import build_red_flag_prompt


class RedFlagTaskFactory:
    """Create CrewAI tasks for red flag analysis."""

    @staticmethod
    def create(task_id: str, context_chunks: List[Dict[str, Any]], company_name: str) -> CrewAITask:
        prompt = build_red_flag_prompt()
        description = (
            f"Analyze the retrieved report excerpts for {company_name}. "
            f"Use only the provided context chunks and return a structured JSON response.\n\n"
            f"{prompt}"
        )
        return CrewAITask(
            description=description,
            expected_output="JSON object with overall_risk, total_flags, flags, execution_time, and model_used",
            agent=None,
            id=task_id,
        )
