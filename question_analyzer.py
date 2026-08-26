"""
Question Analyzer
Converts natural-language questions into structured retrieval intent (Master Requirements §3)

Examples:
  "What was revenue in FY2025?"
  → {intent: "financial_metric", metric: "revenue", period: "FY2025", ...}

  "Why did operating margin decline?"
  → {intent: "causal_analysis", metric: "operating_margin", ...}

  "Compare revenue between Company A and Company B"
  → {intent: "comparison", metric: "revenue", comparison: true}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class FinancialQuestionIntent:
    """Structured representation of question intent for retrieval."""

    # Primary intent type
    intent: str  # "financial_metric", "causal_analysis", "comparison", "calculation", "ranking", "risk", "citation", "unknown"

    # Target entities
    target_company: Optional[str] = None
    target_companies: List[str] = field(default_factory=list)
    target_entities: List[str] = field(default_factory=list)  # segments, divisions, geographies

    # Financial metrics
    target_metrics: List[str] = field(default_factory=list)

    # Time period
    target_years: List[str] = field(default_factory=list)
    target_quarters: List[str] = field(default_factory=list)

    # Question characteristics
    is_causal: bool = False  # "why", "because", "due to", "reason", "driver"
    is_comparative: bool = False  # "compare", "vs", "versus", "between"
    is_ranking: bool = False  # "highest", "lowest", "most", "least", "top", "bottom"
    requires_calculation: bool = False  # "growth", "margin", "ratio", "change", "difference"
    requires_aggregation: bool = False  # "total", "sum", "combined", "consolidated"

    # Question scope
    requires_context: bool = False  # Questions needing explanation, not just numbers
    requires_historical: bool = False  # Multiple years/periods
    requires_segment_breakdown: bool = False

    # Confidence in analysis
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "intent": self.intent,
            "target_company": self.target_company,
            "target_companies": self.target_companies,
            "target_entities": self.target_entities,
            "target_metrics": self.target_metrics,
            "target_years": self.target_years,
            "target_quarters": self.target_quarters,
            "is_causal": self.is_causal,
            "is_comparative": self.is_comparative,
            "is_ranking": self.is_ranking,
            "requires_calculation": self.requires_calculation,
            "requires_aggregation": self.requires_aggregation,
            "requires_context": self.requires_context,
            "requires_historical": self.requires_historical,
            "requires_segment_breakdown": self.requires_segment_breakdown,
            "confidence": self.confidence,
        }


class QuestionIntentAnalyzer:
    """
    Analyzes natural-language questions to extract structured intent.

    Used by Research Agent, Red Flag Agent, and Comparison Agent to plan retrieval strategy.
    """

    # Metric name mappings
    METRIC_ALIASES = {
        "revenue": ["revenue", "sales", "net sales", "total income", "income from operations", "operating revenue"],
        "gross_profit": ["gross profit", "gross margin", "cost of goods sold", "cogs"],
        "operating_income": ["operating income", "operating profit", "ebit", "earnings before interest and taxes"],
        "ebitda": ["ebitda", "earnings before interest taxes depreciation"],
        "net_income": ["net income", "net profit", "bottom line", "profit", "earnings", "profit attributable"],
        "eps": ["eps", "earnings per share", "diluted eps", "basic eps", "per share"],
        "total_assets": ["total assets", "assets", "total current assets", "non-current assets"],
        "total_liabilities": ["total liabilities", "total debt", "liabilities"],
        "stockholders_equity": ["equity", "shareholders equity", "stockholders equity", "total equity"],
        "debt": ["debt", "long-term debt", "short-term debt", "borrowings"],
        "cash_flow": ["cash flow", "operating cash flow", "investing cash flow", "financing cash flow", "free cash flow", "fcf"],
        "margin": ["margin", "operating margin", "profit margin", "net margin", "gross margin", "ebitda margin"],
        "roe": ["roe", "return on equity", "return on assets", "roa"],
        "capex": ["capex", "capital expenditure", "capital expenditures", "property plant equipment"],
        "rd_expense": ["r&d", "research and development", "rd expense"],
        "segment": ["segment", "division", "line of business", "product category", "geography"],
    }

    METRIC_PRIORITY = {
        "revenue": 10,
        "net_income": 9,
        "operating_income": 8,
        "eps": 8,
        "total_assets": 7,
        "debt": 7,
        "margin": 6,
    }

    @classmethod
    def analyze(cls, question: str, target_company: Optional[str] = None) -> FinancialQuestionIntent:
        """
        Analyze a natural-language question and extract intent.

        Args:
            question: Natural language question
            target_company: Optional company name context

        Returns:
            FinancialQuestionIntent with extracted structure
        """
        if not question or not question.strip():
            return FinancialQuestionIntent(intent="unknown")

        q_lower = question.lower().strip()
        intent = FinancialQuestionIntent(intent="financial_metric", target_company=target_company)

        # 1. Extract question characteristics
        intent.is_causal = cls._is_causal_question(q_lower)
        intent.is_comparative = cls._is_comparative_question(q_lower)
        intent.is_ranking = cls._is_ranking_question(q_lower)
        intent.requires_calculation = cls._requires_calculation(q_lower)
        intent.requires_context = cls._requires_context(q_lower)
        intent.requires_historical = cls._requires_historical(q_lower)
        intent.requires_segment_breakdown = cls._requires_segment_breakdown(q_lower)

        # 2. Determine primary intent type
        if intent.is_causal:
            intent.intent = "causal_analysis"
        elif intent.is_comparative and len(cls._extract_companies(q_lower, target_company)) >= 2:
            intent.intent = "comparison"
        elif intent.is_ranking:
            intent.intent = "ranking"
        elif "risk" in q_lower or "concern" in q_lower or "issue" in q_lower:
            intent.intent = "risk"
        elif any(word in q_lower for word in ["citation", "source", "where", "quote", "evidence", "reference"]):
            intent.intent = "citation"
        else:
            intent.intent = "financial_metric"

        # 3. Extract companies
        companies = cls._extract_companies(q_lower, target_company)
        if companies:
            intent.target_company = companies[0] if len(companies) >= 1 else None
            intent.target_companies = companies
        elif target_company:
            intent.target_company = target_company

        # 4. Extract metrics (prioritized)
        metrics = cls._extract_metrics(q_lower)
        intent.target_metrics = sorted(
            metrics,
            key=lambda m: cls.METRIC_PRIORITY.get(m, 0),
            reverse=True
        )

        # 5. Extract temporal information
        intent.target_years = cls._extract_years(q_lower)
        intent.target_quarters = cls._extract_quarters(q_lower)
        intent.requires_historical = len(intent.target_years) >= 2 or len(intent.target_quarters) >= 2

        # 6. Extract entities (segments, geographies, etc.)
        intent.target_entities = cls._extract_entities(q_lower)

        return intent

    @staticmethod
    def _is_causal_question(question: str) -> bool:
        """Detect causal/analytical questions."""
        causal_markers = ["why", "because", "reason", "driver", "cause", "caused", "due to", "attributed",
                         "resulted", "factors", "impact", "driven", "account for", "explain"]
        return any(marker in question for marker in causal_markers)

    @staticmethod
    def _is_comparative_question(question: str) -> bool:
        """Detect comparative questions."""
        comparative_markers = ["compare", "vs", "versus", "between", "versus", "compared to", "vs.",
                              "relative", "higher", "lower", "more", "less", "similar"]
        return any(marker in question for marker in comparative_markers)

    @staticmethod
    def _is_ranking_question(question: str) -> bool:
        """Detect ranking/superlative questions."""
        ranking_markers = ["highest", "lowest", "most", "least", "top", "bottom", "leading", "largest",
                          "smallest", "largest", "best", "worst", "ranked", "ranking"]
        return any(marker in question for marker in ranking_markers)

    @staticmethod
    def _requires_calculation(question: str) -> bool:
        """Detect questions requiring calculations."""
        calc_markers = ["growth", "change", "increased", "decreased", "margin", "ratio", "percentage",
                       "difference", "improvement", "decline", "growth rate", "cagr"]
        return any(marker in question for marker in calc_markers)

    @staticmethod
    def _requires_context(question: str) -> bool:
        """Detect questions requiring contextual explanation."""
        context_markers = ["why", "how", "explain", "discuss", "describe", "background", "reason",
                          "impact", "effect", "consequence", "result"]
        return any(marker in question for marker in context_markers)

    @staticmethod
    def _requires_historical(question: str) -> bool:
        """Detect questions about historical trends."""
        historical_markers = ["over time", "trend", "history", "historically", "historically",
                             "year-over-year", "yoy", "past", "previous"]
        return any(marker in question for marker in historical_markers)

    @staticmethod
    def _requires_segment_breakdown(question: str) -> bool:
        """Detect questions about segment/geographic breakdown."""
        segment_markers = ["segment", "division", "geography", "region", "product", "category",
                          "breakdown", "by region", "by segment", "by country", "by product"]
        return any(marker in question for marker in segment_markers)

    @classmethod
    def _extract_companies(cls, question: str, default_company: Optional[str] = None) -> List[str]:
        """Extract company names from question."""
        companies = []
        if default_company:
            companies.append(default_company)

        # Look for capitalized words (potential company names)
        # This is conservative to avoid false positives
        words = question.split()
        for word in words:
            if word[0].isupper() and len(word) > 1 and "?" not in word and "." not in word:
                # Avoid common English words
                if word.lower() not in ["company", "companies", "corp", "inc", "ltd", "llc", "group"]:
                    companies.append(word)

        return list(dict.fromkeys(companies))  # Remove duplicates

    @classmethod
    def _extract_metrics(cls, question: str) -> List[str]:
        """Extract financial metrics from question."""
        detected = []
        for metric, aliases in cls.METRIC_ALIASES.items():
            for alias in aliases:
                if alias in question:
                    detected.append(metric)
                    break
        return list(dict.fromkeys(detected))

    @staticmethod
    def _extract_years(question: str) -> List[str]:
        """Extract years/fiscal years from question."""
        years = set()

        # FY format: FY2024, FY2025, FY2026
        fy_matches = re.findall(r"fy\s*(\d{4})", question, re.IGNORECASE)
        for year in fy_matches:
            years.add(f"FY{year}")

        # Plain year format: 2024, 2025, 2026
        year_matches = re.findall(r"\b(20\d{2}|19\d{2})\b", question)
        for year in year_matches:
            if f"FY{year}" not in years:
                years.add(year)

        return sorted(list(years), reverse=True)

    @staticmethod
    def _extract_quarters(question: str) -> List[str]:
        """Extract quarters from question."""
        quarters = []

        # Q format: Q1, Q2, Q3, Q4
        q_matches = re.findall(r"(q[1-4])\s*(\d{4})?", question, re.IGNORECASE)
        for q_num, year in q_matches:
            quarter = q_num.upper()
            if year:
                quarter += f" {year}"
            quarters.append(quarter)

        return quarters

    @staticmethod
    def _extract_entities(question: str) -> List[str]:
        """Extract business entities (segments, geographies, etc.)."""
        entities = []

        # Common segment/geography patterns
        segment_patterns = [
            r"segment[s]?[\s:]*([a-zA-Z\s]+?)(?:\s+(?:revenue|sales|income|profit|metric)|\?|$)",
            r"(Americas|Europe|Asia|EMEA|APAC|North America|Europe|India|China|Japan)",
            r"division[s]?[\s:]*([a-zA-Z\s]+?)(?:\s+(?:revenue|sales|income)|\?|$)",
            r"product[\s:]*([a-zA-Z\s]+?)(?:\s+(?:revenue|sales)|\?|$)",
            r"geography|geographic[s]?[\s:]*([a-zA-Z\s]+?)(?:\s+(?:revenue|sales)|\?|$)",
        ]

        for pattern in segment_patterns:
            matches = re.findall(pattern, question, re.IGNORECASE)
            for match in matches:
                entity = match.strip() if isinstance(match, str) else match[0].strip() if match else ""
                if entity and len(entity.split()) <= 3:  # Reasonable entity name length
                    entities.append(entity)

        return list(dict.fromkeys(entities))
