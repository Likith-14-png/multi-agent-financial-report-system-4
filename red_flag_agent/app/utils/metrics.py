try:
    from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
    from fastapi import Response

    # Counters
    REQUESTS_TOTAL = Counter("redflag_requests_total", "Total /redflag/analyze requests")
    GEMINI_REQUESTS_TOTAL = Counter("gemini_requests_total", "Total Gemini API requests")
    GEMINI_FALLBACK_TOTAL = Counter(
        "gemini_fallback_total", "Total Gemini fallback (offline analyzer) events"
    )
    GEMINI_RETRIES_TOTAL = Counter("gemini_retries_total", "Total Gemini retry attempts")
    RETRIEVAL_REQUESTS_TOTAL = Counter("retrieval_requests_total", "Total retrieval service calls")
    INGESTION_REQUESTS_TOTAL = Counter("ingestion_requests_total", "Total ingestion calls")


    def metrics_response() -> Response:
        """Return a FastAPI Response with Prometheus metrics."""
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

except Exception:  # pragma: no cover - provide safe no-op fallbacks when prometheus_client isn't installed
    class _NoopCounter:
        def inc(self, amount: int = 1) -> None:  # type: ignore[override]
            return None


    REQUESTS_TOTAL = _NoopCounter()
    GEMINI_REQUESTS_TOTAL = _NoopCounter()
    GEMINI_FALLBACK_TOTAL = _NoopCounter()
    GEMINI_RETRIES_TOTAL = _NoopCounter()
    RETRIEVAL_REQUESTS_TOTAL = _NoopCounter()
    INGESTION_REQUESTS_TOTAL = _NoopCounter()


    def metrics_response():
        # Return a simple text response indicating metrics are unavailable
        from fastapi import Response

        return Response(content=b"", media_type="text/plain")
