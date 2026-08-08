from __future__ import annotations

from typing import Any

try:
    from crewai import Agent as CrewAIAgent
except Exception:  # pragma: no cover - fallback for minimal environments
    class CrewAIAgent:  # type: ignore[override]
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs


class RedFlagAgentFactory:
    """Create the single CrewAI agent for red flag analysis."""

    @staticmethod
    def create() -> CrewAIAgent:
        return CrewAIAgent(
            role="Senior Financial Risk Analyst",
            goal="Analyze retrieved document chunks and detect financial risks with evidence.",
            backstory=(
                "You have 20+ years of experience in equity research and financial statement analysis. "
                "You never invent facts and you only use retrieved document context."
            ),
            verbose=False,
            allow_delegation=False,
            tools=[],
        )
