"""Dynamic Question & Financial Intent Analyzer.

Dynamically discovers entities, financial concepts, metrics, periods, and analytical intents
without relying on rigid routing tables or hardcoded metric if-branches.
Constructs a complete EvidenceRequirementGraph tailored to any financial question.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.orchestration.research_state import EvidenceRequirement, EvidenceRequirementGraph


class QuestionIntentType(str, Enum):
    FACTUAL = "factual"
    COMPARISON = "comparison"
    CAUSAL = "causal"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    RISK_ANALYSIS = "risk_analysis"
    CALCULATION = "calculation"
    MULTI_PART = "multi_part"
    STATEMENT_ANALYSIS = "statement_analysis"


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
    requirement_graph: EvidenceRequirementGraph = field(default_factory=EvidenceRequirementGraph)
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
    """Dynamic intent representation for any financial inquiry."""
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
    requirement_graph: EvidenceRequirementGraph = field(default_factory=EvidenceRequirementGraph)


class QuestionIntentAnalyzer:
    """Semantic question analyzer discovering financial intents, entities, metrics, and requirement graphs."""

    STOP_WORDS = {
        "according", "to", "the", "and", "or", "for", "vs", "versus", "compare", "calculate", "identify",
        "cite", "exact", "source", "evidence", "every", "figure", "annual", "report", "company", "in",
        "of", "from", "between", "what", "which", "how", "why", "did", "was", "were", "is", "are", "does",
        "have", "has", "year", "years", "segment", "segments", "revenue", "grow", "grew", "growth", "most",
        "least", "highest", "lowest", "best", "worst", "fastest", "over", "rate", "percentage", "table",
        "disclosed", "reported", "filing", "filings", "details", "explain", "explanation", "reasons",
    }

    # Semantic concept dictionary for statement & category affinities
    FINANCIAL_CONCEPT_TAXONOMY = {
        "income_statement": [
            "revenue", "sales", "turnover", "top line", "order intake", "bookings", "arr", "rpo",
            "gross profit", "cost of revenue", "cost of sales", "cogs",
            "operating income", "operating profit", "operating loss", "ebit", "ebitda", "adjusted ebitda",
            "operating expense", "sga", "sg&a", "r&d", "research and development", "restructuring",
            "pre-tax income", "net income", "net profit", "net loss", "earnings", "bottom line",
            "eps", "diluted eps", "basic eps", "earnings per share",
            "operating margin", "gross margin", "net margin", "profit margin", "profitability",
        ],
        "balance_sheet": [
            "balance sheet", "assets", "total assets", "current assets", "cash and cash equivalents",
            "marketable securities", "accounts receivable", "dso", "inventory", "goodwill", "intangibles",
            "liabilities", "total liabilities", "current liabilities", "accounts payable", "dpo",
            "debt", "total debt", "short-term debt", "long-term debt", "borrowings", "credit facility",
            "stockholders equity", "total equity", "retained earnings", "shares outstanding", "book value",
            "working capital", "deferred revenue", "covenants", "leverage", "debt-to-equity",
        ],
        "cash_flow": [
            "cash flow", "free cash flow", "fcf", "operating cash flow", "cash from operations",
            "capital expenditures", "capex", "investing cash flow", "financing cash flow",
            "cash conversion", "dividends", "share repurchases", "buybacks",
        ],
        "segment_analysis": [
            "segment", "division", "business unit", "product line", "line of business",
            "geography", "regional", "geographic", "offerings",
        ],
        "mda_narrative": [
            "management discussion", "md&a", "results of operations", "drivers", "reasons",
            "factors", "headwinds", "tailwinds", "operational performance", "cost savings",
            "productivity", "mix shift", "portfolio", "acquisitions", "integration",
        ],
        "risk_factors": [
            "risk", "risk factors", "going concern", "uncertainties", "threats", "litigation",
            "customer concentration", "regulatory", "cybersecurity", "impairment", "contingencies",
        ],
        "footnotes": [
            "note", "notes to financial statements", "accounting policy", "disposition",
            "realized loss", "unrealized loss", "fair value", "restatement", "segment reporting",
        ],
    }

    @classmethod
    def extract_entities(cls, question: str) -> List[str]:
        """Dynamically extract named business entities, segments, products, or divisions."""
        entities: List[str] = []
        q = question.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').strip()

        # 1. Match explicit list after comparison or segment markers or at start of question: "compare X, Y, and Z [segment]" or "X, Y and Z segment"
        list_match = re.search(
            r"(?:(?:compare|between|for|of|across)\s+|^)([A-Z][\w\s,&/\-]+?)(?:\s+(?:segments?|divisions?|products?|business|revenue|operating|growth)\b|\s+for\s+\d{4}|\s+in\s+\d{4})",
            q,
            re.I,
        )
        if list_match:
            raw_list = list_match.group(1)
            tokens = re.split(r",\s*|\s+and\s+|\s+vs\.?\s+|\s+versus\s+", raw_list, flags=re.I)
            for t in tokens:
                stripped = t.strip(" ,.?")
                clean_t = stripped if stripped.isupper() else stripped.title()
                words = [w for w in clean_t.split() if w.lower() not in cls.STOP_WORDS]
                if words and len(" ".join(words)) >= 3:
                    cand = " ".join(words)
                    if cand not in entities:
                        entities.append(cand)

        # 2. Extract capitalized entity words near segment/division keywords if not already extracted
        if not entities:
            seg_pattern = re.finditer(r"\b([A-Z][a-zA-Z0-9\-]+(?:\s+[A-Z][a-zA-Z0-9\-]+)?)\s+(?:segment|division|offerings?|unit|division revenue|segment revenue)\b", q)
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

        # Filter out financial metrics mistakenly captured as business entities
        all_metrics_terms = {
            term.lower()
            for terms in cls.FINANCIAL_CONCEPT_TAXONOMY.values()
            for term in terms
        }
        metric_keywords = {"profit", "income", "revenue", "loss", "expense", "flow", "margin", "debt", "equity", "asset", "liability", "eps", "ebit", "ebitda"}
        clean_entities = []
        for ent in entities:
            ent_low = ent.lower()
            is_metric = ent_low in all_metrics_terms or any(kw in ent_low for kw in metric_keywords)
            if not is_metric:
                clean_entities.append(ent)

        return clean_entities

    @classmethod
    def extract_dynamic_metrics(cls, question: str) -> List[str]:
        """Extract requested financial metrics and concepts dynamically from noun phrases and financial taxonomy."""
        q_low = question.lower()
        metrics: List[str] = []

        # 1. Match against financial taxonomy phrases
        for category, terms in cls.FINANCIAL_CONCEPT_TAXONOMY.items():
            for term in terms:
                pattern = r"\b" + re.escape(term) + r"\b"
                if re.search(pattern, q_low):
                    if term not in metrics:
                        metrics.append(term)

        # 2. Dynamic phrase extraction for unseen phrases like "contract backlog", "cloud ARR", "working capital"
        phrase_matches = re.finditer(
            r"\b(?:total\s+|adjusted\s+|diluted\s+|net\s+|operating\s+|gross\s+|free\s+)?([a-z0-9\-]+(?:\s+[a-z0-9\-]+)?)\s+(?:margin|growth|revenue|income|expense|cost|backlog|arr|rpo|debt|cash|flow|capital|ratio|loss|profit|equity|assets|liabilities|covenants|provisions|rate|yield|cagr|ebitda|retention|turnover|impairment|charges)\b",
            q_low,
        )
        for pm in phrase_matches:
            cand = pm.group(0).strip()
            # Clean leading stop words
            words = cand.split()
            while words and words[0].lower() in cls.STOP_WORDS:
                words.pop(0)
            clean_cand = " ".join(words)
            if clean_cand and clean_cand not in metrics and len(clean_cand) > 2:
                metrics.append(clean_cand)

        return metrics if metrics else ["revenue"]

    @classmethod
    def analyze(cls, question: str, target_company: Optional[str] = None) -> FinancialQuestionIntent:
        clean_q = question.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').strip()
        q_low = clean_q.lower()

        # 1. Causal & Analytical Inquiry Detection
        is_causal = any(w in q_low for w in [
            "why", "cause", "caused", "reason", "reasons", "driver", "drivers", "explain",
            "explanation", "attributed", "factor", "factors", "impact", "largest impact", "led to", "due to",
        ])

        # 2. Comparative Inquiry Detection
        is_comparative = any(w in q_low for w in [
            "compare", "comparison", "versus", "vs", "between", "difference", "highest",
            "lowest", "best", "worst", "strongest", "weakest", "growth", "increased", "decreased", "decline", "change",
        ])

        # 3. Calculation Need
        requires_calc = any(w in q_low for w in [
            "growth", "growth rate", "percentage", "margin", "calculate", "ratio", "change",
            "cagr", "difference", "increase", "decrease", "variance", "basis points", "bps",
        ])
        calc_type = None
        if "growth" in q_low or "percentage" in q_low or "change" in q_low or "increase" in q_low:
            calc_type = "growth"
        elif "margin" in q_low or "basis points" in q_low or "bps" in q_low:
            calc_type = "margin"
        elif "ratio" in q_low or "conversion" in q_low:
            calc_type = "ratio"
        elif "cagr" in q_low:
            calc_type = "cagr"
        elif "difference" in q_low or "variance" in q_low:
            calc_type = "difference"

        # 4. Ranking Requirement
        requires_ranking = any(w in q_low for w in [
            "most", "highest", "lowest", "best", "worst", "fastest", "slowest", "rank", "ranking", "top", "leader", "largest",
        ])

        # 5. Citation Requirement
        requires_citations = any(w in q_low for w in [
            "cite", "citation", "citations", "source", "sources", "evidence", "chunk", "page",
        ])

        # 6. Target Entities (Segments, Divisions, Products, Geographies)
        target_entities = cls.extract_entities(question)

        # 7. Dynamic Target Metrics
        target_metrics = cls.extract_dynamic_metrics(question)
        if not target_metrics and target_entities:
            target_metrics.append("revenue")

        # 8. Target Years / Periods
        years = re.findall(r"\b(202\d|201\d)\b", question)
        target_years = list(dict.fromkeys(years))

        # 9. Required Statement Sections
        required_sections: List[str] = []
        for sec_name, keywords in cls.FINANCIAL_CONCEPT_TAXONOMY.items():
            if any(kw in q_low for kw in keywords):
                if sec_name == "income_statement":
                    required_sections.append("Income Statement")
                elif sec_name == "balance_sheet":
                    required_sections.append("Balance Sheet")
                elif sec_name == "cash_flow":
                    required_sections.append("Cash Flow Statement")
                elif sec_name == "segment_analysis":
                    required_sections.extend(["Revenue & Segment Analysis", "Segment Analysis"])
                elif sec_name == "mda_narrative":
                    required_sections.append("Management Discussion and Analysis")
                elif sec_name == "risk_factors":
                    required_sections.append("Risk Factors")
                elif sec_name == "footnotes":
                    required_sections.append("Notes to the Financial Statements")

        if is_causal:
            required_sections.extend(["Management Discussion and Analysis", "Notes to the Financial Statements"])

        required_sections = list(dict.fromkeys(required_sections))

        # 10. Intent Classification
        if is_causal:
            intent_type = QuestionIntentType.CAUSAL
        elif is_comparative:
            intent_type = QuestionIntentType.COMPARISON
        elif requires_calc:
            intent_type = QuestionIntentType.CALCULATION
        elif any(m in ["risk", "risk factors", "going concern", "uncertainties"] for m in target_metrics):
            intent_type = QuestionIntentType.RISK_ANALYSIS
        elif any(m in ["operating margin", "revenue", "operating income", "net income", "segment"] for m in target_metrics):
            intent_type = QuestionIntentType.PERFORMANCE_ANALYSIS
        else:
            intent_type = QuestionIntentType.FACTUAL

        # 11. Generate Evidence Requirement Graph
        req_graph = EvidenceRequirementGraph()
        req_id_counter = 1

        effective_entities = target_entities or [target_company or "Company"]
        effective_metrics = target_metrics or ["revenue"]
        effective_periods = target_years or ["2025", "2024"]

        for ent in effective_entities:
            for met in effective_metrics:
                for yr in effective_periods:
                    req_graph.add_requirement(
                        EvidenceRequirement(
                            requirement_id=f"REQ-{req_id_counter:03d}",
                            requirement_type="metric_figure",
                            description=f"Quantitative figure for {ent} {met} in period {yr}",
                            entity=ent,
                            metric=met,
                            period=yr,
                            is_mandatory=True,
                        )
                    )
                    req_id_counter += 1

        if is_causal:
            req_graph.add_requirement(
                EvidenceRequirement(
                    requirement_id=f"REQ-{req_id_counter:03d}",
                    requirement_type="management_narrative",
                    description=f"Management discussion and operational explanations for performance and margin drivers",
                    target_section="Management Discussion and Analysis",
                    is_mandatory=True,
                )
            )
            req_id_counter += 1

        # 12. Generate Structured Research Plan
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

        evidence_req_dicts = req_graph.to_dict()

        plan = StructuredResearchPlan(
            entities=target_entities,
            companies=[target_company] if target_company else [],
            metrics=target_metrics,
            periods=target_years,
            operations=operations,
            sub_questions=sub_questions,
            calculation_requirements=calc_reqs,
            evidence_requirements=evidence_req_dicts,
            requirement_graph=req_graph,
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
            required_sections=required_sections,
            calculation_type=calc_type,
            requires_ranking=requires_ranking,
            requires_citations=requires_citations,
            research_plan=plan,
            requirement_graph=req_graph,
        )
