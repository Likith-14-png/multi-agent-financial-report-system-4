from unittest.mock import MagicMock

from google.genai import errors as genai_errors

from app.services.gemini_service import GeminiService


def test_gemini_service_allows_missing_api_key_and_falls_back(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("app.services.gemini_service.GEMINI_API_KEY", "")
    service = GeminiService(api_key="")
    result = service.analyze("Analyze", [{"document": "Revenue fell", "metadata": {"page": 1}}])

    assert result["model_used"] == "offline-fallback"
    assert result["overall_risk"] in {"High", "Medium", "Low"}


def test_analyze_uses_supported_generate_content_config():
    service = GeminiService(api_key="test-key")
    service.client = MagicMock()
    service.client.models.generate_content.return_value = MagicMock(text='{"risk":"high"}')

    result = service.analyze("Analyze", [{"document": "Revenue fell", "metadata": {"page": 1}}])

    assert result == {"risk": "high"}
    config = service.client.models.generate_content.call_args.kwargs["config"]
    assert config.temperature == 0.1
    assert config.response_mime_type == "application/json"
    assert not hasattr(config, "timeout")


def test_quota_exceeded_falls_back():
    service = GeminiService(api_key="test-key")
    service.client = MagicMock()
    service.client.models.generate_content.side_effect = genai_errors.ClientError(
        code=429,
        response_json={"error": {"message": "Quota exceeded"}},
    )

    result = service.analyze("Analyze", [{"document": "Borrowings rose", "metadata": {"page": 3}}])

    assert result["model_used"] == "offline-fallback"
    assert result["total_flags"] >= 1


def test_invalid_api_key_falls_back():
    service = GeminiService(api_key="bad-key")
    service.client = MagicMock()
    service.client.models.generate_content.side_effect = genai_errors.ClientError(
        code=401,
        response_json={"error": {"message": "Unauthorized"}},
    )

    result = service.analyze("Analyze", [{"document": "Margins weakened", "metadata": {"page": 8}}])

    assert result["model_used"] == "offline-fallback"


def test_missing_model_falls_back_without_retries(monkeypatch):
    service = GeminiService(api_key="test-key", model_name="retired-model")
    service.client = MagicMock()
    service.client.models.generate_content.side_effect = genai_errors.ClientError(
        code=404,
        response_json={"error": {"message": "model retired-model is no longer available"}},
    )
    monkeypatch.setattr("app.services.gemini_service.time.sleep", lambda _seconds: (_ for _ in ()).throw(AssertionError("permanent model errors must not sleep")))

    result = service.analyze("Analyze", [{"document": "Revenue fell", "metadata": {"page": 1}}])

    assert result["model_used"] == "offline-fallback"
    assert service.client.models.generate_content.call_count == 1


def test_network_failure_falls_back():
    service = GeminiService(api_key="test-key")
    service.client = MagicMock()
    service.client.models.generate_content.side_effect = TimeoutError("timed out")

    result = service.analyze("Analyze", [{"document": "Cash flow fell", "metadata": {"page": 10}}])

    assert result["model_used"] == "offline-fallback"
