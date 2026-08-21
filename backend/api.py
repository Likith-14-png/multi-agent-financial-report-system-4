import os
os.environ["MPLBACKEND"] = "Agg"
try:
    import matplotlib
    matplotlib.use("Agg")
except ImportError:
    pass
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.orchestration.contract import (
    AnalysisStatusResponse,
    AnalysisUploadResponse,
    ApiResponse,
    ComparisonResponse,
    ComparisonUploadResponse,
    ExtractionResponse,
    HealthResponse,
    QueryRequest,
    RedFlagsQueryResponse,
    RedFlagsResponse,
    ReportResponse,
    ResearchQueryResponse,
    ResearchResponse,
)
from backend.orchestration.session_store import session_store
from backend.orchestration.workflow import AnalysisWorkflow

app = FastAPI(
    title="Multi-Agent Financial Research System API",
    description=(
        "Enterprise Multi-Agent Financial Research API orchestrating Document Ingestion, "
        "Metric Extraction, Research Retrieval, Red Flag Risk Analysis, Peer Comparison, and Executive Reporting."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Health", "description": "API health check and service readiness"},
        {"name": "Analysis", "description": "Document upload, analysis session creation and status monitoring"},
        {"name": "Extraction", "description": "Structured financial metric extraction retrieval"},
        {"name": "Research", "description": "Grounded research findings and contextual question answering"},
        {"name": "Red Flags", "description": "Financial risk analysis and risk query evaluation"},
        {"name": "Comparison", "description": "Cross-company financial comparison and benchmark analysis"},
        {"name": "Report", "description": "Executive report synthesis and publication PDF download"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


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
            "gross_profit": "Gross Profit",
            "operating_income": "Operating Income",
            "pretax_income": "Pre-tax Income",
            "net_income": "Net Income",
            "total_assets": "Total Assets",
            "total_liabilities": "Total Liabilities",
            "total_equity": "Total Equity",
            "cash_flow": "Cash Flow",
            "operating_cash_flow": "Operating Cash Flow",
            "free_cash_flow": "Free Cash Flow",
            "rd_expense": "R&D Expense",
            "total_debt": "Total Debt",
            "eps": "EPS",
        }
        traceability = raw_extraction.get("traceability") or {}
        metrics = []
        for key, label in metric_map.items():
            value = raw_extraction.get(key)
            if value in (None, "", "Not Found", "not found"):
                continue
            numeric_value, unit = _parse_metric_value(value)
            t_record = traceability.get(key) if isinstance(traceability, dict) else {}
            chunk_id = t_record.get("source_chunk_id") or raw_extraction.get("chunk_id")
            source = t_record.get("source_file") or raw_extraction.get("source")
            metrics.append({
                "metric": label,
                "value": numeric_value if isinstance(numeric_value, (int, float)) else value,
                "unit": unit or "unitless",
                "year": raw_extraction.get("report_year") or raw_extraction.get("year"),
                "source": source,
                "chunk_id": chunk_id,
            })

    return {
        "metrics": metrics,
        "company_name": raw_extraction.get("company_name"),
        "report_year": _coerce_report_year(raw_extraction.get("report_year") or raw_extraction.get("year")),
        "source": raw_extraction.get("source"),
        "chunk_id": raw_extraction.get("chunk_id"),
        "income_statement": raw_extraction.get("income_statement"),
        "balance_sheet": raw_extraction.get("balance_sheet"),
        "cash_flow_statement": raw_extraction.get("cash_flow_statement"),
        "segment_metrics": raw_extraction.get("segment_metrics"),
        "accounting_information": raw_extraction.get("accounting_information"),
        "risk_related_metrics": raw_extraction.get("risk_related_metrics"),
        "yearly_metrics": raw_extraction.get("yearly_metrics"),
        "detailed_metrics": raw_extraction.get("detailed_metrics"),
        "traceability": raw_extraction.get("traceability"),
    }


def _api_error_payload(message: str, code: str = "ANALYSIS_FAILED", stage: str = "api") -> dict[str, Any]:
    return {
        "detail": message,
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
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 422:
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
        payload["detail"] = str(exc)
    return JSONResponse(status_code=500, content=payload)


# ------------------------------------------------------------------ #
# 1. Health Endpoint
# ------------------------------------------------------------------ #

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description="Returns the health status and service identifier of the Financial Research API.",
)
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "financial-analysis-api"}


# ------------------------------------------------------------------ #
# 2. Analysis Upload & Status Endpoints
# ------------------------------------------------------------------ #

@app.post(
    "/analysis/upload",
    response_model=AnalysisUploadResponse,
    tags=["Analysis"],
    summary="Upload financial document and store chunks in ChromaDB",
    description=(
        "Upload a single financial report (PDF or TXT). Initiates an analysis session, processes "
        "document chunking and ingestion into ChromaDB using Document Agent, and returns the stored "
        "chunks and metadata details."
    ),
    status_code=status.HTTP_200_OK,
)
async def upload_analysis(
    file: UploadFile = File(..., description="Financial report file (PDF or TXT)"),
    company_name: Optional[str] = Form(None, description="Optional company name override"),
    report_year: Optional[str] = Form(None, description="Optional report fiscal year override"),
    question: Optional[str] = Form(None, description="Optional specific research question"),
) -> dict[str, Any]:
    if not file or not file.filename or not file.filename.strip():
        raise HTTPException(status_code=400, detail="Document is required")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and TXT documents are supported.")

    contents = await file.read()
    if not contents or len(contents.strip()) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    temp_dir = "./tmp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    temp_path = os.path.join(temp_dir, safe_name)
    with open(temp_path, "wb") as fh:
        fh.write(contents)

    workflow = AnalysisWorkflow(collection_name="financial_research_v1")
    try:
        doc_result = workflow.run_document_ingestion(
            report_path=temp_path,
            company_name=company_name,
            report_year=report_year,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {exc}") from exc

    analysis_id = doc_result["analysis_id"]
    document_id = doc_result["document_id"]
    effective_company = doc_result["company_name"]
    effective_year = _coerce_report_year(doc_result["report_year"])

    # Store initial state in session_store
    session_store.create_session(
        analysis_id=analysis_id,
        document_id=document_id,
        company_name=effective_company,
        report_year=effective_year,
        file_path=temp_path,
        file_name=safe_name,
        status="completed",
        current_agent=None,
        progress=100,
        extraction_result={},
        research_result={},
        red_flags_result={},
        comparison_result=None,
        report_result={},
    )

    return _json_safe(doc_result)


@app.get(
    "/analysis/{analysis_id}/status",
    response_model=AnalysisStatusResponse,
    tags=["Analysis"],
    summary="Get analysis pipeline processing status",
    description="Check the current lifecycle stage, status, active agent, and progress percentage for a session.",
)
async def get_analysis_status(analysis_id: str) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {
        "analysis_id": session.analysis_id,
        "status": session.status,
        "current_agent": session.current_agent,
        "progress": session.progress,
    }


# ------------------------------------------------------------------ #
# 3. Extraction Endpoint
# ------------------------------------------------------------------ #

@app.get(
    "/analysis/{analysis_id}/extraction",
    response_model=ExtractionResponse,
    tags=["Extraction"],
    summary="Retrieve extracted financial metrics",
    description="Returns the actual extracted financial metrics produced by the Extraction Agent.",
)
async def get_extraction(analysis_id: str) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if not session.extraction_result:
        workflow = AnalysisWorkflow(collection_name="financial_research_v1")
        try:
            ext_result = workflow.run_extraction(
                analysis_id=session.analysis_id,
                company_name=session.company_name,
                document_id=session.document_id,
            )
            session_store.update_session(analysis_id=analysis_id, extraction_result=ext_result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc
    else:
        ext_result = session.extraction_result

    res = dict(ext_result)
    res.setdefault("analysis_id", session.analysis_id)
    res.setdefault("company_name", session.company_name)
    res.setdefault("report_year", session.report_year)
    return _json_safe(res)


# ------------------------------------------------------------------ #
# 4. Research Endpoints
# ------------------------------------------------------------------ #

@app.get(
    "/analysis/{analysis_id}/research",
    response_model=ResearchResponse,
    tags=["Research"],
    summary="Retrieve baseline research synthesis",
    description="Returns the actual research answer, citations, and evidence produced by the Research Agent.",
)
async def get_research(analysis_id: str) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if not session.research_result:
        workflow = AnalysisWorkflow(collection_name="financial_research_v1")
        try:
            res_result = workflow.run_research(
                analysis_id=session.analysis_id,
                company_name=session.company_name,
                document_id=session.document_id,
                report_year=session.report_year,
            )
            session_store.update_session(analysis_id=analysis_id, research_result=res_result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Research failed: {exc}") from exc
    else:
        res_result = session.research_result

    res = dict(res_result)
    res.setdefault("analysis_id", session.analysis_id)
    return _json_safe(res)


@app.post(
    "/analysis/{analysis_id}/research/query",
    response_model=ResearchQueryResponse,
    tags=["Research"],
    summary="Ask a research question grounded in document evidence",
    description="Executes a grounded research query against the document chunks in ChromaDB using ResearchAgent.",
)
async def query_research(analysis_id: str, request: QueryRequest) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    workflow = AnalysisWorkflow(collection_name="financial_research_v1")
    try:
        result = workflow.run_research_query(
            analysis_id=analysis_id,
            question=request.question.strip(),
            company_name=session.company_name,
            document_id=session.document_id,
            report_year=session.report_year,
        )
        session_store.update_session(analysis_id=analysis_id, research_result=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research query failed: {exc}") from exc

    return _json_safe(result)


# ------------------------------------------------------------------ #
# 5. Red Flags Endpoints
# ------------------------------------------------------------------ #

@app.get(
    "/analysis/{analysis_id}/red-flags",
    response_model=RedFlagsResponse,
    tags=["Red Flags"],
    summary="Retrieve financial risk analysis and red flags",
    description="Returns the actual financial risk items and overall risk classification produced by the Red Flag Agent.",
)
async def get_red_flags(analysis_id: str) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if not session.red_flags_result:
        workflow = AnalysisWorkflow(collection_name="financial_research_v1")
        try:
            rf_result = workflow.run_red_flags(
                analysis_id=session.analysis_id,
                company_name=session.company_name,
            )
            session_store.update_session(analysis_id=analysis_id, red_flags_result=rf_result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Red flags analysis failed: {exc}") from exc
    else:
        rf_result = session.red_flags_result

    rf = dict(rf_result)
    rf.setdefault("analysis_id", session.analysis_id)
    return _json_safe(rf)


@app.post(
    "/analysis/{analysis_id}/red-flags/query",
    response_model=RedFlagsQueryResponse,
    tags=["Red Flags"],
    summary="Ask a risk-specific question grounded in red flag evidence",
    description="Evaluates a risk-focused question against financial risk and footnote evidence.",
)
async def query_red_flags(analysis_id: str, request: QueryRequest) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    workflow = AnalysisWorkflow(collection_name="financial_research_v1")
    try:
        result = workflow.run_red_flags_query(
            analysis_id=analysis_id,
            question=request.question,
            company_name=session.company_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Red flags query failed: {exc}") from exc

    return _json_safe(result)


# ------------------------------------------------------------------ #
# 6. Comparison Endpoints
# ------------------------------------------------------------------ #

@app.post(
    "/analysis/{analysis_id}/comparison/upload",
    response_model=ComparisonResponse,
    tags=["Comparison"],
    summary="Upload second company report for peer comparison",
    description=(
        "Uploads a second company report (Company B), ingests it with Document Agent under a distinct document_id, "
        "extracts metrics, and runs the Comparison Agent across Company A and Company B."
    ),
)
async def upload_comparison(
    analysis_id: str,
    file: UploadFile = File(..., description="Second company financial report (PDF or TXT)"),
    company_name: Optional[str] = Form(None, description="Optional name of Company B"),
    report_year: Optional[str] = Form(None, description="Optional report year of Company B"),
) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if not file or not file.filename or not file.filename.strip():
        raise HTTPException(status_code=400, detail="Second document is required.")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and TXT documents are supported.")

    contents = await file.read()
    if not contents or len(contents.strip()) == 0:
        raise HTTPException(status_code=400, detail="Uploaded comparison file is empty.")

    temp_dir = "./tmp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    temp_path_b = os.path.join(temp_dir, f"comp_{safe_name}")
    with open(temp_path_b, "wb") as fh:
        fh.write(contents)

    workflow = AnalysisWorkflow(collection_name="financial_research_v1")
    # Ensure first company extraction is available for comparison
    if not session.extraction_result:
        first_extracted = workflow.run_extraction(
            analysis_id=session.analysis_id,
            company_name=session.company_name,
            document_id=session.document_id,
        )
        session_store.update_session(analysis_id=analysis_id, extraction_result=first_extracted)
    else:
        first_extracted = session.extraction_result

    try:
        comparison_result = workflow.run_comparison(
            analysis_id=analysis_id,
            first_company_name=session.company_name or "Company A",
            first_extracted=first_extracted,
            second_report_path=temp_path_b,
            second_company_name=company_name,
            second_report_year=report_year,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {exc}") from exc

    # Update session with comparison data
    session_store.update_session(
        analysis_id=analysis_id,
        comparison_result=comparison_result,
        comparison_document_id=comparison_result.get("comparison_document_id"),
        comparison_id=comparison_result.get("comparison_id"),
        comparison_company_name=company_name or Path(file.filename).stem,
    )

    return _json_safe(comparison_result)


@app.get(
    "/analysis/{analysis_id}/comparison",
    response_model=ComparisonResponse,
    tags=["Comparison"],
    summary="Retrieve cross-company comparison results",
    description="Returns the actual comparison result produced by the Comparison Agent.",
)
async def get_comparison(analysis_id: str) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if not session.comparison_result:
        raise HTTPException(
            status_code=404,
            detail="Comparison not found. Please upload a second company document via /analysis/{analysis_id}/comparison/upload first.",
        )

    cmp_res = dict(session.comparison_result)
    cmp_res.setdefault("analysis_id", session.analysis_id)
    return _json_safe(cmp_res)


# ------------------------------------------------------------------ #
# 7. Report Endpoints
# ------------------------------------------------------------------ #

@app.get(
    "/analysis/{analysis_id}/report",
    response_model=ReportResponse,
    tags=["Report"],
    summary="Retrieve synthesized executive report JSON",
    description="Returns the actual synthesized report produced by the Report Agent.",
)
async def get_report(analysis_id: str) -> dict[str, Any]:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if not session.report_result:
        workflow = AnalysisWorkflow(collection_name="financial_research_v1")
        try:
            # Ensure prerequisites are generated if missing
            ext = session.extraction_result
            if not ext:
                ext = workflow.run_extraction(
                    analysis_id=session.analysis_id,
                    company_name=session.company_name,
                    document_id=session.document_id,
                )
                session_store.update_session(analysis_id=analysis_id, extraction_result=ext)

            res = session.research_result
            if not res:
                res = workflow.run_research(
                    analysis_id=session.analysis_id,
                    company_name=session.company_name,
                )
                session_store.update_session(analysis_id=analysis_id, research_result=res)

            rf = session.red_flags_result
            if not rf:
                rf = workflow.run_red_flags(
                    analysis_id=session.analysis_id,
                    company_name=session.company_name,
                )
                session_store.update_session(analysis_id=analysis_id, red_flags_result=rf)

            cmp = session.comparison_result

            rep_result = workflow.run_report(
                analysis_id=session.analysis_id,
                company_name=session.company_name,
                report_year=session.report_year,
                document_id=session.document_id,
                extraction=ext,
                research=res,
                red_flags=rf,
                comparison=cmp,
            )
            session_store.update_session(analysis_id=analysis_id, report_result=rep_result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}") from exc
    else:
        rep_result = session.report_result

    rep = dict(rep_result)
    rep.setdefault("analysis_id", session.analysis_id)
    return _json_safe(rep)


@app.get(
    "/analysis/{analysis_id}/report/download",
    tags=["Report"],
    summary="Download publication-quality PDF report",
    description="Generates and streams the formal PDF financial report compiled by ReportService and PDFBuilder.",
)
async def download_report_pdf(analysis_id: str) -> FileResponse:
    session = session_store.get_session(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    pdf_path = session.pdf_path
    if not pdf_path or not os.path.exists(pdf_path):
        workflow = AnalysisWorkflow(collection_name="financial_research_v1")
        try:
            pdf_path = workflow.generate_pdf_report(session.to_dict())
            session_store.update_session(analysis_id=analysis_id, pdf_path=pdf_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

    safe_company = re.sub(r"[^\w\-]", "_", session.company_name or "company")
    download_filename = f"financial_report_{safe_company}_{session.report_year or '2025'}.pdf"

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_filename,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.api:app", host="127.0.0.1", port=8000, reload=True)
