from app.agents.crew import RedFlagCrew


def test_crew_requires_gemini_service():
    try:
        RedFlagCrew(gemini_service=None).analyze("Acme", [])
    except ValueError as exc:
        assert "Gemini service is required" in str(exc)
