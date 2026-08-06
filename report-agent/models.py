"""
models.py

Data models used by the Report Agent.

These classes represent the outputs produced by the
Extraction Agent, Red Flag Agent, Comparison Agent,
and Research Agent.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


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

    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    eps: Optional[float] = None
    operating_margin: Optional[float] = None
    gross_margin: Optional[float] = None
    ebitda: Optional[float] = None
    assets: Optional[float] = None
    liabilities: Optional[float] = None
    cash_flow: Optional[float] = None

    financial_ratios: Dict[str, float] = field(default_factory=dict)


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

    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    operating_margin: Optional[float] = None
    debt: Optional[float] = None
    cash_flow: Optional[float] = None

    ratios: Dict[str, float] = field(default_factory=dict)


@dataclass
class ComparisonData:
    """
    Stores comparison results.
    """

    companies: List[CompanyComparison] = field(default_factory=list)


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