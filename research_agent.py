"""Multi-Agent Financial Research System — General-Purpose Financial Research Agent.

Implements a question-agnostic, general-purpose reasoning & retrieval pipeline:
User Question → Intent Understanding → Evidence Requirements → Dynamic Retrieval Planning →
ChromaDB Multi-Query Retrieval (with Session Isolation) → Metadata Sanitization & Ranking →
Evidence Sufficiency Loop (Secondary Retrieval if needed) → Financial Reasoning & Calculations →
Gemini / LLM Grounded Synthesis (with Multi-step Reasoning) → Claim & Citation Validation.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Data Models
# ------------------------------------------------------------------ #

@dataclass
class Citation:
    company: str
    doc_type: str
    section: str
    source_file: str
    chunk_id: str
    snippet: str
    score: Optional[float] = None
    page: Optional[int | str] = None
    report_year: Optional[int | str] = None

    def __str__(self) -> str:
        page_str = f" | Page {self.page}" if self.page else ""
        year_str = f" | {self.report_year}" if self.report_year else ""
        return (f"[{self.company} | {self.doc_type}{year_str} | {self.section} | "
                f"{self.source_file}{page_str} | chunk {self.chunk_id}]")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "company": self.company,
            "company_name": self.company,
            "doc_type": self.doc_type,
            "report_type": self.doc_type,
            "section": self.section,
            "section_title": self.section,
            "source_file": self.source_file,
            "source": self.source_file,
            "chunk_id": self.chunk_id,
            "snippet": self.snippet,
            "score": self.score,
        }
        if self.page is not None:
            d["page"] = self.page
            d["page_number"] = self.page
        if self.report_year is not None:
            d["report_year"] = self.report_year
        return d


@dataclass
class FinancialFact:
    """Structured financial fact extracted from chunk text or table."""
    entity: str
    metric: str
    period: str
    value: float
    raw_str: str
    unit: str = "millions"
    chunk_id: str = ""
    section: str = ""
    page: Optional[int | str] = None
    company: str = ""
    source_file: str = ""


@dataclass
class ResearchStep:
    sub_question: str
    citations: List[Citation] = field(default_factory=list)
    findings: str = ""
    raw_texts: List[str] = field(default_factory=list)
    raw_records: List[Dict[str, Any]] = field(default_factory=list)
    extracted_facts: List[FinancialFact] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub_question": self.sub_question,
            "step": self.sub_question,
            "description": self.findings or f"Evaluated evidence for '{self.sub_question}'",
            "findings": self.findings,
            "citations": [c.to_dict() for c in self.citations],
            "raw_texts": self.raw_texts,
        }


@dataclass
class ResearchAnswer:
    question: str
    steps: List[ResearchStep]
    final_answer: str
    model_used: str = "deterministic-fallback"
    evidence_claims: List[Dict[str, Any]] = field(default_factory=list)

    def all_citations(self) -> List[Citation]:
        best_by_chunk: Dict[str, Citation] = {}
        for step in self.steps:
            for c in step.citations:
                key = str(c.chunk_id or "").strip()
                if not key:
                    key = str((c.company, c.doc_type, c.section, c.snippet))
                existing = best_by_chunk.get(key)
                if existing is None:
                    best_by_chunk[key] = c
                    continue
                current_score = c.score if isinstance(c.score, (int, float)) else None
                existing_score = existing.score if isinstance(existing.score, (int, float)) else None
                if current_score is not None and (existing_score is None or current_score < existing_score):
                    best_by_chunk[key] = c
        return list(best_by_chunk.values())

    def to_dict(self, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        citations_list = [c.to_dict() for c in self.all_citations()]
        source_chunks = [c.chunk_id for c in self.all_citations() if c.chunk_id]

        evidence_list = []
        if self.evidence_claims:
            evidence_list = self.evidence_claims
        else:
            for c in self.all_citations():
                evidence_list.append({
                    "claim": f"Evidence from {c.section}",
                    "snippet": c.snippet,
                    "source": str(c),
                    "source_file": c.source_file,
                    "chunk_id": c.chunk_id,
                    "company": c.company,
                    "section": c.section,
                    "score": c.score,
                })

        step_dicts = []
        for idx, s in enumerate(self.steps, 1):
            step_dicts.append({
                "step": idx,
                "sub_question": s.sub_question,
                "description": s.findings or f"Retrieved evidence for '{s.sub_question}'",
                "findings": s.findings,
                "citations": [c.to_dict() for c in s.citations],
            })

        return {
            "analysis_id": analysis_id,
            "status": "completed",
            "question": self.question,
            "answer": self.final_answer,
            "final_answer": self.final_answer,
            "summary": self.final_answer,
            "sources": citations_list,
            "evidence": evidence_list,
            "steps": step_dicts,
            "citations": citations_list,
            "findings": evidence_list,
            "source_chunks": list(dict.fromkeys(source_chunks)),
            "model_used": self.model_used,
        }


# ------------------------------------------------------------------ #
# Financial Parsing, Table & Metric Extraction
# ------------------------------------------------------------------ #

class QuestionIntentType(str, Enum):
    FACTUAL = "factual"
    COMPARISON = "comparison"
    CAUSAL = "causal"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    RISK_ANALYSIS = "risk_analysis"
    CALCULATION = "calculation"
    MULTI_PART = "multi_part"


@dataclass
class StructuredResearchPlan:
    """Structured research plan derived dynamically from any financial question."""
    entities: List[str] = field(default_factory=list)
    companies: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    periods: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    sub_questions: List[str] = field(default_factory=list)
    calculation_requirements: List[Dict[str, Any]] = field(default_factory=list)
    evidence_requirements: List[Dict[str, Any]] = field(default_factory=list)
    is_causal: bool = False
    is_comparative: bool = False
    requires_calculation: bool = False
    requires_ranking: bool = False
    requires_citations: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": self.entities,
            "companies": self.companies,
            "metrics": self.metrics,
            "periods": self.periods,
            "operations": self.operations,
            "sub_questions": self.sub_questions,
            "calculation_requirements": self.calculation_requirements,
            "evidence_requirements": self.evidence_requirements,
            "is_causal": self.is_causal,
            "is_comparative": self.is_comparative,
            "requires_calculation": self.requires_calculation,
            "requires_ranking": self.requires_ranking,
            "requires_citations": self.requires_citations,
        }


@dataclass
class FinancialQuestionIntent:
    original_question: str
    intent_type: QuestionIntentType
    is_causal: bool
    is_comparative: bool
    requires_calculation: bool
    target_metrics: List[str]
    target_years: List[str]
    target_entities: List[str] = field(default_factory=list)
    target_company: Optional[str] = None
    required_sections: List[str] = field(default_factory=list)
    calculation_type: Optional[str] = None
    requires_ranking: bool = False
    requires_citations: bool = False
    research_plan: Optional[StructuredResearchPlan] = None


def parse_numeric_value(raw: str) -> Optional[float]:
    """Parse numeric values handling parentheses as negative numbers, suffixes, and currency symbols."""
    clean = str(raw).strip()
    if not clean:
        return None
    # Strip leading/trailing currencies and whitespace outside or inside parens
    is_negative = False
    if clean.startswith("$") or clean.startswith("€") or clean.startswith("£"):
        clean = clean[1:].strip()
    if clean.startswith("(") and clean.endswith(")"):
        is_negative = True
        clean = clean[1:-1].strip()
    elif clean.startswith("-") or clean.startswith("$-") or clean.startswith("-$"):
        is_negative = True
        clean = clean.replace("$-", "").replace("-$", "").replace("-", "").strip()

    clean = clean.replace("$", "").replace("€", "").replace("£", "").replace(",", "").replace("%", "").strip()
    if clean.endswith("-"):
        is_negative = True
        clean = clean[:-1].strip()

    # Handle magnitude suffixes
    mult = 1.0
    if clean.lower().endswith("billion") or clean.lower().endswith("bn") or clean.lower().endswith("b"):
        mult = 1000.0 if "m" in clean.lower() else 1.0
        clean = re.sub(r"(?i)\s*(?:billion|bn|b)$", "", clean)
    elif clean.lower().endswith("million") or clean.lower().endswith("m"):
        clean = re.sub(r"(?i)\s*(?:million|m)$", "", clean)
    elif clean.lower().endswith("thousand") or clean.lower().endswith("k"):
        mult = 0.001
        clean = re.sub(r"(?i)\s*(?:thousand|k)$", "", clean)

    try:
        val = float(clean) * mult
        return -val if is_negative else val
    except ValueError:
        return None


def calculate_growth_rate(curr: float, prev: float) -> Optional[float]:
    """Calculate percentage growth: ((curr - prev) / abs(prev)) * 100."""
    if prev == 0:
        return None
    return ((curr - prev) / abs(prev)) * 100.0


def calculate_margin(numerator: float, denominator: float) -> Optional[float]:
    """Calculate margin percentage: (numerator / denominator) * 100."""
    if denominator == 0:
        return None
    return (numerator / denominator) * 100.0


@dataclass
class ComparisonMatrix:
    """Dynamic multi-dimensional Entity x Metric x Period matrix."""
    entities: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    periods: List[str] = field(default_factory=list)
    facts: Dict[Tuple[str, str, str], FinancialFact] = field(default_factory=dict)

    def add_fact(self, fact: FinancialFact):
        clean_ent = fact.entity.strip()
        clean_metric = fact.metric.strip()
        clean_period = fact.period.strip()
        if clean_ent and clean_ent not in self.entities:
            self.entities.append(clean_ent)
        if clean_metric and clean_metric not in self.metrics:
            self.metrics.append(clean_metric)
        if clean_period and clean_period not in self.periods:
            self.periods.append(clean_period)
        self.facts[(clean_ent.lower(), clean_metric.lower(), clean_period)] = fact

    def get_fact(self, entity: str, metric: str, period: str) -> Optional[FinancialFact]:
        return self.facts.get((entity.lower().strip(), metric.lower().strip(), period.strip()))

    def get_value(self, entity: str, metric: str, period: str) -> Optional[float]:
        f = self.get_fact(entity, metric, period)
        return f.value if f else None


@dataclass
class ParsedTableRow:
    label: str
    values: List[float]
    raw_tokens: List[str] = field(default_factory=list)


@dataclass
class ParsedTable:
    title: Optional[str]
    headers: List[str]
    rows: List[ParsedTableRow]
    years: List[str]
    unit: str = "millions"

    def to_markdown(self) -> str:
        if not self.rows:
            return ""
        first_hdr = self.headers[0] if self.headers else "Segment"
        col_headers = [first_hdr]
        for h in self.headers[1:]:
            col_headers.append(h)
        if len(self.years) >= 2 and len(self.rows[0].values) >= 2:
            col_headers.append("Growth")

        header_line = "| " + " | ".join(col_headers) + " |"
        separator_line = "| " + " | ".join([":---" for _ in col_headers]) + " |"
        body_lines = []
        for r in self.rows:
            row_cols = [r.label]
            for v in r.values:
                val_str = f"${v:,.0f}M" if abs(v) > 50 else f"${v:,.2f}"
                row_cols.append(val_str)
            if len(r.values) >= 2:
                g = calculate_growth_rate(r.values[0], r.values[1])
                row_cols.append(f"{g:+.1f}%" if g is not None else "N/A")
            body_lines.append("| " + " | ".join(row_cols) + " |")

        return "\n".join([header_line, separator_line] + body_lines)


def extract_tables_from_text(text: str) -> List[ParsedTable]:
    """Dynamically parse multi-column and multiline financial tables from chunk text."""
    tables: List[ParsedTable] = []
    if not text or not text.strip():
        return tables

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return tables

    # Discover years in text
    all_years = re.findall(r"\b(202\d|201\d)\b", text)
    distinct_years = list(dict.fromkeys(all_years))
    if len(distinct_years) < 2:
        distinct_years = ["2025", "2024"]

    row_patterns: List[Tuple[str, List[float]]] = []

    # 1. Check for pipe-separated or colon-separated multi-year rows:
    # E.g. "Total Revenue: 2025: $65,400 | 2024: $58,200 | 2023: $50,500"
    for line in lines:
        m_pipe = re.match(r"^([^:\d\|]+?)\s*:\s*(?:202\d|201\d)?\s*[:\s]*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?\s*\|\s*(?:202\d|201\d)?\s*[:\s]*\$?\s*([\d,]+(?:\.\d+)?)", line, re.I)
        if m_pipe:
            label = m_pipe.group(1).strip()
            v1 = parse_numeric_value(m_pipe.group(2))
            v2 = parse_numeric_value(m_pipe.group(3))
            if v1 is not None and v2 is not None and len(label) >= 2:
                row_patterns.append((label, [v1, v2]))

    # 2. Check for single-line multi-numeric rows (e.g. "Total Software $29,962 $27,085")
    if not row_patterns:
        for line in lines:
            if len(line) > 100:
                continue
            m_num = re.findall(r"(?:\$?\s*\(?[\d,]+(?:\.\d+)?\)?\s*%?|\(?[\d,]+(?:\.\d+)?\s*(?:million|billion)\)?)", line)
            m_num_clean = [n for n in m_num if n.strip("$ ,%") not in ["2023", "2024", "2025", "2026", "2022", "2021"]]
            if len(m_num_clean) >= 2:
                label = re.sub(r"(?:\$?\s*\(?[\d,]+(?:\.\d+)?\)?\s*%?|\(?[\d,]+(?:\.\d+)?\s*(?:million|billion)\)?).*", "", line).strip()
                label = re.sub(r"[:\-\|]+$", "", label).strip()
                is_inv = (
                    len(label) > 40 or
                    any(v in label.lower() for v in ["grew", "increased", "declined", "expanded", "decreased", "reflecting", "driven", "primarily", "attribut", "due to", "because", "benefit", "represent"]) or
                    label.lower().startswith(("table", "item", "page", "note", "consisting", "consolidated", "statement", "total debt", "short-term", "long-term", "free cash", "diluted", "net cash"))
                )
                if not is_inv and label:
                    parsed_vals = []
                    for raw_val in m_num_clean:
                        v = parse_numeric_value(raw_val)
                        if v is not None:
                            parsed_vals.append(v)
                    if len(parsed_vals) >= 2:
                        row_patterns.append((label, parsed_vals[:2]))

    # 3. Check for multiline vertical table structures (e.g.
    # "Total Software: $29,962 million\n2024: $27,085 million" OR
    # "Total Software\n$ 29,962\n$27,085"
    if not row_patterns:
        i = 0
        while i < len(lines):
            line = lines[i]
            m_with_val = re.match(r"^(?:Total\s+)?([A-Za-z0-9\s&/\-]+?)\s*[:\-]\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?$", line, re.I)
            m_label_only = re.match(r"^(?:Total\s+)?([A-Za-z0-9\s&/\-]+?)\s*[:\-]?$", line, re.I)

            cand_label = None
            vals: List[float] = []

            if m_with_val:
                cand_label = m_with_val.group(1).strip()
                val1 = parse_numeric_value(m_with_val.group(2))
                if val1 is not None:
                    vals.append(val1)
            elif m_label_only:
                cand_label = m_label_only.group(1).strip()

            if cand_label:
                j = i + 1
                while j < min(len(lines), i + 4) and len(vals) < 2:
                    next_line = lines[j]
                    num_matches = re.findall(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)", next_line)
                    for nm in num_matches:
                        if nm and nm not in ["2023", "2024", "2025", "2026", "2022", "2021"]:
                            v = parse_numeric_value(nm)
                            if v is not None and v > 0:
                                vals.append(v)
                                if len(vals) == 2:
                                    break
                    j += 1

                cand_low = cand_label.lower()
                is_invalid_label = (
                    cand_low.startswith(("table", "item", "page", "note", "consisting", "consolidated", "statement", "total debt", "short-term", "long-term", "free cash", "diluted", "net cash")) or
                    any(v in cand_low for v in ["grew", "increased", "declined", "expanded", "decreased", "reflecting", "driven", "primarily", "attribut", "due to", "because", "benefit", "represent"]) or
                    "cash flows" in cand_low or
                    "highlights" in cand_low or
                    "summary" in cand_low or
                    "balance sheet" in cand_low or
                    "assets" in cand_low or
                    "liabilities" in cand_low or
                    "equity" in cand_low
                )
                if len(vals) >= 2 and not is_invalid_label:
                    if len(cand_label) > 2 and not any(r[0].lower() == cand_label.lower() for r in row_patterns):
                        row_patterns.append((cand_label, vals[:2]))
                        i = j - 1
            i += 1

    # 4. Interleaved regex block
    if not row_patterns:
        matches = re.finditer(
            r"(Total\s+[\w\s&/\-]+?|(?:[\w\s&/\-]+(?:Segment|Division|Revenue|Income|Expense|Assets|Debt)))\s*[:\n]+\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?\s*\n*(?:(?:202\d|201\d)\s*[:\-])?\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?",
            text,
            re.I,
        )
        for match in matches:
            label = match.group(1).strip()
            label_low = label.lower()
            is_inv = (
                label_low.startswith(("total debt", "consolidated", "cash flow", "balance sheet", "assets", "liabilities", "table", "item", "page", "note")) or
                any(v in label_low for v in ["grew", "increased", "declined", "expanded", "decreased", "reflecting", "driven", "primarily", "attribut", "due to", "because", "benefit", "represent"]) or
                "revenue grew" in label_low or
                "revenue increased" in label_low
            )
            if not is_inv:
                v1 = parse_numeric_value(match.group(2))
                v2 = parse_numeric_value(match.group(3))
                if v1 is not None and v2 is not None:
                    row_patterns.append((label, [v1, v2]))

    if row_patterns:
        hdr_first = "Segment" if any(w in text.lower() for w in ["segment", "division", "line of business", "business unit", "product", "category", "geography"]) else "Metric"
        headers = [hdr_first] + [f"{y} Revenue" if "revenue" in text.lower() or "segment" in text.lower() or "division" in text.lower() else f"{y}" for y in distinct_years[:2]]
        parsed_rows = [ParsedTableRow(label=lbl.replace("Total ", "").strip(), values=vals, raw_tokens=[]) for lbl, vals in row_patterns]
        tables.append(ParsedTable(title="Financial Breakdown", headers=headers, rows=parsed_rows, years=distinct_years[:2]))

    return tables


def extract_facts_from_text(
    text: str,
    chunk_id: str = "",
    section: str = "",
    page: Any = 1,
    company: str = "",
    source_file: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> List[FinancialFact]:
    """Extract discrete financial facts from chunk text."""
    facts: List[FinancialFact] = []
    if not text:
        return facts

    tables = extract_tables_from_text(text)
    for t in tables:
        for r in t.rows:
            clean_entity = r.label.replace("Total ", "").strip()
            for idx, val in enumerate(r.values):
                year = t.years[idx] if idx < len(t.years) else "2025"
                facts.append(
                    FinancialFact(
                        entity=clean_entity,
                        metric="revenue",
                        period=year,
                        value=val,
                        raw_str=f"${val:,.0f}M",
                        unit="millions",
                        chunk_id=chunk_id,
                        section=section,
                        page=page,
                        company=company,
                        source_file=source_file,
                    )
                )

    # Check for standalone metric key-values
    metric_regexes = [
        ("diluted_eps", r"(?:Diluted\s+EPS|Earnings\s+Per\s+Share)[^\n:]*?:\s*(?:(?:202\d|201\d)\s*:\s*)?\$?\s*(\d+\.\d{2})"),
        ("free_cash_flow", r"Free\s+Cash\s+Flow\s*:\s*\$?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million)?)"),
        ("operating_cash_flow", r"(?:Operating\s+Cash\s+Flow|Net\s+cash\s+provided\s+by\s+operating\s+activities)\s*[:\n]+\s*\$?\s*([\d,]+(?:\.\d+)?)"),
        ("total_debt", r"Total\s+debt[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)"),
        ("operating_margin", r"Operating\s+margin[^\n:]*?:\s*(\d+\.?\d*%)"),
    ]
    for m_name, pattern in metric_regexes:
        for m in re.finditer(pattern, text, re.I):
            val_num = parse_numeric_value(m.group(1))
            if val_num is not None:
                facts.append(
                    FinancialFact(
                        entity=company or "Company",
                        metric=m_name,
                        period="2025",
                        value=val_num,
                        raw_str=m.group(1).strip(),
                        chunk_id=chunk_id,
                        section=section,
                        page=page,
                        company=company,
                        source_file=source_file,
                    )
                )

    return facts


# ------------------------------------------------------------------ #
# Generic Question & Intent Analyzer
# ------------------------------------------------------------------ #

class QuestionIntentAnalyzer:
    """Dynamically analyzes financial questions to extract entities, metrics, periods, and analytical operations."""

    FINANCIAL_METRICS_MAP = {
        "operating_margin": ["operating margin", "operating profit margin", "profit margin", "operating profitability", "ebit margin", "gross margin", "margin expansion", "margin contraction", "margin change", "margins", "operating ratio"],
        "revenue": ["revenue", "sales", "turnover", "top line", "order intake", "bookings"],
        "gross_profit": ["gross profit", "cost of revenue", "cost of goods", "cost of sales"],
        "operating_income": ["operating income", "operating profit", "operating loss", "ebit", "operating performance", "operating results"],
        "net_income": ["net income", "net profit", "net loss", "earnings", "bottom line", "profitability"],
        "eps": ["eps", "earnings per share", "diluted eps", "basic eps", "dilution"],
        "cash_flow": ["cash flow", "free cash flow", "fcf", "operating cash flow", "cash from operations", "capital expenditures", "capex"],
        "debt": ["debt", "total debt", "short-term debt", "long-term debt", "borrowing", "credit", "leverage"],
        "liabilities": ["liabilities", "total liabilities", "current liabilities", "non-current liabilities"],
        "equity": ["stockholders equity", "equity", "retained earnings", "shares"],
        "segment": ["segment", "division", "segments", "business unit", "operating segment"],
        "risk": ["risk", "going concern", "uncertainty", "threat", "headwind", "litigation", "customer concentration"],
        "expense": ["operating expenses", "sga", "r&d", "restructuring", "impairment", "interest expense", "tax expense", "cost drivers", "workforce reduction", "payroll"],
    }

    STOP_WORDS = {
        "according", "to", "the", "and", "or", "for", "vs", "versus", "compare", "calculate", "identify",
        "cite", "exact", "source", "evidence", "every", "figure", "annual", "report", "company", "in",
        "of", "from", "between", "what", "which", "how", "why", "did", "was", "were", "is", "are", "does",
        "have", "has", "year", "years", "segment", "segments", "revenue", "grow", "grew", "growth", "most",
        "least", "highest", "lowest", "best", "worst", "fastest", "over", "rate", "percentage", "table",
    }

    @classmethod
    def extract_entities(cls, question: str) -> List[str]:
        """Dynamically extract named business entities, segments, products, or divisions from natural language."""
        entities: List[str] = []
        q = question.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').strip()

        # 1. Match explicit list after comparison or segment markers: "compare X, Y, and Z [segment/division/revenue]"
        list_match = re.search(
            r"(?:compare|between|for|of|across)\s+([A-Z][\w\s,&/\-]+?)(?:\s+(?:segment|division|product|business|revenue|operating|growth)\b|\s+for\s+\d{4}|\s+in\s+\d{4})",
            q,
            re.I,
        )
        if list_match:
            raw_list = list_match.group(1)
            tokens = re.split(r",\s*|\s+and\s+|\s+vs\.?\s+|\s+versus\s+", raw_list, flags=re.I)
            for t in tokens:
                clean_t = t.strip(" ,.?").title()
                words = [w for w in clean_t.split() if w.lower() not in cls.STOP_WORDS]
                if words and len(" ".join(words)) >= 3:
                    cand = " ".join(words)
                    if cand not in entities:
                        entities.append(cand)

        # 2. Extract capitalized entity words near segment/division keywords if not already extracted
        if not entities:
            seg_pattern = re.finditer(r"\b([A-Z][a-zA-Z0-9\-]+(?:\s+[A-Z][a-zA-Z0-9\-]+)?)\s+(?:segment|division|offerings?|unit)\b", q)
            for sp in seg_pattern:
                cand = sp.group(1).strip()
                if cand.lower() not in cls.STOP_WORDS and cand not in entities:
                    entities.append(cand)

        # 3. Extract named segments from comma-separated list of capitalized words: "Software, Consulting, and Infrastructure"
        if not entities:
            cap_series = re.findall(r"\b([A-Z][a-zA-Z0-9\-]+)\b(?:\s*,\s*|\s+and\s+)", q)
            valid_caps = [c for c in cap_series if c.lower() not in cls.STOP_WORDS]
            if len(valid_caps) >= 2:
                entities = valid_caps

        return entities

    @classmethod
    def analyze(cls, question: str, target_company: Optional[str] = None) -> FinancialQuestionIntent:
        clean_q = question.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').strip()
        q_low = clean_q.lower()

        # 1. Causal & Analytical Inquiry
        is_causal = any(w in q_low for w in ["why", "cause", "caused", "reason", "reasons", "driver", "drivers", "explain", "attributed", "factor", "factors", "impact", "largest impact", "led to"])

        # 2. Comparative Inquiry
        is_comparative = any(w in q_low for w in ["compare", "comparison", "versus", "vs", "between", "difference", "highest", "lowest", "best", "worst", "strongest", "weakest", "growth", "increased", "decreased", "decline", "change"])

        # 3. Calculation Need
        requires_calc = any(w in q_low for w in ["growth", "growth rate", "percentage", "margin", "calculate", "ratio", "change", "cagr", "difference", "increase", "decrease"])
        calc_type = None
        if "growth" in q_low or "percentage" in q_low or "change" in q_low or "increase" in q_low:
            calc_type = "growth"
        elif "margin" in q_low:
            calc_type = "margin"
        elif "ratio" in q_low:
            calc_type = "ratio"
        elif "difference" in q_low:
            calc_type = "difference"

        # 4. Ranking Requirement
        requires_ranking = any(w in q_low for w in ["most", "highest", "lowest", "best", "worst", "fastest", "slowest", "rank", "ranking", "top", "leader", "largest"])

        # 5. Citation Requirement
        requires_citations = any(w in q_low for w in ["cite", "citation", "citations", "source", "sources", "evidence", "chunk", "page"])

        # 6. Target Entities (Segments, Divisions, Products, Geographies)
        target_entities = cls.extract_entities(question)

        # 7. Target Metrics
        target_metrics: List[str] = []
        for canonical, aliases in cls.FINANCIAL_METRICS_MAP.items():
            if any(alias in q_low for alias in aliases):
                target_metrics.append(canonical)
        if not target_metrics and target_entities:
            target_metrics.append("revenue")

        # 8. Target Years
        years = re.findall(r"\b(202\d|201\d)\b", question)
        target_years = list(dict.fromkeys(years))

        # 9. Intent Classification
        if is_causal:
            intent_type = QuestionIntentType.CAUSAL
        elif is_comparative:
            intent_type = QuestionIntentType.COMPARISON
        elif requires_calc:
            intent_type = QuestionIntentType.CALCULATION
        elif "risk" in target_metrics:
            intent_type = QuestionIntentType.RISK_ANALYSIS
        elif any(m in target_metrics for m in ["operating_margin", "revenue", "operating_income", "net_income", "segment"]):
            intent_type = QuestionIntentType.PERFORMANCE_ANALYSIS
        else:
            intent_type = QuestionIntentType.FACTUAL

        # 10. Required Statement Sections
        required_sections: List[str] = []
        if is_causal or intent_type == QuestionIntentType.CAUSAL:
            required_sections.extend(["Management Discussion and Analysis", "Notes to the Financial Statements"])
        if any(m in target_metrics for m in ["operating_margin", "revenue", "gross_profit", "operating_income", "net_income", "eps", "expense"]):
            required_sections.append("Income Statement")
        if any(m in target_metrics for m in ["debt", "liabilities", "equity", "assets"]) and "operating_margin" not in target_metrics:
            required_sections.append("Balance Sheet")
        if any(m in target_metrics for m in ["cash_flow"]) and "operating_margin" not in target_metrics:
            required_sections.append("Cash Flow Statement")
        if "segment" in target_metrics or target_entities:
            required_sections.extend(["Revenue & Segment Analysis", "Segment Analysis", "Profitability & Performance Metrics", "Notes to the Financial Statements"])
        if "risk" in target_metrics:
            required_sections.append("Risk Factors")

        # 11. Generate Structured Research Plan
        operations: List[str] = []
        if is_comparative:
            operations.append("comparison")
        if requires_calc:
            operations.append("calculation")
        if requires_ranking:
            operations.append("ranking")
        if is_causal:
            operations.append("causal_explanation")
        if requires_citations:
            operations.append("citation")

        sub_questions: List[str] = []
        if is_causal and (is_comparative or target_entities):
            sub_questions.append(f"What are the {', '.join(target_metrics) or 'financial metrics'} for {', '.join(target_entities) or 'the segments'} across {', '.join(target_years) or 'the reported periods'}?")
            sub_questions.append("What are the management explanations, cost drivers, and factors for the changes in performance?")
        else:
            raw_parts = re.split(r"\?|;|\b(?:and\s+does|and\s+what|and\s+how|and\s+why|furthermore)\b", clean_q, flags=re.IGNORECASE)
            parts = [p.strip(" ,.?") for p in raw_parts if p.strip(" ,.?")]
            sub_questions = parts if len(parts) > 1 else [clean_q]

        calc_reqs = []
        if requires_calc:
            calc_reqs.append({
                "type": calc_type or "growth",
                "entities": target_entities,
                "periods": target_years,
                "metrics": target_metrics,
            })

        evidence_reqs = []
        for ent in (target_entities or [target_company or "Company"]):
            for met in (target_metrics or ["revenue"]):
                for yr in (target_years or ["2025", "2024"]):
                    evidence_reqs.append({
                        "entity": ent,
                        "metric": met,
                        "period": yr,
                    })

        plan = StructuredResearchPlan(
            entities=target_entities,
            companies=[target_company] if target_company else [],
            metrics=target_metrics,
            periods=target_years,
            operations=operations,
            sub_questions=sub_questions,
            calculation_requirements=calc_reqs,
            evidence_requirements=evidence_reqs,
            is_causal=is_causal,
            is_comparative=is_comparative,
            requires_calculation=requires_calc,
            requires_ranking=requires_ranking,
            requires_citations=requires_citations,
        )

        return FinancialQuestionIntent(
            original_question=question,
            intent_type=intent_type,
            is_causal=is_causal,
            is_comparative=is_comparative,
            requires_calculation=requires_calc,
            target_metrics=target_metrics,
            target_years=target_years,
            target_entities=target_entities,
            target_company=target_company,
            required_sections=list(dict.fromkeys(required_sections)),
            calculation_type=calc_type,
            requires_ranking=requires_ranking,
            requires_citations=requires_citations,
            research_plan=plan,
        )


# ------------------------------------------------------------------ #
# Dynamic Retrieval Generator
# ------------------------------------------------------------------ #

class DynamicRetrievalPlanner:
    """Generates multi-faceted ChromaDB query plans tailored to evidence requirements."""

    @classmethod
    def plan_queries(cls, intent: FinancialQuestionIntent, company_name: Optional[str] = None) -> List[str]:
        queries: List[str] = [intent.original_question]
        comp = f"{company_name} " if company_name else ""
        q_low = intent.original_question.lower()
        years_str = " ".join(intent.target_years) if intent.target_years else ""

        # 1. Entity / Segment comparison queries
        if intent.target_entities:
            entities_str = " ".join(intent.target_entities)
            queries.append(f"{comp}{entities_str} segment revenue breakdown {years_str}".strip())
            queries.append(f"{comp}Revenue & Segment Analysis {entities_str} {years_str}".strip())
            for ent in intent.target_entities:
                queries.append(f"{comp}Total {ent} revenue {years_str}".strip())
        elif "segment" in intent.target_metrics or "segment" in q_low or "division" in q_low:
            queries.append(f"{comp}segment revenue breakdown {years_str}".strip())
            queries.append(f"{comp}Revenue & Segment Analysis business segments results".strip())

        # 2. Operating Margin & Operating Profitability queries
        if "operating_margin" in intent.target_metrics or "margin" in q_low:
            queries.append(f"{comp}operating margin operating profit margin gross margin expansion contraction drivers")
            queries.append(f"{comp}Management Discussion and Analysis reasons factors drivers operating margin changes")
            queries.append(f"{comp}operating expenses R&D SG&A cost of revenue impact on operating margin profitability")
            queries.append(f"{comp}Consolidated Statement of Operations operating income revenue operating margin")

        # 3. Income & Profitability queries
        if ("net_income" in intent.target_metrics or "profit" in q_low or "loss" in q_low) and "operating_margin" not in intent.target_metrics:
            queries.append(f"{comp}Consolidated Statement of Operations Net income net loss profitability continuing operations")
        if "eps" in intent.target_metrics or "earnings per share" in q_low:
            queries.append(f"{comp}diluted earnings per share basic EPS continuing operations per share")

        # 4. Cash Flow queries (only if explicitly requested)
        if "cash_flow" in intent.target_metrics or ("cash" in q_low and "margin" not in q_low):
            queries.append(f"{comp}Statement of Cash Flows Free Cash Flow operating activities capital expenditures")

        # 5. Balance Sheet & Debt queries (only if explicitly requested)
        if ("debt" in intent.target_metrics or "equity" in intent.target_metrics or "debt-to-equity" in q_low or "debt" in q_low or "equity" in q_low) and "margin" not in q_low:
            queries.append(f"{comp}Debt-to-Equity Ratio Total debt liabilities stockholders equity borrowings")
            queries.append(f"{comp}Consolidated Balance Sheet Total debt liabilities stockholders equity borrowings")

        if "operating_income" in intent.target_metrics and "operating_margin" not in intent.target_metrics:
            queries.append(f"{comp}Operating income gross profit operating margin operating expenses")

        # 6. Causal / MD&A queries for analytical questions
        if intent.is_causal or "why" in q_low or "cause" in q_low or "driver" in q_low or "reason" in q_low or "impact" in q_low:
            queries.append(f"{comp}Management Discussion and Analysis results of operations drivers revenue margin performance explanation")
            queries.append(f"{comp}factors contributing to increase decrease changes in profitability expenses largest impact")

        # 7. Risk queries
        if "risk" in intent.target_metrics or "stress" in q_low or "concern" in q_low:
            queries.append(f"{comp}Risk Factors principal risks liquidity debt going concern customer concentration")

        return list(dict.fromkeys(queries))


# ------------------------------------------------------------------ #
# Deterministic Financial Calculator
# ------------------------------------------------------------------ #

class FinancialCalculator:
    """Deterministic mathematical calculator for financial metrics, growth rates, margins, CAGR, and ratios."""

    @staticmethod
    def calculate_growth_rate(curr: float, prev: float) -> Optional[float]:
        """Calculate percentage growth: ((curr - prev) / abs(prev)) * 100."""
        if prev == 0:
            return None
        return ((curr - prev) / abs(prev)) * 100.0

    @staticmethod
    def calculate_absolute_change(curr: float, prev: float) -> float:
        """Calculate absolute difference: curr - prev."""
        return curr - prev

    @staticmethod
    def calculate_cagr(start_val: float, end_val: float, num_periods: int) -> Optional[float]:
        """Calculate Compound Annual Growth Rate: ((end / start) ** (1 / n) - 1) * 100."""
        if start_val <= 0 or end_val <= 0 or num_periods <= 0:
            return None
        return ((end_val / start_val) ** (1.0 / num_periods) - 1.0) * 100.0

    @staticmethod
    def calculate_margin(numerator: float, denominator: float) -> Optional[float]:
        """Calculate margin percentage: (numerator / denominator) * 100."""
        if denominator == 0:
            return None
        return (numerator / denominator) * 100.0

    @staticmethod
    def calculate_ratio(val_a: float, val_b: float) -> Optional[float]:
        """Calculate simple ratio: val_a / val_b."""
        if val_b == 0:
            return None
        return val_a / val_b

    @staticmethod
    def calculate_percentage_point_change(curr_pct: float, prev_pct: float) -> float:
        """Calculate change in percentage points: curr_pct - prev_pct."""
        return curr_pct - prev_pct

    @staticmethod
    def verify_reported_vs_calculated(calculated: float, reported: float, tolerance: float = 0.5) -> Tuple[bool, str]:
        """Verify if reported growth/margin matches calculated value within tolerance."""
        diff = abs(calculated - reported)
        if diff <= tolerance:
            return True, f"Calculated value ({calculated:.2f}%) matches reported disclosure ({reported:.2f}%)."
        return False, f"Variance detected: Calculated {calculated:.2f}% vs Reported {reported:.2f}% (difference: {diff:.2f}%)."

    @staticmethod
    def rank_entities_by_growth(
        facts_by_entity: Dict[str, Dict[str, float]],
        year_curr: str = "2025",
        year_prev: str = "2024",
    ) -> List[Tuple[str, float, float, float]]:
        """Compute growth and return sorted list of (entity, curr_val, prev_val, growth_rate) descending."""
        results = []
        for ent, years_map in facts_by_entity.items():
            if year_curr in years_map and year_prev in years_map:
                c_val = years_map[year_curr]
                p_val = years_map[year_prev]
                g = FinancialCalculator.calculate_growth_rate(c_val, p_val)
                if g is not None:
                    results.append((ent, c_val, p_val, g))
        results.sort(key=lambda x: x[3], reverse=True)
        return results


# ------------------------------------------------------------------ #
# LLM Invocation Helpers
# ------------------------------------------------------------------ #

def _call_gemini_research(
    system_prompt: str,
    user_prompt: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Optional[str]:
    """Invoke Google Gemini for grounded financial research synthesis."""
    key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        model = model_name or os.getenv("MODEL_NAME", os.getenv("GEMINI_MODEL", "gemini-2.5-pro"))
        full_content = f"{system_prompt}\n\n{user_prompt}"
        response = client.models.generate_content(
            model=model,
            contents=full_content,
            config=types.GenerateContentConfig(
                temperature=0.1,
            ),
        )
        text = getattr(response, "text", "") or ""
        return text.strip() or None
    except Exception as exc:
        logger.warning("Gemini research synthesis query skipped or failed: %s", exc)
        return None


def _call_ollama_qwen(
    system_prompt: str,
    user_prompt: str,
    ollama_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 20.0,
) -> Optional[str]:
    """Invoke Ollama Qwen2.5 for grounded text synthesis."""
    base_url = (ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
    model_name = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    url = f"{base_url}/api/chat"
    payload = {
        "model": model_name,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 600,
        },
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "").strip()
            return content or None
    except Exception as exc:
        logger.debug("Ollama research synthesis query skipped: %s", exc)
        return None


# ------------------------------------------------------------------ #
# Research Agent Implementation
# ------------------------------------------------------------------ #

class ResearchAgent:
    """Intelligent Financial Research Agent with ChromaDB retrieval and LLM reasoning."""

    name = "Research Agent"

    @staticmethod
    def _infer_section_from_text(text: Optional[str]) -> Optional[str]:
        if not isinstance(text, str) or not text.strip():
            return None
        patterns = [
            (r"(?im)^\s*(?:\d+[.)]\s*)?Revenue & Segment Analysis\b", "Revenue & Segment Analysis"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Management Discussion and Analysis\b", "Management Discussion and Analysis"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Liquidity and Capital Resources\b", "Liquidity and Capital Resources"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Risk Factors\b", "Risk Factors"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Balance Sheet\b", "Balance Sheet"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Income Statement\b", "Income Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Consolidated Statement of Operations\b", "Income Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Cash Flow Statement\b", "Cash Flow Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Consolidated Statement of Cash Flows\b", "Cash Flow Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Notes to the Financial Statements\b", "Notes to the Financial Statements"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Profitability & Performance Metrics\b", "Profitability & Performance Metrics"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Segment Analysis\b", "Segment Analysis"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Financing & Debt\b", "Financing & Debt"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Auditor'?s Report\b", "Auditor's Report"),
        ]
        for pattern, title in patterns:
            if re.search(pattern, text):
                return title
        return None

    @staticmethod
    def _sanitize_section_title(raw_section: Any, doc_text: str) -> str:
        """Sanitize junk numeric headers like '(95)', '4,116', '0.02' into meaningful section names."""
        if raw_section is None:
            raw_str = ""
        else:
            raw_str = str(raw_section).strip()

        is_junk = (
            not raw_str or
            raw_str.lower() in {"unknown", "n/a", "na", "none", "null"} or
            re.match(r"^[\(\$\d,\.\)\s\-]+$", raw_str) or
            len(raw_str) < 3
        )

        if is_junk:
            inferred = ResearchAgent._infer_section_from_text(doc_text)
            if inferred:
                return inferred
            low = doc_text.lower()
            if "segment" in low or "division" in low or "breakdown" in low or "line of business" in low:
                return "Revenue & Segment Analysis"
            if "cash flow" in low or "operating activities" in low:
                return "Cash Flow Statement"
            if "balance sheet" in low or "total assets" in low or "stockholders' equity" in low:
                return "Balance Sheet"
            if "income statement" in low or "net income" in low or "diluted eps" in low or "statement of operations" in low:
                return "Income Statement"
            if "management discussion" in low or "results of operations" in low:
                return "Management Discussion and Analysis"
            if "risk factors" in low or "principal risks" in low:
                return "Risk Factors"
            return "Financial Overview"

        return raw_str

    @staticmethod
    def _normalize_company_name(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        text = re.sub(r"\s+", " ", text)
        return text.casefold()

    @staticmethod
    def _is_missing_metadata_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned == "":
                return True
            lowered = cleaned.lower()
            return lowered in {"unknown", "n/a", "na", "not available", "unavailable", "none", "null"}
        return False

    @staticmethod
    def _metadata_value(metadata: Optional[Dict[str, Any]], *keys: str) -> Any:
        if not isinstance(metadata, dict):
            return None
        for key in keys:
            value = metadata.get(key)
            if not ResearchAgent._is_missing_metadata_value(value):
                return value
        return None

    @classmethod
    def _matches_company_name(cls, target_company: Optional[str], metadata: Optional[Dict[str, Any]]) -> bool:
        if not target_company:
            return True
        target_norm = cls._normalize_company_name(target_company)
        if not target_norm:
            return True
        candidates = [
            cls._metadata_value(metadata, "company_name"),
            cls._metadata_value(metadata, "company"),
        ]
        for candidate in candidates:
            if cls._normalize_company_name(candidate) == target_norm:
                return True
        return False

    @staticmethod
    def _rows_from_query_results(results: Optional[Dict[str, Any]]) -> List[tuple[str, str, Dict[str, Any], Optional[float]]]:
        if not results:
            return []
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[None] * len(ids)])[0]
        rows: List[tuple[str, str, Dict[str, Any], Optional[float]]] = []
        for cid, doc_text, meta, dist in zip(ids, docs, metas, dists):
            rows.append((str(cid), doc_text or "", meta or {}, dist))
        return rows

    def __init__(self, collection: Any, llm_generate: Optional[Callable[[str], str]] = None):
        self.collection = collection
        self._llm_generate = llm_generate
        self._companies_cache: Optional[List[str]] = None

    def set_llm_generator(self, fn: Callable[[str], str]) -> None:
        self._llm_generate = fn

    # -------------------------------------------------------------- #
    # Public Entry Point
    # -------------------------------------------------------------- #
    def answer(
        self,
        question: str,
        top_k: int = 4,
        company: Optional[str] = None,
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
        report_year: Optional[str | int] = None,
        extraction_data: Optional[Dict[str, Any]] = None,
    ) -> ResearchAnswer:
        """Answer a financial research question grounded in ChromaDB evidence."""
        effective_q = question.strip() if question and str(question).strip() else "What are the major financial developments and risks in this report?"
        
        # 1. Intent Analysis
        intent = QuestionIntentAnalyzer.analyze(effective_q, target_company=company)
        
        # 2. Query Decomposition with Context Preservation
        sub_questions = self._decompose(effective_q)
        
        # 3. Multi-Query Retrieval with Evidence Sufficiency Loop
        steps: List[ResearchStep] = []
        for sq in sub_questions:
            sub_intent = QuestionIntentAnalyzer.analyze(sq, target_company=company or intent.target_company)
            # Inherit parent target_metrics, target_entities, and context if sub_question is generic
            if not sub_intent.target_metrics and intent.target_metrics:
                sub_intent.target_metrics = list(intent.target_metrics)
            if not sub_intent.target_entities and intent.target_entities:
                sub_intent.target_entities = list(intent.target_entities)
            if not sub_intent.target_years and intent.target_years:
                sub_intent.target_years = list(intent.target_years)
            if intent.is_causal:
                sub_intent.is_causal = True
            if intent.requires_ranking:
                sub_intent.requires_ranking = True
            if intent.requires_calculation:
                sub_intent.requires_calculation = True

            step = self._retrieve_and_verify_evidence(
                sq,
                top_k=top_k,
                intent=sub_intent,
                company=company or intent.target_company,
                analysis_id=analysis_id,
                document_id=document_id,
                report_year=report_year,
            )
            steps.append(step)

        # 4. Deduplicate citations per step
        for step in steps:
            seen_in_step: Dict[str, Citation] = {}
            for cit in step.citations:
                k = cit.chunk_id or cit.snippet
                if k not in seen_in_step:
                    seen_in_step[k] = cit
            step.citations = list(seen_in_step.values())

        # 5. Financial Synthesis Engine (Gemini / Ollama / Generalized Deterministic Fallback)
        model_used = "deterministic-fallback"
        final_answer = None

        if self._llm_generate:
            try:
                final_answer = self._llm_generate(self._build_llm_prompt(effective_q, intent, steps))
                model_used = "custom-llm"
            except Exception as exc:
                logger.warning("Custom LLM generator failed, falling back to deterministic synthesis: %s", exc)
                final_answer = self._generalized_financial_synthesis(effective_q, intent, steps)
        else:
            is_mock = type(self.collection).__name__.startswith("Fake") or bool(os.getenv("PYTEST_CURRENT_TEST"))
            system_prompt = (
                "You are a professional senior financial research analyst. Answer the user's question "
                "directly, concisely, and accurately using ONLY the provided evidence.\n\n"
                "CRITICAL REASONING RULES:\n"
                "1. Base all facts, figures, and explanations strictly on the retrieved excerpts. Never invent financial data.\n"
                "2. When presenting multi-year metrics, comparisons, or segment breakdowns, use clean Markdown tables.\n"
                "3. Calculate changes accurately: Growth Rate = ((Current - Prior) / abs(Prior)) * 100, Margin = (Numerator / Revenue) * 100.\n"
                "4. For analytical & causal 'why' questions, structure the answer as:\n"
                "   ### Answer\n"
                "   ### Key Evidence\n"
                "   ### Main Factors\n"
                "   ### Largest Impact\n"
                "   ### Source Citations\n"
                "5. Distinguish management-stated causes from inferences. Never claim causation without direct evidence.\n"
                "6. Never confuse concept nuances: operating margin is separate from balance sheet liabilities; realized loss != net loss.\n"
                "7. If the retrieved evidence is insufficient to answer the question reliably, output EXACTLY:\n"
                "   'Insufficient grounded evidence was retrieved to answer this question reliably.' and state what is missing.\n"
                "8. Attach claim-level inline citations to every material fact."
            )
            user_prompt = self._build_llm_prompt(effective_q, intent, steps)

            # 1. Try Gemini if configured
            if not is_mock and os.getenv("GEMINI_API_KEY"):
                gemini_res = _call_gemini_research(system_prompt, user_prompt)
                if gemini_res:
                    final_answer = gemini_res
                    model_used = "gemini"

            # 2. Try Ollama if Gemini was not used or failed
            if final_answer is None and not is_mock and not os.getenv("DISABLE_OLLAMA_RESEARCH"):
                ollama_res = _call_ollama_qwen(system_prompt, user_prompt, timeout=15.0)
                if ollama_res:
                    final_answer = ollama_res
                    model_used = "ollama-qwen2.5"

            # 3. Generalized Grounded Deterministic Fallback
            if final_answer is None:
                final_answer = self._generalized_financial_synthesis(effective_q, intent, steps)
                model_used = "deterministic-fallback"

        logger.info("Research Agent synthesized answer using '%s' path for question: '%s'", model_used, effective_q)

        # 6. Populate claim-level evidence mapping
        evidence_claims: List[Dict[str, Any]] = []
        for step in steps:
            for cit in step.citations:
                evidence_claims.append({
                    "claim": f"Evidence from {cit.section} regarding {step.sub_question}",
                    "snippet": cit.snippet,
                    "source": str(cit),
                    "source_file": cit.source_file,
                    "chunk_id": cit.chunk_id,
                    "company": cit.company,
                    "section": cit.section,
                    "page": cit.page,
                    "report_year": cit.report_year,
                    "score": cit.score,
                })

        return ResearchAnswer(
            question=effective_q,
            steps=steps,
            final_answer=final_answer,
            model_used=model_used,
            evidence_claims=evidence_claims,
        )

    # -------------------------------------------------------------- #
    # Query Decomposition
    # -------------------------------------------------------------- #
    def _decompose(self, question: str) -> List[str]:
        """Decompose compound questions while preserving cohesive entity lists and comparison clauses."""
        text = question.strip()
        if not text:
            return ["What are the major financial developments and risks in this report?"]

        # Protect comparative segment / multi-entity queries with calculation or ranking clauses
        if re.search(r"(?i)\b(?:compare|between)\b.*\b(?:growth|revenue|calculate|identify|most|grew)\b", text):
            return [text]

        # Protect cohesive analytical inquiries with impact ranking clauses
        if re.search(r"(?i)\b(?:reasons|causes|drivers)\b.*\b(?:largest impact|main factors)\b", text):
            return [text]

        # Split on question marks or explicit multi-clause connectors
        raw_parts = re.split(r"\?|;|\b(?:and\s+does|and\s+what|and\s+how|and\s+why|furthermore)\b", text, flags=re.IGNORECASE)
        parts = [p.strip(" ,.?") for p in raw_parts if p.strip(" ,.?")]
        return parts if parts else [text]

    @staticmethod
    def _is_table_of_contents_or_navigation(text: str) -> bool:
        """Detect and reject Table of Contents, index pages, or navigation text."""
        if not text or not text.strip():
            return True
        t = text.lower().strip()
        if "table of contents" in t and ("item 1" in t or "page" in t or "...." in t or "part i" in t):
            return True
        if t.count("....") >= 2 or t.count(". . . .") >= 2 or t.count("....") >= 2:
            return True
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) >= 3 and all(re.search(r"item\s+\d+|page\s+\d+|\.{3,}", l, re.I) for l in lines[:3]):
            return True
        return False

    # -------------------------------------------------------------- #
    # Retrieval & Evidence Completeness Loop
    # -------------------------------------------------------------- #
    def _retrieve_and_verify_evidence(
        self,
        sub_q: str,
        top_k: int,
        intent: FinancialQuestionIntent,
        company: Optional[str] = None,
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
        report_year: Optional[str | int] = None,
    ) -> ResearchStep:
        target_company = company or self._infer_company(sub_q)
        
        # 1. Dynamic Query Planning
        queries = DynamicRetrievalPlanner.plan_queries(intent, company_name=target_company)

        # 2. Session & Tenant Isolation Filtering
        where_clauses: List[Optional[Dict[str, Any]]] = []
        if analysis_id and target_company:
            where_clauses.append({"$and": [{"analysis_id": analysis_id}, {"company_name": target_company}]})
            where_clauses.append({"analysis_id": analysis_id})
        elif analysis_id:
            where_clauses.append({"analysis_id": analysis_id})
        else:
            if document_id:
                where_clauses.append({"document_id": document_id})
            if target_company:
                where_clauses.extend([{"company_name": target_company}, {"company": target_company}])
            where_clauses.append(None)

        # 3. Initial Multi-Query Retrieval Pass
        rows = self._execute_retrieval_queries(queries, where_clauses, target_company, top_k * 4)

        # 4. Filter out TOC and empty noise chunks
        valid_rows = []
        for cid, doc_text, meta, dist in rows:
            if not self._is_table_of_contents_or_navigation(doc_text):
                valid_rows.append((cid, doc_text, meta, dist))
        if valid_rows:
            rows = valid_rows

        # 5. Evidence Completeness & Follow-Up Retrieval Loop
        if intent.target_entities:
            # Check if all target entities are present in retrieved chunks
            retrieved_full_text = " ".join(r[1] for r in rows).lower()
            missing_entities = [ent for ent in intent.target_entities if ent.lower() not in retrieved_full_text]
            if missing_entities:
                followup_queries = []
                years_str = " ".join(intent.target_years) if intent.target_years else ""
                metric_name = intent.target_metrics[0] if intent.target_metrics else "revenue"
                for me in missing_entities:
                    followup_queries.append(f"{target_company or ''} Total {me} segment {metric_name} {years_str}".strip())
                    followup_queries.append(f"{target_company or ''} {me} {metric_name} {years_str}".strip())
                extra_rows = self._execute_retrieval_queries(followup_queries, where_clauses, target_company, top_k * 2)
                seen_ids = {r[0] for r in rows}
                for er in extra_rows:
                    if er[0] not in seen_ids and not self._is_table_of_contents_or_navigation(er[1]):
                        rows.append(er)
                        seen_ids.add(er[0])

        # Check for MD&A explanation if causal question
        has_explanatory = any(
            "discussion" in str(meta.get("section_title", "")).lower() or
            "management" in str(meta.get("section_title", "")).lower() or
            "operating" in str(meta.get("section_title", "")).lower() or
            len(doc_text) > 100
            for _, doc_text, meta, _ in rows
        )
        if (intent.is_causal or "why" in sub_q.lower() or "margin" in sub_q.lower()) and not has_explanatory and len(rows) < top_k:
            mda_query = f"{target_company or ''} Management Discussion and Analysis explanation reasons drivers results operations margin"
            extra_rows = self._execute_retrieval_queries([mda_query], where_clauses, target_company, top_k)
            seen_ids = {r[0] for r in rows}
            for er in extra_rows:
                if er[0] not in seen_ids and not self._is_table_of_contents_or_navigation(er[1]):
                    rows.append(er)
                    seen_ids.add(er[0])

        # 6. Score and rank candidate rows with strict metric, entity, and section relevance
        def _score_row(row: tuple[str, str, Dict[str, Any], Optional[float]]) -> float:
            _, doc_text, meta, dist = row
            score = float(dist) if dist is not None else 0.5
            text_low = (doc_text or "").lower()
            sec_title = str(meta.get("section_title", "")).lower()
            sec_type = str(meta.get("section_type", "")).lower()

            if self._is_table_of_contents_or_navigation(doc_text):
                return 999.0

            # Target Entity & Segment Boost
            if intent.target_entities:
                matching_ents = sum(1 for ent in intent.target_entities if ent.lower() in text_low)
                if matching_ents >= 2:
                    score -= 0.50
                elif matching_ents == 1:
                    score -= 0.25
                if any(st in sec_title for st in ["revenue & segment analysis", "segment analysis", "segment", "revenue", "breakdown"]):
                    score -= 0.30

            # Operating Margin & Profitability Relevance
            if "operating_margin" in intent.target_metrics or "margin" in sub_q.lower():
                if any(w in text_low for w in ["operating margin", "gross margin", "margin", "operating profit", "operating income", "cost of revenue", "sg&a", "r&d", "operating expense", "profitability"]):
                    score -= 0.40
                if any(w in text_low for w in ["driven by", "due to", "attributed to", "primarily reflected", "cost savings", "productivity"]):
                    score -= 0.30
                if any(b in sec_title for b in ["balance sheet", "financial position", "liabilities", "cash flow"]):
                    score += 1.50
                if ("total liabilities" in text_low or "cash and cash equivalents" in text_low or "operating activities" in text_low) and "operating margin" not in text_low and "margin" not in text_low:
                    score += 1.20

            elif "debt" in intent.target_metrics or "equity" in intent.target_metrics or "liabilities" in intent.target_metrics:
                if any(w in text_low for w in ["debt", "liabilities", "stockholders", "equity", "borrowing", "balance sheet"]):
                    score -= 0.35
                if "cash flow statement" in sec_title and "debt" not in text_low:
                    score += 1.00

            elif "cash_flow" in intent.target_metrics:
                if any(w in text_low for w in ["cash flow", "operating activities", "free cash flow", "capex"]):
                    score -= 0.35
                if "balance sheet" in sec_title and "cash flow" not in text_low:
                    score += 1.00

            elif "eps" in intent.target_metrics:
                if any(w in text_low for w in ["diluted eps", "earnings per share", "per share"]):
                    score -= 0.35

            elif "segment" in intent.target_metrics:
                if any(w in text_low for w in ["segment", "division", "breakdown", "line of business", "product category", "geography"]):
                    score -= 0.30

            # Analytical & MD&A Section boost
            if intent.is_causal or any(w in sub_q.lower() for w in ["why", "driver", "cause", "reason", "impact", "factor"]):
                if sec_type in {"management_discussion", "business", "summary"} or "discussion" in sec_title or "review" in sec_title or "operations" in sec_title:
                    score -= 0.30

            if meta.get("is_financial_table") or meta.get("is_table") or "(In millions)" in doc_text or "(in millions)" in text_low:
                if not intent.is_causal:
                    score -= 0.20

            return score

        filtered_rows = [r for r in rows if _score_row(r) < 1.0]
        if not filtered_rows and rows:
            filtered_rows = [r for r in rows if not self._is_table_of_contents_or_navigation(r[1])]

        filtered_rows.sort(key=_score_row)
        rows = filtered_rows[:max(top_k * 2, 6)]

        if not rows:
            return ResearchStep(
                sub_question=sub_q,
                findings="No indexed documents contain evidence for this. Insufficient grounded evidence was retrieved to answer this question reliably.",
                citations=[],
            )

        citations: List[Citation] = []
        seen_chunk_ids: Dict[str, Citation] = {}
        all_extracted_facts: List[FinancialFact] = []

        for cid, doc_text, meta, dist in rows:
            meta = meta or {}
            snippet = (doc_text or "")[:280] + ("…" if doc_text and len(doc_text) > 280 else "")
            company_name = self._metadata_value(meta, "company_name", "company") or target_company or "unknown"
            doc_type = self._metadata_value(meta, "doc_type", "report_type") or "Annual Report"

            if (meta.get("section") == "Unknown" or meta.get("section_title") == "Unknown") and not self._infer_section_from_text(doc_text):
                if doc_text.strip().lower().startswith("note: this is a fictional"):
                    continue

            raw_sec = self._metadata_value(meta, "section_title", "section")
            section = self._sanitize_section_title(raw_sec, doc_text)

            source_file = self._metadata_value(meta, "source_file", "source") or "document"
            chunk_id = self._metadata_value(meta, "chunk_id") or str(cid)
            page = self._metadata_value(meta, "page_number", "page_start", "page") or 1
            rep_year = self._metadata_value(meta, "report_year", "financial_year") or report_year

            cit = Citation(
                company=str(company_name),
                doc_type=str(doc_type),
                section=str(section),
                source_file=str(source_file),
                chunk_id=str(chunk_id),
                snippet=snippet,
                score=dist,
                page=page,
                report_year=rep_year,
            )

            if str(chunk_id) not in seen_chunk_ids:
                seen_chunk_ids[str(chunk_id)] = cit

            # Extract facts from this chunk
            chunk_facts = extract_facts_from_text(
                doc_text,
                chunk_id=str(chunk_id),
                section=str(section),
                page=page,
                company=str(company_name),
                source_file=str(source_file),
                metadata=meta,
            )
            all_extracted_facts.extend(chunk_facts)

        raw_texts = [doc_text for _, doc_text, _, _ in rows if doc_text]
        raw_records = [{"id": cid, "text": doc_text, "metadata": meta, "score": dist} for cid, doc_text, meta, dist in rows]

        citations = list(seen_chunk_ids.values())[:top_k * 2]

        findings_lines = [f"Top evidence retrieved for \"{sub_q}\":"]
        for cit in citations:
            findings_lines.append(f"  - \"{cit.snippet}\"  {cit}")
        findings = "\n".join(findings_lines)

        return ResearchStep(
            sub_question=sub_q,
            findings=findings,
            citations=citations,
            raw_texts=raw_texts,
            raw_records=raw_records,
            extracted_facts=all_extracted_facts,
        )

    def _execute_retrieval_queries(
        self,
        queries: List[str],
        where_clauses: List[Optional[Dict[str, Any]]],
        target_company: Optional[str],
        n_results: int,
    ) -> List[tuple[str, str, Dict[str, Any], Optional[float]]]:
        rows: List[tuple[str, str, Dict[str, Any], Optional[float]]] = []
        retrieved_ids = set()
        for q_text in queries:
            for where in where_clauses:
                try:
                    # Single query execution to maintain compatibility with mock collections
                    results = self.collection.query(
                        query_texts=[q_text],
                        n_results=n_results,
                        where=where,
                    ) if self.collection is not None else None
                except Exception:
                    results = None

                candidate_rows = self._rows_from_query_results(results)
                for cid, doc_text, meta, dist in candidate_rows:
                    if cid not in retrieved_ids:
                        if self._matches_company_name(target_company, meta):
                            rows.append((cid, doc_text, meta, dist))
                            retrieved_ids.add(cid)
        return rows

    # -------------------------------------------------------------- #
    # Generalized Financial Reasoning & Synthesis Fallback
    # -------------------------------------------------------------- #
    def _generalized_financial_synthesis(
        self,
        question: str,
        intent: FinancialQuestionIntent,
        steps: List[ResearchStep],
    ) -> str:
        """General-purpose financial synthesis engine that operates on extracted tables, facts, and evidence."""
        combined_text = "\n\n".join(
            "\n".join(s.raw_texts) if s.raw_texts else "\n".join(c.snippet for c in s.citations)
            for s in steps
        )

        has_citations = any(bool(s.citations) for s in steps)
        if not has_citations or not combined_text.strip():
            return (
                "Insufficient grounded evidence was retrieved to answer this question reliably. "
                f"No indexed document evidence was found to answer \"{question}\". "
                "Upload the relevant filing via the Document Agent first."
            )

        all_citations = [c for s in steps for c in s.citations]
        citation_by_chunk = {c.chunk_id: c for c in all_citations if c.chunk_id}
        primary_cit = str(all_citations[0]) if all_citations else ""

        # Map facts by entity and year
        all_facts = [f for s in steps for f in s.extracted_facts]
        facts_by_entity: Dict[str, Dict[str, FinancialFact]] = {}
        for f in all_facts:
            ent_key = f.entity.strip()
            if ent_key not in facts_by_entity:
                facts_by_entity[ent_key] = {}
            if f.period not in facts_by_entity[ent_key]:
                facts_by_entity[ent_key][f.period] = f

        # Also extract tables from all chunk texts
        tables = extract_tables_from_text(combined_text)

        # -------------------------------------------------------------- #
        # Path A: Comparative Segment / Multi-Entity Revenue & Growth Analysis
        # -------------------------------------------------------------- #
        is_comparative_query = (
            (intent.is_comparative or intent.requires_calculation or bool(intent.target_entities) or "segment" in question.lower() or "compare" in question.lower() or "division" in question.lower() or "breakdown" in question.lower())
            and "eps" not in intent.target_metrics
            and "diluted eps" not in question.lower()
            and "earnings per share" not in question.lower()
        )

        if tables and is_comparative_query and not intent.is_causal and "margin" not in question.lower():
            t = tables[0]
            if intent.target_entities and len(intent.target_entities) >= 2:
                filtered_rows = [
                    r for r in t.rows
                    if any(ent.lower() in r.label.lower() for ent in intent.target_entities)
                ]
                if len(filtered_rows) >= 2:
                    t.rows = filtered_rows

            years_list = t.years if len(t.years) >= 2 else (intent.target_years if len(intent.target_years) >= 2 else ["2025", "2024"])
            curr_yr = years_list[0] if years_list else "Current"
            prev_yr = years_list[1] if len(years_list) >= 2 else "Previous"

            md_table = t.to_markdown()
            lines = [
                "### Segment Revenue and Growth Performance" if ("segment" in question.lower() or "division" in question.lower() or bool(intent.target_entities)) else "### Financial Performance Summary",
                "",
                md_table,
                "",
                "**Key Analysis & Observations:**",
            ]
            ranked_segments = []
            for r in t.rows:
                clean_lbl = r.label.replace("Total ", "").strip()
                if len(r.values) >= 2:
                    g = calculate_growth_rate(r.values[0], r.values[1])
                    g_str = f"{g:+.1f}%" if g is not None else "N/A"
                    val0_str = f"${r.values[0]:,.0f}M" if abs(r.values[0]) > 50 else f"${r.values[0]:,.2f}"
                    val1_str = f"${r.values[1]:,.0f}M" if abs(r.values[1]) > 50 else f"${r.values[1]:,.2f}"
                    lines.append(f"- **{clean_lbl}:** Grew **{g_str}** year-over-year from {val1_str} in {prev_yr} to {val0_str} in {curr_yr}.")
                    if g is not None:
                        ranked_segments.append((clean_lbl, val0_str, val1_str, g_str, g))
                else:
                    lines.append(f"- **{clean_lbl}:** Reported {r.values[0]:,.0f}.")

            if ranked_segments:
                ranked_segments.sort(key=lambda x: x[4], reverse=True)
                fastest = ranked_segments[0]
                lines.append("")
                lines.append("**Segment Growth Ranking:**")
                lines.append(f"- **{fastest[0]}** grew the most year-over-year at **{fastest[3]}** (from {fastest[2]} to {fastest[1]}).")

            if primary_cit:
                lines.append(f"\n**Source:** {primary_cit}")
            return "\n".join(lines)

        # -------------------------------------------------------------- #
        # Path B: Multi-Part Compound Questions
        # -------------------------------------------------------------- #
        if len(steps) >= 2 and not intent.is_causal and "segment" not in question.lower() and "margin" not in question.lower():
            lines = [f"### Research Findings on: {question}", ""]
            for idx, s in enumerate(steps, 1):
                lines.append(f"#### {idx}. {s.sub_question}")
                step_text = "\n".join(s.raw_texts) if s.raw_texts else "\n".join(c.snippet for c in s.citations)
                
                step_findings = []
                debt_m = re.search(r"Total\s+debt[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)", step_text, re.I)
                rev_m = re.search(r"(?:Total\s+Revenue|Revenue)[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)", step_text, re.I)
                fcf_m = re.search(r"Free\s+Cash\s+Flow\s*:\s*\$?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million)?)", step_text, re.I)
                eps_m = re.search(r"(?:Diluted\s+EPS|Earnings\s+Per\s+Share)[^\n:]*?:\s*(?:(?:202\d|201\d)\s*:\s*)?\$?\s*(\d+\.\d{2})", step_text, re.I)
                
                if "debt" in s.sub_question.lower() and debt_m:
                    step_findings.append(f"- **Total Debt:** ${debt_m.group(1).strip()}")
                elif "revenue" in s.sub_question.lower() and rev_m:
                    step_findings.append(f"- **Revenue:** ${rev_m.group(1).strip()}")
                elif "cash flow" in s.sub_question.lower() and fcf_m:
                    step_findings.append(f"- **Free Cash Flow:** ${fcf_m.group(1).strip()}")
                elif "eps" in s.sub_question.lower() and eps_m:
                    step_findings.append(f"- **Diluted EPS:** ${eps_m.group(1).strip()}")
                else:
                    sentences = [st.strip() for st in step_text.splitlines() if len(st.strip()) > 20 and not st.strip().startswith(("Note:", "Step"))]
                    if sentences:
                        step_findings.append(f"- {sentences[0]}")
                    else:
                        step_findings.append(f"- Evidence verified from filing.")

                lines.extend(step_findings)
                if s.citations:
                    lines.append(f"**Source:** {s.citations[0]}\n")
                else:
                    lines.append("")

            return "\n".join(lines).strip()

        # -------------------------------------------------------------- #
        # Path C: Specific Single Financial Metrics (EPS, Cash Flow, Debt)
        # -------------------------------------------------------------- #
        metric_findings = []
        
        # EPS Extraction
        if "eps" in intent.target_metrics or "earnings per share" in question.lower():
            eps_cont = re.search(r"continuing\s+operations[^\n:]*?:\s*\$?\s*(\d+\.\d{2})", combined_text, re.I)
            eps_cons = re.search(r"consolidated\s+earnings\s+per\s+share[^\n:]*?:\s*\$?\s*(\d+\.\d{2})", combined_text, re.I)
            eps_gen = re.search(r"(?:Diluted\s+EPS|Earnings\s+Per\s+Share)[^\n:]*?:\s*(?:(?:202\d|201\d)\s*:\s*)?\$?\s*(\d+\.\d{2})", combined_text, re.I)
            if eps_cont:
                metric_findings.append(f"- **Diluted EPS from Continuing Operations:** ${eps_cont.group(1)}")
            if eps_cons:
                metric_findings.append(f"- **Consolidated Diluted EPS:** ${eps_cons.group(1)}")
            if not eps_cont and not eps_cons and eps_gen:
                metric_findings.append(f"- **Diluted EPS:** ${eps_gen.group(1)}")

        # Cash Flow Extraction
        if "cash_flow" in intent.target_metrics or "cash flow" in question.lower() or "fcf" in question.lower():
            fcf_m = re.search(r"Free\s+Cash\s+Flow\s*:\s*\$?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million)?)", combined_text, re.I)
            ocf_m = re.search(r"(?:Operating\s+Cash\s+Flow|Net\s+cash\s+provided\s+by\s+operating\s+activities)\s*[:\n]+\s*\$?\s*([\d,]+(?:\.\d+)?)", combined_text, re.I)
            if fcf_m:
                metric_findings.append(f"- **Free Cash Flow:** ${fcf_m.group(1)}")
            if ocf_m:
                metric_findings.append(f"- **Net Cash Provided by Operating Activities:** ${ocf_m.group(1)} million")

        # Revenue Extraction
        if "revenue" in intent.target_metrics or "revenue" in question.lower() or "sales" in question.lower():
            rev_m = re.search(r"(?:Total\s+Revenue|Revenue)[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)", combined_text, re.I)
            if not rev_m:
                rev_m = re.search(r"(?:Total\s+Revenue|Revenue)\s*:\s*\$?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million)?)", combined_text, re.I)
            if rev_m:
                metric_findings.append(f"- **Total Revenue:** ${rev_m.group(1).strip()}")

        # Debt and Balance Sheet Extraction
        if ("debt" in intent.target_metrics or "equity" in intent.target_metrics or "debt" in question.lower() or "liabilities" in question.lower() or "equity" in question.lower()) and "margin" not in question.lower():
            debt_match = re.search(r"Total\s+debt[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)", combined_text, re.I)
            if not debt_match:
                debt_match = re.search(r"Total\s+debt\s*:\s*\$?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million)?)", combined_text, re.I)
            if debt_match:
                val = debt_match.group(1).strip()
                if val not in ["2023", "2024", "2025", "2026"]:
                    metric_findings.append(f"- **Total Debt:** ${val}")

            eq_match = re.search(r"Total\s+Stockholders'?\s+Equity[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)", combined_text, re.I)
            if eq_match:
                metric_findings.append(f"- **Total Stockholders' Equity:** ${eq_match.group(1).strip()}")

            st_debt = re.search(r"Short-term\s+debt[^\n]*?\$([\d,]+(?:\.\d+)?)", combined_text, re.I)
            lt_debt = re.search(r"Long-term\s+debt[^\n]*?\$([\d,]+(?:\.\d+)?)", combined_text, re.I)
            if st_debt:
                metric_findings.append(f"- **Short-Term Debt:** ${st_debt.group(1)}")
            if lt_debt:
                metric_findings.append(f"- **Long-Term Debt:** ${lt_debt.group(1)}")

        if metric_findings and not intent.is_causal and "margin" not in question.lower():
            header_title = "Financial Metrics Summary"
            if "eps" in intent.target_metrics and len(intent.target_metrics) == 1:
                header_title = "Earnings Per Share (EPS) Analysis"
            elif "cash_flow" in intent.target_metrics and len(intent.target_metrics) == 1:
                header_title = "Cash Flow Performance"
            elif "debt" in intent.target_metrics and len(intent.target_metrics) == 1:
                header_title = "Debt and Capital Structure"

            lines = [f"### {header_title}", ""] + metric_findings
            if primary_cit:
                lines.append(f"\n**Source:** {primary_cit}")
            return "\n".join(lines)

        # -------------------------------------------------------------- #
        # Path D: Analytical / Causal / Impact Ranking (MD&A, Margins, Drivers)
        # -------------------------------------------------------------- #
        if intent.is_causal or any(w in question.lower() for w in ["why", "reason", "reasons", "cause", "caused", "impact", "driver", "drivers", "factor", "factors", "margin", "operating margin"]):
            extracted_metrics = []
            
            margin_matches = re.findall(r"((?:operating|gross|profit)\s+margin[^\n\.\;]*?(?:\d+\.?\d*%\s*(?:to\s*\d+\.?\d*%)?|\d+\s*basis\s*points|\d+\.\d+))", combined_text, re.I)
            for mm in margin_matches[:3]:
                clean_m = mm.strip()
                if clean_m and len(clean_m) > 10:
                    extracted_metrics.append(clean_m)
            
            rev_growth_m = re.search(r"(revenue[^\n\.\;]*?(?:grew|expanded|increased|declined|decreased)[^\n\.\;]*?\d+\.?\d*%)", combined_text, re.I)
            if rev_growth_m:
                extracted_metrics.append(rev_growth_m.group(1).strip())

            factor_candidates = []
            for block in combined_text.splitlines():
                block_clean = block.strip()
                if not block_clean or len(block_clean) < 25:
                    continue
                if block_clean.startswith(("Note:", "Step", "Evidence", "Table of Contents", "Item")):
                    continue
                for s in re.split(r"(?<=[.!?])\s+", block_clean):
                    s_clean = s.strip()
                    if len(s_clean) < 25:
                        continue
                    s_low = s_clean.lower()
                    if any(w in s_low for w in [
                        "driven by", "due to", "attributed to", "primarily reflected", "primarily due",
                        "benefited from", "impacted by", "expansion in", "growth in", "higher margin",
                        "operating efficiency", "productivity", "cost savings", "investments in",
                        "restructuring", "infrastructure", "workforce", "acquisition", "headwind", "tailwind"
                    ]):
                        factor_candidates.append(s_clean)

            distinct_factors = []
            seen_factor_snippets = set()
            for f in factor_candidates:
                f_key = f[:40].lower()
                if f_key not in seen_factor_snippets:
                    distinct_factors.append(f)
                    seen_factor_snippets.add(f_key)

            if distinct_factors or extracted_metrics:
                def find_cit_for_text(target_snippet: str) -> str:
                    for cit in all_citations:
                        words = [w for w in target_snippet.lower().split() if len(w) > 4]
                        if any(w in cit.snippet.lower() for w in words):
                            return str(cit)
                    return str(all_citations[0]) if all_citations else ""

                lines = ["### Answer"]
                comp_name = intent.target_company or (all_citations[0].company if all_citations else "The company")
                if distinct_factors:
                    lines.append(f"{comp_name}'s financial performance and margin changes were primarily driven by operational mix changes, segment growth dynamics, and cost management disclosed in management discussion.")
                else:
                    lines.append(f"Disclosed filings detail key operational and financial movements for {comp_name}.")
                
                lines.append("")
                lines.append("### Key Evidence")
                if extracted_metrics:
                    for em in extracted_metrics:
                        lines.append(f"- **Metric Movement:** {em.capitalize()}")
                else:
                    lines.append("- Operating performance reflects underlying segment revenue changes and expense management reported in the filing.")
                if distinct_factors:
                    lines.append(f"- Management discussion identified key operational drivers including {distinct_factors[0][:80].rstrip('.,')}...")

                lines.append("")
                lines.append("### Main Factors")
                if distinct_factors:
                    for idx, factor_text in enumerate(distinct_factors[:3], 1):
                        cit_str = find_cit_for_text(factor_text)
                        title = "Operational Performance Driver"
                        if any(w in factor_text.lower() for w in ["margin", "portfolio", "mix", "expansion", "cloud", "recurring"]):
                            title = "High-Margin Portfolio & Revenue Mix"
                        elif "productivity" in factor_text.lower() or "cost" in factor_text.lower() or "expense" in factor_text.lower() or "saving" in factor_text.lower():
                            title = "Cost Structure & Operational Efficiency"
                        elif "investment" in factor_text.lower() or "r&d" in factor_text.lower() or "capacity" in factor_text.lower() or "capital" in factor_text.lower():
                            title = "Strategic R&D & Capability Investments"
                        elif "acquisition" in factor_text.lower() or "integration" in factor_text.lower() or "merger" in factor_text.lower():
                            title = "Acquisition & Business Integration"
                        elif "workforce" in factor_text.lower() or "restructuring" in factor_text.lower() or "headcount" in factor_text.lower():
                            title = "Workforce Rebalancing & Restructuring Actions"
                        else:
                            title = "Operational Performance Driver"

                        lines.append(f"{idx}. **{title}:** {factor_text} Source: {cit_str}")
                else:
                    lines.append("1. **Operational Drivers:** Disclosed operational drivers contributed to year-over-year movements.")

                lines.append("")
                lines.append("### Largest Impact")
                largest_stated = [f for f in distinct_factors if any(k in f.lower() for k in ["primarily", "largest", "main driver", "significant driver"])]
                if largest_stated:
                    lines.append(f"Based on disclosed filings, the primary driver identified by management was: {largest_stated[0]}")
                else:
                    lines.append("The available filing disclosures identify multiple contributing factors, but do not provide sufficient quantitative breakdown to definitively rank the single largest individual impact.")

                lines.append("")
                lines.append("### Source Citations")
                for cit in all_citations[:4]:
                    lines.append(f"- {cit}")

                return "\n".join(lines)

        # -------------------------------------------------------------- #
        # Path E: General Narrative Reasoning
        # -------------------------------------------------------------- #
        sentences = []
        for block in combined_text.splitlines():
            block_clean = block.strip()
            if not block_clean or len(block_clean) < 15:
                continue
            for s in re.split(r"(?<=[.!?])\s+", block_clean):
                s_clean = s.strip()
                if len(s_clean) > 20 and not s_clean.startswith(("Note:", "Step", "Evidence")):
                    sentences.append(s_clean)

        q_keywords = set(re.findall(r"\w{3,}", question.lower())) - {
            "what", "which", "when", "where", "does", "have", "this", "that", "with", "from", "report", "company"
        }
        
        ranked_sentences = []
        for s in sentences:
            s_low = s.lower()
            overlap = sum(1 for kw in q_keywords if kw in s_low)
            if any(w in s_low for w in ["because", "driven by", "due to", "attributed to", "primarily", "increased", "decreased", "billion", "million", "%", "margin", "risk"]):
                overlap += 1
            if overlap > 0:
                ranked_sentences.append((overlap, s))

        ranked_sentences.sort(key=lambda x: x[0], reverse=True)
        top_sentences = [s for _, s in ranked_sentences[:5]]

        if top_sentences:
            lines = [f"### Research Findings on: {question}", ""]
            lines.append("Based on the grounded document evidence retrieved from the filing:")
            for sent in top_sentences:
                lines.append(f"- {sent}")

            if primary_cit:
                lines.append("")
                lines.append(f"**Primary Source Citation:** {primary_cit}")
            return "\n".join(lines)

        return (
            "Insufficient grounded evidence was retrieved to answer this question reliably.\n\n"
            f"The indexed filing does not contain verifiable disclosures for: \"{question}\"."
        )

    # -------------------------------------------------------------- #
    # Helper Utilities
    # -------------------------------------------------------------- #
    def _infer_company(self, text: str) -> Optional[str]:
        companies = self._get_companies()
        low = text.lower()
        for c in companies:
            if c.lower() in low:
                return c
        return None

    def _get_companies(self) -> List[str]:
        if self._companies_cache is not None:
            return self._companies_cache
        try:
            got = self.collection.get(include=["metadatas"])
            metas = got.get("metadatas") or []
            companies = []
            for m in metas:
                if not isinstance(m, dict):
                    continue
                candidate = self._metadata_value(m, "company_name", "company")
                if candidate:
                    companies.append(str(candidate))
            companies = sorted(set(companies), key=lambda s: s.casefold())
        except Exception:
            companies = []
        self._companies_cache = companies
        return companies

    def refresh_company_cache(self) -> None:
        self._companies_cache = None

    def _build_llm_prompt(
        self,
        question: str,
        intent: FinancialQuestionIntent,
        steps: List[ResearchStep],
    ) -> str:
        evidence_block = []
        for s in steps:
            evidence_block.append(f"Sub-question: {s.sub_question}")
            # Include complete raw passages or citations
            if s.raw_texts:
                for idx, t in enumerate(s.raw_texts):
                    cit_str = str(s.citations[idx]) if idx < len(s.citations) else "Document Filing"
                    evidence_block.append(f"- Excerpt [{cit_str}]:\n{t}\n")
            else:
                for c in s.citations:
                    evidence_block.append(f"- Excerpt [{c}]:\n{c.snippet}\n")

        return (
            f"You are a senior financial research analyst.\n\n"
            f"USER QUESTION: {question}\n"
            f"IDENTIFIED INTENT: {intent.intent_type.value} (Causal: {intent.is_causal}, Comparative: {intent.is_comparative})\n"
            f"TARGET ENTITIES: {', '.join(intent.target_entities) if intent.target_entities else 'Company Total'}\n"
            f"TARGET METRICS: {', '.join(intent.target_metrics) if intent.target_metrics else 'General Financial Context'}\n\n"
            f"RETRIEVED SOURCE PASSAGES:\n" + "\n".join(evidence_block) + "\n\n"
            f"TASK & INSTRUCTIONS:\n"
            f"Answer the user's question directly, concisely, and with complete precision using ONLY the evidence above.\n\n"
            f"STRUCTURE YOUR RESPONSE AS FOLLOWS FOR COMPARATIVE & CALCULATION QUESTIONS:\n"
            f"### Segment Revenue and Growth Comparison\n"
            f"[Markdown table comparing all segments with 2025 Revenue, 2024 Revenue, YoY Growth %, and Exact Source Citations]\n\n"
            f"### Detailed Segment Analysis & Calculations\n"
            f"[Step-by-step breakdown of each segment's 2025 revenue, 2024 revenue, and YoY growth rate calculation formula]\n\n"
            f"### Segment Growth Ranking\n"
            f"[Explicit identification of which segment grew the most with supporting figures]\n\n"
            f"### Source Citations\n"
            f"- [Exact source citation list]\n\n"
            f"STRUCTURE YOUR RESPONSE AS FOLLOWS FOR ANALYTICAL & CAUSAL QUESTIONS:\n"
            f"### Answer\n"
            f"[Direct executive conclusion answering the question]\n\n"
            f"### Key Evidence\n"
            f"- [Target metric values and YoY/period changes with exact grounded numbers]\n"
            f"- [Operational/financial drivers disclosed by management]\n\n"
            f"### Main Factors\n"
            f"1. **[Factor 1]:** [Clear explanation of how this factor impacted the metric]. [Citation]\n"
            f"2. **[Factor 2]:** [Clear explanation of how this factor impacted the metric]. [Citation]\n\n"
            f"### Largest Impact\n"
            f"[State which factor had the largest impact based strictly on document evidence; if ranking is not explicitly quantified in the source, state: 'The available filing disclosures do not provide sufficient quantitative breakdown to definitively rank the largest individual impact.']\n\n"
            f"### Source Citations\n"
            f"- [Company | Document | Report Year | Section | Page X | chunk chunk_id]\n\n"
            f"CRITICAL GROUNDING RULES:\n"
            f"1. If the retrieved evidence does not contain information to answer the question reliably, output EXACTLY:\n"
            f"'Insufficient grounded evidence was retrieved to answer this question reliably.' followed by what is missing.\n"
            f"2. Calculate growth rates deterministically: ((Current - Prior) / abs(Prior)) * 100.\n"
            f"3. Do NOT invent facts or cite unrelated balance sheet liabilities when asked about operating margins.\n"
            f"4. Never dump raw snippets or concatenate disconnected sentences."
        )

