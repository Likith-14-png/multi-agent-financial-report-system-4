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
