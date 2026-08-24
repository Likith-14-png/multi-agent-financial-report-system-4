from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnalysisMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: str
    document_id: str
    company_name: str
    report_year: int | str
    chunk_id: Optional[str] = None

    @field_validator("analysis_id", "document_id", "company_name")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        if value is None or str(value).strip() == "":
            raise ValueError("required field cannot be empty")
        return str(value)

    @field_validator("report_year")
    @classmethod
    def validate_report_year(cls, value: int | str) -> int | str:
        if value in (None, ""):
            raise ValueError("report_year is required")
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("report_year is required")
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError("report_year must be an integer or integer-like string") from exc
        return int(value)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    source: Optional[str] = None
    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    company_name: Optional[str] = None
    report_year: Optional[int | str] = None
    chunk_id: Optional[str] = None


class ResearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    answer: str = ""
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class RedFlagResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    overall_risk: str = "Low"
    total_flags: int = 0
    flags: List[Dict[str, Any]] = Field(default_factory=list)
    execution_time: Optional[float] = None
    model_used: Optional[str] = None


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    comparison_type: str = "single_year"
    records: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None


class ReportResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    metadata: Optional[Dict[str, Any]] = None
    company_name: Optional[str] = None
    report_year: Optional[int] = None
    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    executive_summary: str = ""
    financial_metrics: List[Dict[str, Any]] = Field(default_factory=list)
    research_findings: List[Dict[str, Any]] = Field(default_factory=list)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    comparison: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    report_status: str = "complete"
    extraction: Optional[Dict[str, Any]] = None
    research: Optional[Dict[str, Any]] = None
    red_flags: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_required_sections(self) -> "ReportResult":
        if self.metadata is None:
            if not self.analysis_id or not self.document_id or not self.company_name or self.report_year in (None, ""):
                raise ValueError("metadata is required for a valid report")
        else:
            if not self.metadata.get("analysis_id") or not self.metadata.get("document_id") or not self.metadata.get("company_name"):
                raise ValueError("metadata.analysis_id/document_id/company_name are required")
            if self.report_year in (None, "") and self.metadata.get("report_year") in (None, ""):
                raise ValueError("metadata.report_year is required")
        if self.report_status not in {"complete", "partial", "failed"}:
            raise ValueError("report_status must be complete, partial, or failed")
        return self


class AnalysisContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    metadata: AnalysisMetadata
    extraction: Dict[str, Any] = Field(default_factory=dict)
    research: Dict[str, Any] = Field(default_factory=dict)
    red_flags: Dict[str, Any] = Field(default_factory=dict)
    comparison: Dict[str, Any] = Field(default_factory=dict)
    report: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_metadata_exists(self) -> "AnalysisContext":
        metadata = self.metadata
        if not metadata.analysis_id:
            raise ValueError("metadata.analysis_id is required")
        if not metadata.document_id:
            raise ValueError("metadata.document_id is required")
        if not metadata.company_name:
            raise ValueError("metadata.company_name is required")
        if metadata.report_year in (None, ""):
            raise ValueError("metadata.report_year is required")
        return self


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "success"
    analysis: AnalysisContext


class ApiAnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    company_name: Optional[str] = None
    report_year: Optional[int | str] = None


class ApiErrorDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str = "ANALYSIS_FAILED"
    message: str = "Analysis failed"
    stage: str = "api"


class ApiResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    success: bool = True
    status: str = "success"
    analysis: ApiAnalysisSummary = Field(default_factory=ApiAnalysisSummary)
    extraction: Dict[str, Any] = Field(default_factory=dict)
    research: Dict[str, Any] = Field(default_factory=dict)
    red_flags: Dict[str, Any] = Field(default_factory=dict)
    comparison: Dict[str, Any] = Field(default_factory=dict)
    report: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[ApiErrorDetail] = None
    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    company_name: Optional[str] = None
    report_year: Optional[int | str] = None


def validate_analysis_context(payload: Dict[str, Any]) -> AnalysisContext:
    return AnalysisContext.model_validate(payload)


# ------------------------------------------------------------------ #
# Dedicated API Request / Response Models for Swagger & Endpoints
# ------------------------------------------------------------------ #

class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = Field("healthy", json_schema_extra={"example": "healthy"}, description="Health check status")
    service: str = Field("financial-analysis-api", json_schema_extra={"example": "financial-analysis-api"}, description="Service identifier")


class DocumentChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk_id: str = Field(..., description="Unique chunk identifier")
    chunk_index: Optional[int] = Field(None, description="Index of the chunk in the document")
    page_number: Optional[str | int] = Field(None, description="Source page number or range")
    page_start: Optional[int] = Field(None, description="Starting page number")
    page_end: Optional[int] = Field(None, description="Ending page number")
    section_title: Optional[str] = Field(None, description="Heading or section title")
    section_type: Optional[str] = Field(None, description="Section classification type")
    text: Optional[str] = Field(None, description="Extracted chunk text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Complete metadata stored with chunk")


class AnalysisUploadResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = Field("success", description="Status of the document ingestion")
    message: str = Field("Document processed and stored in ChromaDB successfully", description="Status message")
    analysis_id: str = Field(..., description="Unique analysis session identifier")
    document_id: str = Field(..., description="Unique document identifier")
    company_name: Optional[str] = Field(None, description="Detected or provided company name")
    report_year: Optional[int | str] = Field(None, description="Detected or provided fiscal year")
    document: Optional[str] = Field(None, description="Uploaded file name")
    collection: Optional[str] = Field("financial_research_v1", description="ChromaDB collection name")
    total_chunks: int = Field(0, description="Total chunks processed and stored")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="Document chunks stored in ChromaDB")
    quality_report: Optional[Dict[str, Any]] = Field(default=None, description="Document Agent quality report")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Analysis and document metadata")


class AnalysisStatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: str = Field(..., description="Unique analysis session identifier")
    status: str = Field(..., description="Current status of the analysis session")
    current_agent: Optional[str] = Field(None, description="Currently active agent or null if complete")
    progress: int = Field(100, description="Estimated progress percentage (0-100)")


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    company_name: Optional[str] = None
    report_year: Optional[int | str] = None
    revenue: Optional[Any] = None
    gross_profit: Optional[Any] = None
    operating_income: Optional[Any] = None
    pretax_income: Optional[Any] = None
    net_income: Optional[Any] = None
    total_assets: Optional[Any] = None
    total_liabilities: Optional[Any] = None
    total_equity: Optional[Any] = None
    cash_flow: Optional[Any] = None
    operating_cash_flow: Optional[Any] = None
    free_cash_flow: Optional[Any] = None
    rd_expense: Optional[Any] = None
    eps: Optional[Any] = None
    basic_eps: Optional[Any] = None
    diluted_eps: Optional[Any] = None
    trend_eps: Optional[Any] = None
    yearly_metrics: Optional[Dict[str, Any]] = None
    income_statement: Optional[Dict[str, Any]] = None
    balance_sheet: Optional[Dict[str, Any]] = None
    cash_flow_statement: Optional[Dict[str, Any]] = None
    segment_metrics: Optional[Dict[str, Any]] = None
    accounting_information: Optional[List[Dict[str, Any]]] = None
    risk_related_metrics: Optional[List[Dict[str, Any]]] = None
    detailed_metrics: Optional[List[Dict[str, Any]]] = None
    observations: Optional[List[Dict[str, Any]]] = None
    traceability: Optional[Dict[str, Any]] = None
    source_chunks: Optional[List[str]] = None
    source_file: Optional[str] = None
    source: Optional[str] = None
    chunk_id: Optional[str] = None
    source_text: Optional[str] = None


class ResearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: Optional[str] = None
    status: Optional[str] = "completed"
    question: Optional[str] = None
    answer: Optional[str] = Field(None, description="Grounded research synthesis answer")
    final_answer: Optional[str] = None
    summary: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Citations and evidence snippets")
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    steps: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    findings: Optional[List[Any]] = None
    source_chunks: Optional[List[str]] = None
    model_used: Optional[str] = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question to query against document evidence", json_schema_extra={"example": "Why did revenue increase?"})


class ResearchQueryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: str
    question: str
    answer: str
    status: Optional[str] = "completed"
    summary: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    steps: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    findings: Optional[List[Any]] = None
    source_chunks: Optional[List[str]] = None
    model_used: Optional[str] = None


class RedFlagsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: Optional[str] = None
    overall_risk: str = Field("Low", description="Overall risk classification")
    total_flags: int = Field(0, description="Total number of risk flags identified")
    flags: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed list of detected financial risk items")
    model_used: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class RedFlagsQueryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: str
    question: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)


class ComparisonUploadResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: str
    comparison_id: str
    status: str = "completed"
    companies: List[str] = Field(default_factory=list, description="List of companies compared")


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: Optional[str] = None
    comparison_id: Optional[str] = None
    status: Optional[str] = None
    companies: List[str] = Field(default_factory=list)
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    records: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None
    comparison_type: Optional[str] = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    company_name: Optional[str] = None
    report_year: Optional[int | str] = None
    executive_summary: Optional[str] = None
    financial_metrics: Optional[List[Dict[str, Any]]] = None
    research_findings: Optional[List[Dict[str, Any]]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    comparison: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    recommendations: Optional[List[str]] = None
    report_status: Optional[str] = None
    extraction: Optional[Dict[str, Any]] = None
    research: Optional[Dict[str, Any]] = None
    red_flags: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    metadata_trace: Optional[Dict[str, Any]] = None
