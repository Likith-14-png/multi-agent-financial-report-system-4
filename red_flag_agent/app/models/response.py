from typing import List, Optional
from pydantic import BaseModel, Field


class RedFlag(BaseModel):
    category: str
    severity: str
    title: str
    description: str
    reason: str
    evidence: str
    page: Optional[int] = None
    source_file: Optional[str] = None
    source_chunk: Optional[str] = None
    recommendation: str
    confidence: float


class RedFlagAnalysisResponse(BaseModel):
    overall_risk: str
    total_flags: int
    flags: List[RedFlag]
    execution_time: float
    model_used: str
