from app.models.response import RedFlagAnalysisResponse, RedFlag


def test_response_model_schema():
    payload = {
        "overall_risk": "High",
        "total_flags": 1,
        "flags": [
            {
                "category": "Debt",
                "severity": "High",
                "title": "Debt increase",
                "description": "Debt increased",
                "reason": "Borrowings grew",
                "evidence": "Borrowings rose",
                "page": 10,
                "recommendation": "Monitor leverage",
                "confidence": 0.93,
            }
        ],
        "execution_time": 0.1,
        "model_used": "gemini",
    }
    response = RedFlagAnalysisResponse(**payload)
    assert response.total_flags == 1
    assert isinstance(response.flags[0], RedFlag)
