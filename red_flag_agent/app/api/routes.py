from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.crew import RedFlagCrew
from app.models.request import RedFlagAnalyzeRequest
from app.models.response import RedFlagAnalysisResponse
from app.services.gemini_service import GeminiService
from app.services.retrieval_service import RetrievalService
from app.utils.logger import get_logger
from app.utils import metrics as metrics
from fastapi import Response

logger = get_logger(__name__)
router = APIRouter()


def get_gemini_service() -> GeminiService | None:
    try:
        return GeminiService()
    except (ValueError, RuntimeError):
        return None


def get_retrieval_service() -> RetrievalService:
    return RetrievalService()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    return metrics.metrics_response()


@router.post("/redflag/analyze", response_model=RedFlagAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_red_flags(
    payload: RedFlagAnalyzeRequest,
    gemini_service: GeminiService | None = Depends(get_gemini_service),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> RedFlagAnalysisResponse:
    start_time = time.time()
    metrics.REQUESTS_TOTAL.inc()
    if not payload.company.strip() or not payload.collection.strip():
        raise HTTPException(status_code=422, detail="company and collection must be non-empty")

    if gemini_service is None:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing")

    logger.info("Incoming request for company=%s collection=%s", payload.company, payload.collection)

    try:
        retrieved_chunks = retrieval_service.retrieve(payload.collection, payload.company)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Retrieval failed")
        raise HTTPException(status_code=500, detail="Retrieval service failed") from exc

    if not retrieved_chunks:
        raise HTTPException(status_code=404, detail="No chunks retrieved")

    try:
        crew = RedFlagCrew(gemini_service=gemini_service)
        result = crew.analyze(payload.company, retrieved_chunks)
    except Exception as exc:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail="Analysis failed") from exc

    execution_time = round(time.time() - start_time, 3)
    response = RedFlagAnalysisResponse(
        overall_risk=result.get("overall_risk", "Low"),
        total_flags=int(result.get("total_flags", 0)),
        flags=result.get("flags", []),
        execution_time=execution_time,
        model_used=result.get("model_used", "gemini"),
    )
    return response
