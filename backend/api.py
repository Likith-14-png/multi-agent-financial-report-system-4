from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.orchestration.contract import ApiResponse, ComparisonUploadResponse, HealthResponse, RedFlagQueryRequest, ResearchQueryRequest, ResearchQueryResponse, StatusResponse, UploadResponse
from backend.orchestration.session_store import get_session, session_store, update_session
from backend.orchestration.workflow import AnalysisWorkflow

app = FastAPI(title="Financial Analysis API", description="Frontend-facing API for the existing six-agent financial research workflow.", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_ALLOWED_EXTENSIONS = {".pdf", ".txt"}
_ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain", "application/octet-stream", "binary/octet-stream"}
_REPORT_DIR = Path(tempfile.gettempdir()) / "financial-analysis-reports"
_REPORT_DIR.mkdir(parents=True, exist_ok=True)


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
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return text


def _parse_metric_value(value: Any) -> tuple[float | str | None, str | None]:
    if value is None or value in ("", "Not Found", "not found"):
        return None, None
    if isinstance(value, (int, float)):
        return float(value), "unitless"
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "not available", "unavailable", "none", "null"}:
        return None, None
    lower = text.lower()
    unit = "percent" if "%" in lower else "unitless"
    for candidate in ("billion", "million", "thousand"):
        if candidate in lower:
            unit = candidate
            break
    percent_match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?\s*%", text)
    if percent_match:
        try:
            return float(percent_match.group(0).replace("%", "").replace(",", "")), "percent"
        except ValueError:
            pass
    numeric_match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    if numeric_match:
        try:
            return float(numeric_match.group(0).replace(",", "")), unit
        except ValueError:
            pass
    return text, unit


def _normalize_extraction(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"metrics": []}
    if isinstance(raw.get("metrics"), list):
        return raw
    mapping = {"revenue": "Revenue", "operating_income": "Operating Income", "net_income": "Net Income", "total_assets": "Total Assets", "total_liabilities": "Total Liabilities", "cash_flow": "Cash Flow", "eps": "EPS"}
    metrics = []
    for key, label in mapping.items():
        value = raw.get(key)
        if value in (None, "", "Not Found", "not found"):
            continue
        numeric, unit = _parse_metric_value(value)
        metrics.append({"metric": label, "value": numeric if isinstance(numeric, (int, float)) else value, "unit": unit or "unitless", "year": raw.get("report_year") or raw.get("year"), "source": raw.get("source"), "chunk_id": raw.get("chunk_id")})
    return {**raw, "metrics": metrics}


def _api_error_payload(message: str, code: str = "ANALYSIS_FAILED", stage: str = "api") -> dict[str, Any]:
    return {"success": False, "status": "error", "error": {"code": code, "message": message, "stage": stage}}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"detail": str(exc.detail)})
    code = "VALIDATION_ERROR" if exc.status_code == 422 else "BAD_REQUEST" if exc.status_code < 500 else "ANALYSIS_FAILED"
    return JSONResponse(status_code=exc.status_code, content=_api_error_payload(str(exc.detail), code=code))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=_api_error_payload("Invalid request payload", code="VALIDATION_ERROR"))


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=_api_error_payload("Analysis failed", code="ANALYSIS_FAILED"))


def _validate_upload(file: UploadFile) -> str:
    filename = os.path.basename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported document type. PDF is recommended; TXT is supported for compatibility.")
    if file.content_type and file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported document content type.")
    return suffix


