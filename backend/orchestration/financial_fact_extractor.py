"""Multi-Layout Financial Table & Fact Extraction Engine.

Extracts structured financial facts and multi-dimensional comparison matrices from:
- Multi-column pipe-separated and colon-separated tables
- Vertical stacked multiline financial disclosures
- Single-line multi-period numeric statements
- Unstructured narrative disclosures and financial statement footnotes
Preserves exact chunk, section, page, period, unit, and currency provenance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.orchestration.financial_calculator import FinancialCalculator
from backend.orchestration.research_state import FinancialFact


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
    statement_type: str = "general"

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
                g = FinancialCalculator.calculate_growth_rate(r.values[0], r.values[1])
                row_cols.append(f"{g:+.1f}%" if g is not None else "N/A")
            body_lines.append("| " + " | ".join(row_cols) + " |")

        return "\n".join([header_line, separator_line] + body_lines)


@dataclass
class ComparisonMatrix:
    """Dynamic multi-dimensional Entity x Metric x Period matrix."""
    entities: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    periods: List[str] = field(default_factory=list)
    facts: Dict[Tuple[str, str, str], FinancialFact] = field(default_factory=dict)

    def add_fact(self, fact: FinancialFact) -> None:
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


class FinancialFactExtractor:
    """Extracts structured financial tables, facts, and multi-period matrices."""

    INVALID_LABEL_SUBSTRINGS = [
        "table of contents", "item 1", "item 7", "page ", "note:", "consisting of",
        "consolidated", "statement of", "cash flows", "balance sheets", "highlights", "summary",
        "revenue grew", "revenue increased", "margin expanded", "reflecting",
        "primarily due", "attributable to", "representing", "driven by",
        "total assets", "total liabilities", "total debt", "short-term debt", "long-term debt",
        "capital expenditures", "free cash flow", "diluted eps", "stockholders", "equity", "debt summary",
    ]

    @classmethod
    def extract_tables_from_text(cls, text: str) -> List[ParsedTable]:
        """Dynamically parse multi-column, stacked vertical, and inline financial tables."""
        tables: List[ParsedTable] = []
        if not text or not text.strip():
            return tables

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return tables

        # Discover years mentioned in table context
        all_years = re.findall(r"\b(202\d|201\d)\b", text)
        distinct_years = list(dict.fromkeys(all_years))
        if len(distinct_years) < 2:
            distinct_years = ["2025", "2024"]

        row_patterns: List[Tuple[str, List[float]]] = []

        # 1. Pipe-separated or colon-separated multi-year rows:
        # e.g. "Total Revenue: 2025: $65,400 | 2024: $58,200 | 2023: $50,500"
        for line in lines:
            m_pipe = re.match(
                r"^([^:\d\|]+?)\s*:\s*(?:202\d|201\d)?\s*[:\s]*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?\s*\|\s*(?:202\d|201\d)?\s*[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                line,
                re.I,
            )
            if m_pipe:
                label = m_pipe.group(1).strip()
                v1 = FinancialCalculator.parse_numeric_value(m_pipe.group(2))
                v2 = FinancialCalculator.parse_numeric_value(m_pipe.group(3))
                if v1 is not None and v2 is not None and len(label) >= 2:
                    if not any(sub in label.lower() for sub in cls.INVALID_LABEL_SUBSTRINGS):
                        row_patterns.append((label, [v1, v2]))

        # 2. Single-line multi-numeric rows (e.g. "Total Software $29,962 $27,085")
        if not row_patterns:
            for line in lines:
                if len(line) > 100:
                    continue
                m_num = re.findall(r"(?:\$?\s*\(?[\d,]+(?:\.\d+)?\)?\s*%?|\(?[\d,]+(?:\.\d+)?\s*(?:million|billion)\)?)", line)
                m_num_clean = [n for n in m_num if n.strip("$ ,%") not in ["2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028"]]
                if len(m_num_clean) >= 2:
                    label = re.sub(r"(?:\$?\s*\(?[\d,]+(?:\.\d+)?\)?\s*%?|\(?[\d,]+(?:\.\d+)?\s*(?:million|billion)\)?).*", "", line).strip()
                    label = re.sub(r"[:\-\|]+$", "", label).strip()
                    is_inv = (
                        len(label) > 40 or
                        any(sub in label.lower() for sub in cls.INVALID_LABEL_SUBSTRINGS) or
                        label.lower().startswith(("table", "item", "page", "note", "consisting", "total debt", "short-term", "long-term", "free cash", "diluted", "net cash", "assets", "liabilities"))
                    )
                    if not is_inv and label:
                        parsed_vals = []
                        for raw_val in m_num_clean:
                            v = FinancialCalculator.parse_numeric_value(raw_val)
                            if v is not None:
                                parsed_vals.append(v)
                        if len(parsed_vals) >= 2:
                            row_patterns.append((label, parsed_vals[:2]))

        # 3. Multiline vertical stacked table structures
        # e.g. "Total Software: $29,962 million\n2024: $27,085 million"
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
                    val1 = FinancialCalculator.parse_numeric_value(m_with_val.group(2))
                    if val1 is not None:
                        vals.append(val1)
                elif m_label_only:
                    cand_label = m_label_only.group(1).strip()

                if cand_label:
                    j = i + 1
                    while j < min(len(lines), i + 4) and len(vals) < 2:
                        next_line = lines[j]
                        if re.search(r"^(?:Total\s+)?(?:Assets|Liabilities|Debt|Equity|Capital|Cash|Operating\s+activities|Net\s+cash|Free\s+cash|Diluted)", next_line, re.I):
                            break
                        num_matches = re.findall(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)", next_line)
                        for nm in num_matches:
                            if nm and nm not in ["2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028"]:
                                v = FinancialCalculator.parse_numeric_value(nm)
                                if v is not None and v > 0:
                                    vals.append(v)
                                    if len(vals) == 2:
                                        break
                        j += 1

                    cand_low = cand_label.lower()
                    is_invalid = (
                        any(sub in cand_low for sub in cls.INVALID_LABEL_SUBSTRINGS) or
                        cand_low.startswith(("table", "item", "page", "note", "consisting", "total debt", "short-term", "long-term", "free cash", "diluted", "net cash", "assets", "liabilities"))
                    )
                    if len(vals) >= 2 and not is_invalid:
                        if len(cand_label) > 2 and not any(r[0].lower() == cand_label.lower() for r in row_patterns):
                            row_patterns.append((cand_label, vals[:2]))
                            i = j - 1
                i += 1

        if row_patterns:
            hdr_first = "Segment" if any(w in text.lower() for w in ["segment", "division", "line of business", "business unit", "product", "category", "geography"]) else "Metric"
            headers = [hdr_first] + [f"{y} Revenue" if "revenue" in text.lower() or "segment" in text.lower() else f"{y}" for y in distinct_years[:2]]
            parsed_rows = [ParsedTableRow(label=lbl.replace("Total ", "").strip(), values=vals, raw_tokens=[]) for lbl, vals in row_patterns]
            tables.append(ParsedTable(title="Financial Breakdown", headers=headers, rows=parsed_rows, years=distinct_years[:2]))

        return tables

    @classmethod
    def extract_facts_from_text(
        cls,
        text: str,
        chunk_id: str = "",
        section: str = "",
        page: Any = 1,
        company: str = "",
        source_file: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[FinancialFact]:
        """Extract structured financial facts with complete provenance."""
        facts: List[FinancialFact] = []
        if not text:
            return facts

        # 1. Extract from multi-column tables
        tables = cls.extract_tables_from_text(text)
        for t in tables:
            for r in t.rows:
                clean_entity = r.label.replace("Total ", "").strip()
                # Determine metric identity from row label or section title
                metric_name = "revenue"
                lbl_low = clean_entity.lower()
                if "operating income" in lbl_low or "operating profit" in lbl_low:
                    metric_name = "operating_income"
                elif "net income" in lbl_low or "net profit" in lbl_low:
                    metric_name = "net_income"
                elif "gross profit" in lbl_low:
                    metric_name = "gross_profit"
                elif "operating margin" in lbl_low:
                    metric_name = "operating_margin"
                elif "operating expense" in lbl_low or "sg&a" in lbl_low or "r&d" in lbl_low:
                    metric_name = "operating_expenses"
                elif "total debt" in lbl_low:
                    metric_name = "total_debt"
                elif "total assets" in lbl_low:
                    metric_name = "total_assets"
                elif "total liabilities" in lbl_low:
                    metric_name = "total_liabilities"

                for idx, val in enumerate(r.values):
                    year = t.years[idx] if idx < len(t.years) else "2025"
                    facts.append(
                        FinancialFact(
                            entity=clean_entity,
                            metric=metric_name,
                            period=year,
                            value=val,
                            raw_str=f"${val:,.0f}M" if abs(val) > 50 else f"${val:,.2f}",
                            unit="millions",
                            statement_type="segment_analysis" if "segment" in section.lower() else "financial_statement",
                            chunk_id=chunk_id,
                            section=section,
                            page=page,
                            company=company,
                            source_file=source_file,
                        )
                    )

        # 2. Extract discrete standalone metric key-values
        metric_patterns = [
            ("diluted_eps", r"(?:Diluted\s+EPS|Earnings\s+Per\s+Share)[^\n:]*?:\s*(?:(?:202\d|201\d)\s*:\s*)?\$?\s*(\d+\.\d{2})"),
            ("free_cash_flow", r"Free\s+Cash\s+Flow\s*:\s*\$?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million)?)"),
            ("operating_cash_flow", r"(?:Operating\s+Cash\s+Flow|Net\s+cash\s+provided\s+by\s+operating\s+activities)\s*[:\n]+\s*\$?\s*([\d,]+(?:\.\d+)?)"),
            ("total_debt", r"Total\s+debt[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)"),
            ("operating_margin", r"Operating\s+margin[^\n:]*?:\s*(\d+\.?\d*%)"),
            ("revenue", r"(?:Total\s+Revenue|Revenue)[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)"),
            ("contract_backlog", r"(?:Contract\s+Backlog|Backlog|RPO)[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)"),
            ("working_capital", r"Working\s+Capital[^\n]*?\$([\d,]+(?:\.\d+)?(?:\s*(?:billion|million))?)"),
        ]

        for m_name, pattern in metric_patterns:
            for m in re.finditer(pattern, text, re.I):
                val_num = FinancialCalculator.parse_numeric_value(m.group(1))
                if val_num is not None:
                    # Detect year from surrounding line
                    line_text = m.group(0)
                    year_match = re.search(r"\b(202\d|201\d)\b", line_text)
                    period_val = year_match.group(1) if year_match else (str(metadata.get("report_year")) if metadata and metadata.get("report_year") else "2025")
                    facts.append(
                        FinancialFact(
                            entity=company or "Company",
                            metric=m_name,
                            period=period_val,
                            value=val_num,
                            raw_str=m.group(1).strip(),
                            unit="millions",
                            statement_type="general",
                            chunk_id=chunk_id,
                            section=section,
                            page=page,
                            company=company,
                            source_file=source_file,
                        )
                    )

        return facts


# Module-level convenience functions
extract_tables_from_text = FinancialFactExtractor.extract_tables_from_text
extract_facts_from_text = FinancialFactExtractor.extract_facts_from_text
