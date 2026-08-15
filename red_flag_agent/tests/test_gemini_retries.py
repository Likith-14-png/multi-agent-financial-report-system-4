import types

import pytest

from app.services.gemini_service import GeminiService
from app.config import GEMINI_MAX_RETRIES


class FakeModels:
    def __init__(self, behavior):
        # behavior: callable that will be invoked on each call
        self._behavior = behavior

    def generate_content(self, *args, **kwargs):
        return self._behavior()


class FakeClient:
    def __init__(self, behavior):
        self.models = FakeModels(behavior)


def test_gemini_retries_success_after_transient_failures(monkeypatch):
    calls = {"count": 0}

    def behavior():
        calls["count"] += 1
        # fail the first two times, succeed afterwards
        if calls["count"] <= 2:
            raise RuntimeError("transient error")
        # return an object with a `text` attribute containing JSON
        resp = types.SimpleNamespace()
        resp.text = '{"ok": true, "attempt": %d}' % calls["count"]
        return resp

    svc = GeminiService(api_key="test-key")
    svc.client = FakeClient(behavior)

    # avoid sleeping during tests
    monkeypatch.setattr("app.services.gemini_service.time.sleep", lambda s: None)

    result = svc.analyze("prompt", [])

    assert isinstance(result, dict)
    assert result.get("ok") is True
    # should have retried twice then succeeded on third call
    assert calls["count"] == 3


def test_gemini_fallback_after_exhausted_retries(monkeypatch):
    calls = {"count": 0}

    def behavior():
        calls["count"] += 1
        raise RuntimeError("permanent failure")

    svc = GeminiService(api_key="test-key")
    svc.client = FakeClient(behavior)

    # stub out sleep to speed test
    monkeypatch.setattr("app.services.gemini_service.time.sleep", lambda s: None)

    # stub offline analyzer to confirm fallback path
    monkeypatch.setattr(svc, "offline_analyzer", types.SimpleNamespace(analyze=lambda p, c: {"fallback": True}))

    result = svc.analyze("prompt", [])

    assert result == {"fallback": True}
    # total attempts should equal GEMINI_MAX_RETRIES + 1
    assert calls["count"] == (GEMINI_MAX_RETRIES + 1)
