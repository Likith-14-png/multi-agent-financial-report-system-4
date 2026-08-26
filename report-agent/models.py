"""
models.py

Data models used by the Report Agent.

These classes represent the outputs produced by the
Extraction Agent, Red Flag Agent, Comparison Agent,
and Research Agent.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# -------------------------------------------------
# Extraction Agent
# -------------------------------------------------

@dataclass
class ExtractionData:
    """
    Financial metrics extracted from annual reports.
    """

    company_name: str
    industry: Optional[str] = None
    business_model: Optional[str] = None
    market_position: Optional[str] = None

    revenue: Optional[Any] = None
    net_profit: Optional[Any] = None
    eps: Optional[Any] = None
    operating_margin: Optional[Any] = None
    gross_margin: Optional[Any] = None
    ebitda: Optional[Any] = None
    assets: Optional[Any] = None
    liabilities: Optional[Any] = None
    cash_flow: Optional[Any] = None
    total_debt: Optional[Any] = None
    debt_to_equity: Optional[Any] = None
    net_margin: Optional[Any] = None
    material_weakness: Optional[Dict[str, Any]] = None

    financial_ratios: Dict[str, Any] = field(default_factory=dict)
    metrics: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.metrics:
            return
        excluded = {"company_name", "industry", "business_model", "market_position", "material_weakness", "financial_ratios", "metrics"}
        self.metrics = [
            {"metric": key.replace("_", " ").title(), "value": value}
            for key, value in self.__dict__.items()
            if key not in excluded and value is not None
        ]


# -------------------------------------------------
# Red Flag Agent
# -------------------------------------------------

@dataclass
class RiskItem:
    """
    Represents a single financial risk.
    """

    category: str
    description: str
    severity: str
    title: Optional[str] = None
    evidence: Any = None
    source: Optional[str] = None
    source_page: Optional[Any] = None
    source_chunk: Optional[str] = None


@dataclass
class RedFlagData:
    """
    Stores detected risks.
    """

    risks: List[RiskItem] = field(default_factory=list)


# -------------------------------------------------
# Comparison Agent
# -------------------------------------------------

@dataclass
class CompanyComparison:
    """
    Comparison against another company.
    """

    company_name: str

    revenue: Optional[Any] = None
    net_profit: Optional[Any] = None
    operating_margin: Optional[Any] = None
    debt: Optional[Any] = None
    cash_flow: Optional[Any] = None

    ratios: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonData:
    """
    Stores comparison results.
    """

    companies: List[CompanyComparison] = field(default_factory=list)
    records: List[Dict[str, Any]] = field(default_factory=list)


# -------------------------------------------------
# Research Agent
# -------------------------------------------------

@dataclass
class ResearchItem:
    """
    Question Answer Citation
    """

    question: str
    answer: str
    evidence: str
    source: str
    source_page: Optional[Any] = None
    source_chunk: Optional[str] = None
    citation: Optional[str] = None


# -------------------------------------------------
# Final Report Model
# -------------------------------------------------

@dataclass
class ReportData:
    """
    Complete input received by Report Agent.
    """

    extraction: ExtractionData
    red_flags: RedFlagData
    comparison: ComparisonData
    research: List[ResearchItem]