async def _save_upload(file: UploadFile) -> str:
    suffix = _validate_upload(file)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Document is empty.")
    if data.startswith(b"MZ"):
        raise HTTPException(status_code=400, detail="Executable files are not supported.")
    fd, path = tempfile.mkstemp(prefix="financial-analysis-", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _cleanup(path: str | None) -> None:
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass


def _require_session(analysis_id: str):
    session = get_session(analysis_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return session


def _session_as_analysis(session: Any) -> dict[str, Any]:
    return {"analysis_id": session.analysis_id, "document_id": session.document_id, "company_name": session.company_name, "report_year": session.report_year, "extraction": session.extraction, "research": session.research, "red_flags": session.red_flags, "comparison": session.comparison, "report": session.report}


def _store_initial_result(result: dict[str, Any]) -> None:
    session_store.create_session(result["analysis_id"], result["document_id"], company_name=result.get("company_name"), report_year=result.get("report_year"))
    update_session(result["analysis_id"], status="completed", current_agent="report", extraction=_normalize_extraction(result.get("extraction") or {}), research=result.get("research") or {}, red_flags=result.get("red_flags") or {}, comparison=result.get("comparison") or {}, report=result.get("report") or {})


@app.get("/health", tags=["Health"], summary="Check API health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    # Existing API tests assert the legacy status value; the service identifier
    # provides the stable frontend health contract without breaking that client.
    return {"status": "ok", "service": "financial-analysis-api"}


@app.post("/analysis/upload", tags=["Analysis"], summary="Upload the first financial document", description="Creates an analysis session and synchronously runs the existing Document, Extraction, Research, Red Flag, and Report agents. Comparison remains pending until a second document is uploaded.", response_model=UploadResponse | ApiResponse, responses={400: {"description": "Invalid or unsupported document"}, 422: {"description": "Validation error"}, 500: {"description": "Sanitized processing failure"}})
async def upload_analysis(file: UploadFile = File(..., description="PDF financial report; TXT is retained for compatibility."), company_name: str | None = Form(None), report_year: str | None = Form(None), question: str | None = Form(None)) -> dict[str, Any]:
    path = await _save_upload(file)
    try:
        analysis_id, document_id = str(uuid4()), str(uuid4())
        result = AnalysisWorkflow(collection_name="financial_research_v1").run_initial_analysis(path, analysis_id=analysis_id, document_id=document_id, company_name=company_name or None, report_year=_coerce_report_year(report_year), question=question or None)
        _store_initial_result(result)
        if company_name is not None or report_year is not None or question is not None:
            legacy = {"success": True, "status": "success", "analysis": {"analysis_id": result["analysis_id"], "document_id": result["document_id"], "company_name": result.get("company_name"), "report_year": _coerce_report_year(result.get("report_year"))}, "extraction": _json_safe(_normalize_extraction(result.get("extraction") or {})), "research": _json_safe(result.get("research") or {}), "red_flags": _json_safe(result.get("red_flags") or {}), "comparison": _json_safe(result.get("comparison") or {}), "report": _json_safe(result.get("report") or {}), "metadata": {"analysis_id": result["analysis_id"], "document_id": result["document_id"], "company_name": result.get("company_name"), "report_year": _coerce_report_year(result.get("report_year"))}, "error": None}
            return ApiResponse.model_validate(legacy).model_dump(mode="json")
        return UploadResponse(analysis_id=result["analysis_id"], document_id=result["document_id"], status="completed", message="Analysis completed successfully").model_dump()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Analysis failed") from exc
    finally:
        _cleanup(path)


@app.get("/analysis/{analysis_id}/status", tags=["Analysis"], summary="Get analysis processing status", response_model=StatusResponse)
async def analysis_status(analysis_id: str) -> dict[str, Any]:
    session = _require_session(analysis_id)
    return StatusResponse(analysis_id=analysis_id, status=session.status, current_agent=session.current_agent, progress=100 if session.status == "completed" else None).model_dump()


@app.get("/analysis/{analysis_id}/extraction", tags=["Extraction"], summary="Get extracted financial metrics")
async def get_extraction(analysis_id: str) -> dict[str, Any]:
    session = _require_session(analysis_id)
    if not session.extraction:
        raise HTTPException(status_code=404, detail="Extraction result not available.")
    return _json_safe(session.extraction)


@app.get("/analysis/{analysis_id}/research", tags=["Research"], summary="Get the research result")
async def get_research(analysis_id: str) -> dict[str, Any]:
    session = _require_session(analysis_id)
    if not session.research:
        raise HTTPException(status_code=404, detail="Research result not available.")
    return {"analysis_id": analysis_id, "status": "completed", **_json_safe(session.research)}


@app.post("/analysis/{analysis_id}/research/query", tags=["Research"], summary="Ask a grounded research question", response_model=ResearchQueryResponse)
async def research_query(analysis_id: str, request: ResearchQueryRequest) -> dict[str, Any]:
    session = _require_session(analysis_id)
    result = AnalysisWorkflow(collection_name="financial_research_v1").run_research_query(_session_as_analysis(session), request.question)
    update_session(analysis_id, research=result, current_agent="research")
    return ResearchQueryResponse(analysis_id=analysis_id, answer=result.get("answer", ""), sources=result.get("sources", []), evidence=result.get("evidence", [])).model_dump()


@app.get("/analysis/{analysis_id}/red-flags", tags=["Red Flags"], summary="Get financial red flags")
async def get_red_flags(analysis_id: str) -> dict[str, Any]:
    session = _require_session(analysis_id)
    if not session.red_flags:
        raise HTTPException(status_code=404, detail="Red flag result not available.")
    return {"analysis_id": analysis_id, **_json_safe(session.red_flags)}


@app.post("/analysis/{analysis_id}/red-flags/query", tags=["Red Flags"], summary="Ask a red-flag evidence question")
async def red_flags_query(analysis_id: str, request: RedFlagQueryRequest) -> dict[str, Any]:
    session = _require_session(analysis_id)
    result = AnalysisWorkflow(collection_name="financial_research_v1").run_red_flags_query(_session_as_analysis(session), request.question)
    return {"analysis_id": analysis_id, **_json_safe(result)}


@app.post("/analysis/{analysis_id}/comparison/upload", tags=["Comparison"], summary="Upload the second company report", response_model=ComparisonUploadResponse)
async def comparison_upload(analysis_id: str, file: UploadFile = File(..., description="Second company's PDF financial report; TXT is supported for compatibility.")) -> dict[str, Any]:
    session = _require_session(analysis_id)
    if not session.extraction:
        raise HTTPException(status_code=400, detail="Initial analysis must complete before comparison.")
    path = await _save_upload(file)
    try:
        workflow = AnalysisWorkflow(collection_name="financial_research_v1")
        result = workflow.run_comparison_upload(analysis_id=analysis_id, original_extraction=session.extraction, report_path=path, document_id=str(uuid4()))
        comparison = result["comparison"]
        report = workflow.generate_comparison_report(analysis_id=analysis_id, original_extraction=session.extraction, research=session.research, red_flags=session.red_flags, comparison=comparison)
        comparison_doc = {"document_id": result["document_id"], "company_name": result.get("company_name"), "report_year": result.get("report_year")}
        session_store.update_session(analysis_id, document_ids=list(dict.fromkeys(session.document_ids + [result["document_id"]])), comparison_documents=session.comparison_documents + [comparison_doc], comparison=comparison, report=report, status="completed", current_agent="report")
        return ComparisonUploadResponse(analysis_id=analysis_id, comparison_id=result["comparison_id"], document_id=result["document_id"], status="completed", companies=comparison.get("companies") or [session.company_name, result.get("company_name")]).model_dump()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Comparison analysis failed") from exc
    finally:
        _cleanup(path)


@app.get("/analysis/{analysis_id}/comparison", tags=["Comparison"], summary="Get the comparison result")
async def get_comparison(analysis_id: str) -> dict[str, Any]:
    session = _require_session(analysis_id)
    if not session.comparison or session.comparison.get("comparison_type") == "pending":
        return {"analysis_id": analysis_id, "status": "pending", "comparison": session.comparison or {}}
    return {"analysis_id": analysis_id, **_json_safe(session.comparison)}


@app.get("/analysis/{analysis_id}/report", tags=["Report"], summary="Get the final structured report")
async def get_report(analysis_id: str) -> dict[str, Any]:
    session = _require_session(analysis_id)
    if not session.report:
        raise HTTPException(status_code=404, detail="Report not available.")
    return {"analysis_id": analysis_id, "status": session.status, "report": _json_safe(session.report)}


@app.get("/analysis/{analysis_id}/report/download", tags=["Report"], summary="Download the final PDF report")
async def download_report(analysis_id: str) -> FileResponse:
    session = _require_session(analysis_id)
    if not session.report:
        raise HTTPException(status_code=404, detail="Report not available.")
    pdf_path = session.report_pdf_path
    if not pdf_path or not Path(pdf_path).is_file():
        pdf_path = str(_REPORT_DIR / f"{analysis_id}.pdf")
        AnalysisWorkflow(collection_name="financial_research_v1").generate_pdf_report(session.report, pdf_path)
        update_session(analysis_id, report_pdf_path=pdf_path)
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"financial-analysis-{analysis_id}.pdf")
