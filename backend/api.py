import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.orchestration.contract import ApiResponse
from backend.orchestration.workflow import AnalysisWorkflow

app = FastAPI(title="Financial Research API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump(mode="json"))
        except TypeError:
            pass
    if hasattr(value, "to_dict"):
        try:
            return _json_safe(value.to_dict())
        except TypeError:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    return str(value)


def _coerce_report_year(value: Any) -> int | str | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _parse_metric_value(value: Any) -> tuple[float | str | None, str | None]:
    if value is None or value in ("", "Not Found", "not found"):
        return None, None
    if isinstance(value, (int, float)):
        return float(value), "unitless"
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "not available", "unavailable", "none", "null"}:
        return None, None

    lower = text.lower()
    unit = "unitless"
    if "billion" in lower:
        unit = "billion"
    elif "million" in lower:
        unit = "million"
    elif "thousand" in lower:
        unit = "thousand"

    monetary_pattern = re.compile(r"(?:[$€£]\s*)?[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:million|billion|thousand|k|m|bn)", re.I)
    monetary_match = None
    for match in monetary_pattern.finditer(text):
        candidate = match.group(0)
        prev_char = text[match.start() - 1] if match.start() > 0 else ""
        if prev_char in {".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            continue
        monetary_match = match
        if "billion" in candidate.lower() or "million" in candidate.lower() or "thousand" in candidate.lower():
            break

    if monetary_match:
        candidate = monetary_match.group(0)
        cleaned = candidate.replace("$", "").replace("€", "").replace("£", "").replace(",", "").replace("%", "")
        cleaned = re.sub(r"\s+(?:million|billion|thousand|k|m|bn)$", "", cleaned, flags=re.I)
        try:
            return float(cleaned), unit
        except ValueError:
            pass

    percent_match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?\s*%", text)
    if percent_match:
        cleaned = percent_match.group(0).replace("%", "").replace(",", "")
        try:
            return float(cleaned), "percent"
        except ValueError:
            pass

    cleaned = text.replace("$", "").replace("€", "").replace("£", "").replace(",", "").replace("%", "")
    cleaned = cleaned.strip()
    try:
        return float(cleaned), unit
    except ValueError:
        try:
            return float(cleaned.split()[0]), unit
        except (ValueError, IndexError):
            return text, unit


def _normalize_extraction(raw_extraction: Any) -> dict[str, Any]:
    if not isinstance(raw_extraction, dict):
        return {"metrics": []}

    metrics_list = raw_extraction.get("metrics")
    if isinstance(metrics_list, list):
        metrics = metrics_list
    else:
        metric_map = {
            "revenue": "Revenue",
            "operating_income": "Operating Income",
            "net_income": "Net Income",
            "total_assets": "Total Assets",
            "total_liabilities": "Total Liabilities",
            "cash_flow": "Cash Flow",
            "eps": "EPS",
        }
        metrics = []
        for key, label in metric_map.items():
            value = raw_extraction.get(key)
            if value in (None, "", "Not Found", "not found"):
                continue
            numeric_value, unit = _parse_metric_value(value)
            metrics.append({
                "metric": label,
                "value": numeric_value if isinstance(numeric_value, (int, float)) else value,
                "unit": unit or "unitless",
                "year": raw_extraction.get("report_year") or raw_extraction.get("year"),
                "source": raw_extraction.get("source"),
                "chunk_id": raw_extraction.get("chunk_id"),
            })

    return {
        "metrics": metrics,
        "company_name": raw_extraction.get("company_name"),
        "report_year": _coerce_report_year(raw_extraction.get("report_year") or raw_extraction.get("year")),
        "source": raw_extraction.get("source"),
        "chunk_id": raw_extraction.get("chunk_id"),
    }


def _api_error_payload(message: str, code: str = "ANALYSIS_FAILED", stage: str = "api") -> dict[str, Any]:
    return {
        "success": False,
        "status": "error",
        "analysis": {
            "analysis_id": None,
            "document_id": None,
            "company_name": None,
            "report_year": None,
        },
        "extraction": {},
        "research": {},
        "red_flags": {},
        "comparison": {},
        "report": {},
        "metadata": {},
        "error": {"code": code, "message": message, "stage": stage},
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code = "BAD_REQUEST"
    if exc.status_code == 422:
        code = "VALIDATION_ERROR"
    elif exc.status_code >= 500:
        code = "ANALYSIS_FAILED"
    payload = _api_error_payload(str(exc.detail) if isinstance(exc.detail, str) else "Request failed", code=code, stage="api")
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    payload = _api_error_payload("Invalid request payload", code="VALIDATION_ERROR", stage="api")
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    payload = _api_error_payload("Analysis failed", code="ANALYSIS_FAILED", stage="api")
    if isinstance(exc, ValueError):
        payload["error"]["message"] = str(exc)
    return JSONResponse(status_code=500, content=payload)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analysis/upload", response_model=ApiResponse)
async def upload_analysis(
    file: UploadFile = File(...),
    company_name: str = Form(...),
    report_year: str = Form(...),
    question: str = Form(...),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Document is required")

    temp_dir = "./tmp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    temp_path = os.path.join(temp_dir, safe_name)
    contents = await file.read()
    with open(temp_path, "wb") as fh:
        fh.write(contents)

    workflow = AnalysisWorkflow(collection_name="financial_research_v1")
    try:
        result = workflow.run_analysis(
            report_path=temp_path,
            company_name=company_name,
            report_year=report_year,
            question=question,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    analysis_payload = result.get("analysis") or {}
    if isinstance(analysis_payload, dict):
        metadata = analysis_payload.get("metadata") or result.get("metadata") or {}
    else:
        metadata = result.get("metadata") or {}

    metadata_payload = _json_safe(metadata)
    analysis_id = result.get("analysis_id") or (analysis_payload.get("metadata") or {}).get("analysis_id") or (analysis_payload.get("analysis_id") if isinstance(analysis_payload, dict) else None)
    document_id = result.get("document_id") or (analysis_payload.get("metadata") or {}).get("document_id") or (analysis_payload.get("document_id") if isinstance(analysis_payload, dict) else None)
    company_name = result.get("company_name") or (analysis_payload.get("metadata") or {}).get("company_name") or (analysis_payload.get("company_name") if isinstance(analysis_payload, dict) else None)
    report_year = _coerce_report_year(result.get("report_year") or (analysis_payload.get("metadata") or {}).get("report_year") or (analysis_payload.get("report_year") if isinstance(analysis_payload, dict) else None))

    research_payload = result.get("research") or {}
    if isinstance(research_payload, dict):
        evidence_items = research_payload.get("evidence") or research_payload.get("sources") or research_payload.get("findings") or []
        deduped_chunks = []
        seen_chunks = set()
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            chunk_id = item.get("chunk_id")
            if not chunk_id:
                continue
            cid = str(chunk_id)
            if cid not in seen_chunks:
                seen_chunks.add(cid)
                deduped_chunks.append(cid)
        research_out = {
            "summary": research_payload.get("answer") or research_payload.get("summary") or "",
            "findings": research_payload.get("findings") or (research_payload.get("sources") or research_payload.get("evidence") or []),
            "evidence": research_payload.get("evidence") or research_payload.get("sources") or [],
            "source_chunks": deduped_chunks,
        }
    else:
        research_out = {"summary": "", "findings": [], "evidence": [], "source_chunks": []}

    red_flags_payload = result.get("red_flags") or {}
    if isinstance(red_flags_payload, dict):
        red_flags_out = {
            "overall_risk": red_flags_payload.get("overall_risk") or "Low",
            "total_flags": red_flags_payload.get("total_flags") or 0,
            "model_used": red_flags_payload.get("model_used") or "offline-fallback",
            "flags": red_flags_payload.get("flags") or [],
        }
    else:
        red_flags_out = {"overall_risk": "Low", "total_flags": 0, "model_used": "offline-fallback", "flags": []}

    comparison_payload = result.get("comparison") or {}
    if isinstance(comparison_payload, dict) and "records" in comparison_payload:
        comparison_out = comparison_payload
    elif isinstance(comparison_payload, list):
        comparison_out = {"records": comparison_payload}
    else:
        comparison_out = {"records": []}

    report_payload = result.get("report") or {}

    extraction_out = _normalize_extraction(result.get("extraction") or {})

    payload = {
        "success": True,
        "status": "success",
        "analysis": {
            "analysis_id": analysis_id,
            "document_id": document_id,
            "company_name": company_name,
            "report_year": report_year,
        },
        "extraction": _json_safe(extraction_out),
        "research": _json_safe(research_out),
        "red_flags": _json_safe(red_flags_out),
        "comparison": _json_safe(comparison_out),
        "report": _json_safe(report_payload),
        "metadata": {
            **_json_safe(metadata_payload),
            "analysis_id": analysis_id,
            "document_id": document_id,
            "company_name": company_name,
            "report_year": report_year,
        },
        "analysis_id": analysis_id,
        "document_id": document_id,
        "company_name": company_name,
        "report_year": report_year,
        "error": None,
    }
    return ApiResponse.model_validate(payload)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.api:app", host="127.0.0.1", port=8000, reload=True)

