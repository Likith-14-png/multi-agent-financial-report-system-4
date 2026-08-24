"""Enterprise Multi-Agent Financial Extraction Agent.

Combines Semantic understanding with deterministic financial table parsing,
universal multi-currency detection (INR, USD, EUR, GBP), unit-multiplier detection (crore, lakh, billion, million),
context-driven canonical selection, independent EPS observation models, and multi-factor
matrix evidence traceability.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Metric Synonym & Classification Taxonomy
# ---------------------------------------------------------------------------

METRIC_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "revenue": {
        "canonical_name": "Revenue",
        "aliases": [
            r"\btotal revenues?\b",
            r"\brevenues?\b",
            r"\bnet sales\b",
            r"\bsales\b",
            r"\brevenue from operations\b",
            r"\bturnover\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "gross_profit": {
        "canonical_name": "Gross Profit",
        "aliases": [
            r"\bgross profit\b",
            r"\btotal gross profit\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "operating_income": {
        "canonical_name": "Operating Income",
        "aliases": [
            r"\boperating income\b",
            r"\boperating profit\b",
            r"\boperating earnings\b",
            r"\bincome from operations\b",
            r"\boperating profit \(ebit\)\b",
            r"\boperating result\b",
            r"\boperating loss\b",
            r"\bebit\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "pretax_income": {
        "canonical_name": "Pre-tax Income",
        "aliases": [
            r"\(pre-?tax income\)",
            r"\bpre-?tax income\b",
            r"\bpretax income\b",
            r"\bincome before taxes\b",
            r"\bprofit before tax\b",
            r"\bincome from continuing operations before income taxes\b",
            r"\bpre-tax income from continuing operations\b",
            r"\bearnings before taxes\b",
            r"\bebt\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "net_income": {
        "canonical_name": "Net Income",
        "aliases": [
            r"\bnet income\b",
            r"\bnet profit\b",
            r"\bnet earnings\b",
            r"\bprofit for the year\b",
            r"\bprofit attributable to shareholders\b",
            r"\bnet income attributable to\b",
            r"\bnet loss\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "eps": {
        "canonical_name": "EPS",
        "aliases": [
            r"\bearnings per share from continuing operations - assuming dilution\b",
            r"\bconsolidated earnings per share - assuming dilution\b",
            r"\bdiluted earnings per share\b",
            r"\bbasic earnings per share\b",
            r"\bearnings per share\b",
            r"\bdiluted eps\b",
            r"\bbasic eps\b",
            r"\beps\b",
        ],
        "category": "income_statement",
        "is_per_share": True,
        "is_percent": False,
    },
    "basic_eps": {
        "canonical_name": "Basic EPS",
        "aliases": [
            r"\bbasic earnings per share\b",
            r"\bbasic eps\b",
            r"\bbasic per share\b",
        ],
        "category": "income_statement",
        "is_per_share": True,
        "is_percent": False,
    },
    "diluted_eps": {
        "canonical_name": "Diluted EPS",
        "aliases": [
            r"\bearnings per share from continuing operations - assuming dilution\b",
            r"\bconsolidated earnings per share - assuming dilution\b",
            r"\bdiluted earnings per share\b",
            r"\bdiluted eps\b",
        ],
        "category": "income_statement",
        "is_per_share": True,
        "is_percent": False,
    },
    "trend_eps": {
        "canonical_name": "Performance Trend EPS",
        "aliases": [
            r"\bperformance trend eps\b",
            r"\bperformance-trend eps\b",
            r"\boperating eps\b",
            r"\badjusted eps\b",
            r"\btrend eps\b",
            r"\beps from performance trend\b",
            r"\bperformance trend\b",
        ],
        "category": "income_statement",
        "is_per_share": True,
        "is_percent": False,
    },
    "rd_expense": {
        "canonical_name": "R&D Expense",
        "aliases": [
            r"\bresearch and development expense\b",
            r"\bresearch and development\b",
            r"\br&d expense\b",
            r"\br&d expenditure\b",
            r"\br&d\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "interest_expense": {
        "canonical_name": "Interest Expense",
        "aliases": [
            r"\binterest expense\b",
            r"\binterest on debt\b",
            r"\bfinance costs?\b",
            r"\bcost of financing\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "tax_expense": {
        "canonical_name": "Tax Expense",
        "aliases": [
            r"\bprovision for/\(benefit from\) income taxes\b",
            r"\bprovision for income taxes\b",
            r"\bincome tax expense\b",
            r"\btax expense\b",
            r"\bprovision for taxes\b",
        ],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": False,
    },
    "total_assets": {
        "canonical_name": "Total Assets",
        "aliases": [
            r"\btotal assets\b",
            r"\bassets\b",
        ],
        "category": "balance_sheet",
        "is_per_share": False,
        "is_percent": False,
    },
    "total_liabilities": {
        "canonical_name": "Total Liabilities",
        "aliases": [
            r"\btotal liabilities\b",
            r"\bliabilities\b",
            r"\btotal debt and liabilities\b",
        ],
        "category": "balance_sheet",
        "is_per_share": False,
        "is_percent": False,
    },
    "total_equity": {
        "canonical_name": "Total Equity",
        "aliases": [
            r"\btotal equity\b",
            r"\btotal stockholders'? equity\b",
            r"\btotal shareholders'? equity\b",
            r"\bstockholders'? equity\b",
            r"\bshareholders'? equity\b",
            r"\bequity\b",
        ],
        "category": "balance_sheet",
        "is_per_share": False,
        "is_percent": False,
    },
    "cash_and_equivalents": {
        "canonical_name": "Cash and Cash Equivalents",
        "aliases": [
            r"\bcash, cash equivalents, restricted cash and marketable securities\b",
            r"\bcash, cash equivalents and marketable securities\b",
            r"\bcash and cash equivalents\b",
            r"\bcash and marketable securities\b",
            r"\bcash and cash equivalents at end of period\b",
        ],
        "category": "balance_sheet",
        "is_per_share": False,
        "is_percent": False,
    },
    "total_debt": {
        "canonical_name": "Total Debt",
        "aliases": [
            r"\btotal debt\b",
            r"\btotal borrowings\b",
            r"\bdebt \(short-term and long-term\)\b",
            r"\bshort-term and long-term debt\b",
            r"\blong-term debt and short-term borrowings\b",
            r"\btotal lease liabilities\b",
        ],
        "category": "balance_sheet",
        "is_per_share": False,
        "is_percent": False,
    },
    "operating_cash_flow": {
        "canonical_name": "Cash Flow",
        "aliases": [
            r"\bnet cash generated from operating activities\b",
            r"\bnet cash provided by operating activities\b",
            r"\bnet cash from operating activities\b",
            r"\bcash generated from operations\b",
            r"\bcash flows? from operating activities\b",
            r"\bcash flows? from operations\b",
            r"\boperating cash flow\b",
            r"\bcash flow from operations\b",
            r"\bcash flow\b",
        ],
        "category": "cash_flow",
        "is_per_share": False,
        "is_percent": False,
    },
    "free_cash_flow": {
        "canonical_name": "Free Cash Flow",
        "aliases": [
            r"\bfree cash flow\b",
            r"\badjusted free cash flow\b",
            r"\bfcf\b",
        ],
        "category": "cash_flow",
        "is_per_share": False,
        "is_percent": False,
    },
    "capex": {
        "canonical_name": "Capital Expenditure",
        "aliases": [
            r"\bpayments for property, plant and equipment\b",
            r"\bpurchases of property, plant and equipment\b",
            r"\bcapital expenditures?\b",
            r"\badditions to property, plant and equipment\b",
            r"\bcapex\b",
        ],
        "category": "cash_flow",
        "is_per_share": False,
        "is_percent": False,
    },
    "software_revenue": {
        "canonical_name": "Software Revenue",
        "aliases": [
            r"\btotal software\b",
            r"\bsoftware segment revenue\b",
            r"\bsoftware revenue\b",
            r"\bsoftware segment\b",
            r"\bhybrid cloud software\b",
            r"\bsoftware\b",
        ],
        "category": "segment_metrics",
        "is_per_share": False,
        "is_percent": False,
    },
    "consulting_revenue": {
        "canonical_name": "Consulting Revenue",
        "aliases": [
            r"\btotal consulting\b",
            r"\bconsulting segment revenue\b",
            r"\bconsulting revenue\b",
            r"\bconsulting segment\b",
            r"\bconsulting\b",
        ],
        "category": "segment_metrics",
        "is_per_share": False,
        "is_percent": False,
    },
    "infrastructure_revenue": {
        "canonical_name": "Infrastructure Revenue",
        "aliases": [
            r"\btotal infrastructure\b",
            r"\binfrastructure segment revenue\b",
            r"\binfrastructure revenue\b",
            r"\binfrastructure segment\b",
            r"\bhybrid infrastructure\b",
            r"\binfrastructure\b",
        ],
        "category": "segment_metrics",
        "is_per_share": False,
        "is_percent": False,
    },
}


# ---------------------------------------------------------------------------
# 2. Universal Currency, Unit & Number Parsing Engine
# ---------------------------------------------------------------------------

CURRENCY_SYMBOLS = {
    "INR": ["₹", "Rs.", "Rs", "INR"],
    "USD": ["$", "US$", "USD"],
    "EUR": ["€", "EUR"],
    "GBP": ["£", "GBP"],
    "JPY": ["¥", "JPY"],
    "CHF": ["CHF"],
}

UNIT_MULTIPLIERS = {
    "crore": 10_000_000.0,
    "crores": 10_000_000.0,
    "cr": 10_000_000.0,
    "lakh": 100_000.0,
    "lakhs": 100_000.0,
    "lac": 100_000.0,
    "billion": 1_000_000_000.0,
    "billions": 1_000_000_000.0,
    "bn": 1_000_000_000.0,
    "million": 1_000_000.0,
    "millions": 1_000_000.0,
    "mn": 1_000_000.0,
    "thousand": 1_000.0,
    "thousands": 1_000.0,
    "k": 1_000.0,
}

NUM_PATTERN_STR = r"(?:[+-]?(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3}|\d+)(?:\.\d+)?)"


def extract_table_header_units(text: str) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    header_patterns = [
        (r"(?i)\(\s*₹\s*(?:in\s+)?crores?\s*\)|\(\s*Rs\.?\s*(?:in\s+)?crores?\s*\)|\(\s*in\s+(?:₹|Rs\.?)\s*crores?\s*\)|\(\s*in\s+crores?\s*\)", "INR", "crore"),
        (r"(?i)\(\s*₹\s*(?:in\s+)?lakhs?\s*\)|\(\s*Rs\.?\s*(?:in\s+)?lakhs?\s*\)|\(\s*in\s+lakhs?\s*\)", "INR", "lakh"),
        (r"(?i)\(\s*(?:in\s+)?(?:US\$|\$|USD)\s*billions?\s*\)|\(\s*in\s+billions?\s*\)", "USD", "billion"),
        (r"(?i)\(\s*(?:in\s+)?(?:US\$|\$|USD)\s*millions?\s*\)|\(\s*in\s+millions?\s*\)", "USD", "million"),
        (r"(?i)\(\s*(?:in\s+)?(?:US\$|\$|USD)\s*thousands?\s*\)|\(\s*in\s+thousands?\s*\)", "USD", "thousand"),
        (r"(?i)\(\s*(?:in\s+)?(?:€|EUR)\s*billions?\s*\)", "EUR", "billion"),
        (r"(?i)\(\s*(?:in\s+)?(?:€|EUR)\s*millions?\s*\)", "EUR", "million"),
        (r"(?i)\(\s*(?:in\s+)?(?:£|GBP)\s*millions?\s*\)", "GBP", "million"),
    ]
    for pattern, curr, unit in header_patterns:
        if re.search(pattern, text):
            return curr, unit
    return None, None


def parse_financial_number(
    snippet: str,
    inherited_currency: Optional[str] = None,
    inherited_unit: Optional[str] = None,
    is_per_share: bool = False,
    is_percent: bool = False,
) -> Optional[Dict[str, Any]]:
    if not snippet:
        return None
    cleaned_snippet = snippet.strip()
    if is_percent:
        pct_match = re.search(rf"({NUM_PATTERN_STR})\s*%", cleaned_snippet)
        if pct_match:
            num_val = float(pct_match.group(1).replace(",", ""))
            return {
                "raw_value": f"{pct_match.group(1)}%",
                "numeric_value": num_val,
                "currency": "PERCENT",
                "unit": "percent",
                "unit_multiplier": 0.01,
                "normalized_base_value": num_val * 0.01,
            }
        return None
    detected_currency = inherited_currency
    curr_prefix = ""
    if "₹" in cleaned_snippet:
        detected_currency = "INR"
        curr_prefix = "₹"
    elif re.search(r"\bRs\.?\b", cleaned_snippet, re.I):
        detected_currency = "INR"
        m_rs = re.search(r"\bRs\.?\s*", cleaned_snippet, re.I)
        curr_prefix = m_rs.group(0) if m_rs else "Rs. "
    elif re.search(r"\bINR\b", cleaned_snippet, re.I):
        detected_currency = "INR"
        m_inr = re.search(r"\bINR\s*", cleaned_snippet, re.I)
        curr_prefix = m_inr.group(0) if m_inr else "INR "
    elif re.search(r"US\$", cleaned_snippet, re.I):
        detected_currency = "USD"
        curr_prefix = "$"
    elif "$" in cleaned_snippet:
        detected_currency = "USD"
        curr_prefix = "$"
    elif "€" in cleaned_snippet:
        detected_currency = "EUR"
        curr_prefix = "€"
    elif "£" in cleaned_snippet:
        detected_currency = "GBP"
        curr_prefix = "£"
    elif inherited_currency == "INR":
        detected_currency = "INR"
        curr_prefix = "₹"
    elif inherited_currency == "USD":
        detected_currency = "USD"
        curr_prefix = "$"
    elif inherited_currency == "EUR":
        detected_currency = "EUR"
        curr_prefix = "€"
    elif inherited_currency == "GBP":
        detected_currency = "GBP"
        curr_prefix = "£"
    elif not detected_currency:
        detected_currency = "UNKNOWN"
        curr_prefix = ""
    detected_unit = inherited_unit
    unit_mult = 1.0
    unit_match = re.search(r"\b(crores?|cr|lakhs?|lac|billions?|bn|b|millions?|mn|m|thousands?|k)\b", cleaned_snippet, re.I)
    if unit_match:
        norm_u = unit_match.group(1).lower()
        if norm_u in ("crores", "cr"):
            detected_unit = "crore"
        elif norm_u in ("lakhs", "lac"):
            detected_unit = "lakh"
        elif norm_u in ("billions", "bn", "b"):
            detected_unit = "billion"
        elif norm_u in ("millions", "mn", "m"):
            detected_unit = "million"
        elif norm_u in ("thousands", "k"):
            detected_unit = "thousand"
        else:
            detected_unit = norm_u
        unit_mult = UNIT_MULTIPLIERS.get(detected_unit, 1.0)
    elif detected_unit:
        unit_mult = UNIT_MULTIPLIERS.get(detected_unit, 1.0)
    else:
        detected_unit = "units" if not is_per_share else "per_share"
        unit_mult = 1.0
    # Strip growth rates if parsing monetary metrics
    cleaned_snippet = re.sub(r"(?i)(?:increased|decreased|grew|fell|dropped|rose|up|down)?\s*[-+]?\d+(?:\.\d+)?%\s*(?:to\s*)?", "", cleaned_snippet)
    cleaned_snippet = re.sub(r"[-+]?\d+(?:\.\d+)?%", "", cleaned_snippet)
    curr_anchored_match = re.search(rf"(?:[₹$€£]|Rs\.?\s*|US\$\s*|INR\s*)({NUM_PATTERN_STR})", cleaned_snippet, re.I)
    if curr_anchored_match:
        raw_num_str = curr_anchored_match.group(1)
    else:
        match = re.search(NUM_PATTERN_STR, cleaned_snippet)
        if not match:
            return None
        raw_num_str = match.group(0)
    try:
        numeric_val = float(raw_num_str.replace(",", ""))
    except ValueError:
        return None
    if is_per_share:
        raw_val = f"{curr_prefix}{numeric_val:.2f}" if curr_prefix else f"{numeric_val:.2f}"
    elif detected_unit and detected_unit != "units" and detected_unit != "per_share":
        raw_val = f"{curr_prefix}{raw_num_str} {detected_unit}".strip()
    else:
        raw_val = f"{curr_prefix}{raw_num_str}".strip()
    return {
        "raw_value": raw_val,
        "numeric_value": numeric_val,
        "currency": detected_currency,
        "unit": detected_unit,
        "unit_multiplier": unit_mult,
        "normalized_base_value": numeric_val * unit_mult,
    }


# ---------------------------------------------------------------------------
# 3. Helper Normalizers
# ---------------------------------------------------------------------------

def _normalize_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip(" \t\n\r.;,")
    if cleaned.endswith(")") and cleaned.count("(") < cleaned.count(")"):
        cleaned = cleaned.rstrip(")")
    cleaned = cleaned.strip("'\"")
    return cleaned or None


def _coalesce_metadata(metadata: Optional[Dict[str, Any]], *keys: str) -> Optional[str]:
    if not metadata:
        return None
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _extract_company_name(text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    metadata_value = _coalesce_metadata(metadata, "company_name")
    if metadata_value and str(metadata_value).lower() not in {"unknown", "none", "null", "not found"}:
        name = str(metadata_value).strip()
        return _normalize_value(name)
    patterns = [
        r"(?im)^\s*Company\s*(?:Name)?\s*[:\-]\s*([A-Z][-A-Za-z0-9&. ]+(?:\s*\([-A-Za-z0-9&. ]+\))?)(?:\s*(?:Ltd\.?|Inc\.?|Corp\.?|Corporation|Holdings|Group|PLC|LLC))?\s*$",
        r"(?im)^\s*([A-Z][-A-Za-z0-9&. ]+(?:\s*\([-A-Za-z0-9&. ]+\))?)\s+Annual Report\s+\d{4}\s*$",
        r"(?im)^\s*([A-Z][-A-Za-z0-9&. ]+(?:\s*\([-A-Za-z0-9&. ]+\))?)\s+(?:Ltd\.?|Inc\.?|Corp\.?|Corporation|Holdings|Group|PLC|LLC)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if value and not re.search(r"\b(?:Annual Report|Management Discussion and Analysis|Risk Factors|Balance Sheet|For the year ended)\b", value, re.I):
                return _normalize_value(value)
    return None


def _extract_report_year(text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    metadata_value = _coalesce_metadata(metadata, "report_year", "year", "financial_year")
    if metadata_value and str(metadata_value).lower() not in {"unknown", "none", "null"}:
        return str(metadata_value).strip()
    for pattern in [
        r"(?i)\b(?:for the year ended|year ended|FY|Fiscal year)\s+[A-Za-z]+\s+\d{1,2},?\s+(\d{4})\b",
        r"(?i)\b([12]\d{3})\b(?:\s+Annual Report)?",
    ]:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _normalize_year_value(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = int(value)
        if 1900 <= value <= 2100:
            return value
        return None
    text = str(value).strip()
    if not text:
        return None
    matches = re.findall(r"(?:19|20)\d{2}", text)
    if not matches:
        return None
    year = int(matches[-1])
    return year if 1900 <= year <= 2100 else None


def _canonical_yearly_metric_name(metric_name: str) -> str:
    normalized = metric_name.strip().lower().replace("_", " ")
    aliases = {
        "revenue": "Revenue",
        "total revenue": "Revenue",
        "total revenues": "Revenue",
        "sales": "Revenue",
        "operating income": "Operating Income",
        "operating profit": "Operating Income",
        "income from operations": "Operating Income",
        "operating loss": "Operating Income",
        "gross profit": "Gross Profit",
        "pre-tax income": "Pre-tax Income",
        "pretax income": "Pre-tax Income",
        "income before taxes": "Pre-tax Income",
        "net income": "Net Income",
        "net profit": "Net Income",
        "net loss": "Net Income",
        "total assets": "Total Assets",
        "assets": "Total Assets",
        "total liabilities": "Total Liabilities",
        "liabilities": "Total Liabilities",
        "total equity": "Total Equity",
        "total debt": "Total Debt",
        "cash flow": "Cash Flow",
        "cash flow from operations": "Cash Flow",
        "operating cash flow": "Cash Flow",
        "free cash flow": "Free Cash Flow",
        "r&d expense": "R&D Expense",
        "research and development": "R&D Expense",
        "eps": "EPS",
        "basic eps": "Basic EPS",
        "diluted eps": "Diluted EPS",
        "trend eps": "Performance Trend EPS",
        "earnings per share": "EPS",
        "software": "Software Segment",
        "software revenue": "Software Segment",
        "consulting": "Consulting Segment",
        "consulting revenue": "Consulting Segment",
        "infrastructure": "Infrastructure Segment",
        "infrastructure revenue": "Infrastructure Segment",
    }
    return aliases.get(normalized, metric_name.strip())


# ---------------------------------------------------------------------------
# 4. Multi-Factor Evidence Grounding & Traceability Engine
# ---------------------------------------------------------------------------

def _find_grounded_chunk_for_observation(
    obs: Dict[str, Any],
    chunk_records: List[Dict[str, Any]],
    target_year: Optional[int] = None,
) -> Tuple[Optional[str], int, str, float]:
    if not chunk_records:
        return None, 1, "", 0.0
    raw_val = str(obs.get("raw_value", "")).strip()
    num_val = obs.get("numeric_value")
    num_str = f"{num_val:.2f}".rstrip("0").rstrip(".") if num_val is not None else ""
    raw_digits = re.sub(r"[^\d.]", "", raw_val)
    metric_name = obs.get("metric_name", "")
    spec = METRIC_TAXONOMY.get(metric_name, {})
    aliases = spec.get("aliases", [metric_name])
    category = spec.get("category", "")
    target_year_str = str(target_year) if target_year else str(obs.get("report_year", ""))
    best_chunk_id = None
    best_page = 1
    best_snippet = ""
    best_score = 0.0
    for chunk in chunk_records:
        c_text = chunk.get("text", "")
        if not c_text:
            continue
        c_text_lower = c_text.lower()
        c_meta = chunk.get("metadata", {})
        sec_title = str(c_meta.get("section_title", "")).lower()
        has_num = False
        if raw_val and raw_val.lower() in c_text_lower:
            has_num = True
        elif num_str and num_str in c_text:
            has_num = True
        elif raw_digits and len(raw_digits) >= 2 and raw_digits in re.sub(r"[^\d.]", "", c_text):
            has_num = True
        if not has_num:
            continue
        score = 10.0
        lines = c_text.splitlines()
        found_in_same_line = False
        matching_line = ""
        for line in lines:
            line_lower = line.lower()
            if (num_str and num_str in line) or (raw_digits and raw_digits in re.sub(r"[^\d.]", "", line)) or (raw_val.lower() in line_lower):
                matching_line = line.strip()
                if any(re.search(alias, line, re.I) for alias in aliases):
                    found_in_same_line = True
                    score += 15.0
                    break
        if category == "income_statement" and any(w in sec_title or w in c_text_lower[:150] for w in ["profit", "loss", "income statement", "operations", "financial performance", "p&l"]):
            score += 8.0
        elif category == "balance_sheet" and any(w in sec_title or w in c_text_lower[:150] for w in ["balance sheet", "financial position", "assets", "liabilities"]):
            score += 8.0
        elif category == "cash_flow" and any(w in sec_title or w in c_text_lower[:150] for w in ["cash flow", "cash flows", "operating activities"]):
            score += 8.0
        if target_year_str and target_year_str in c_text:
            score += 5.0
        if any(w in c_text_lower for w in ["scope 1", "scope 2", "greenhouse gas", "learning hours per employee", "carbon emissions", "sustainability initiative"]):
            if metric_name in ["eps", "basic_eps", "diluted_eps", "trend_eps", "total_liabilities", "total_equity", "revenue", "operating_income", "net_income"]:
                score -= 30.0
        if score > best_score and score >= 10.0:
            best_score = score
            best_chunk_id = chunk.get("chunk_id")
            best_page = chunk.get("page_start", 1)
            best_snippet = (matching_line if matching_line else c_text[:200]).replace("\n", " ")
    return best_chunk_id, best_page, best_snippet, best_score


# ---------------------------------------------------------------------------
# 5. Context-Driven Canonical Selection Hierarchy
# ---------------------------------------------------------------------------

def select_canonical_observation(
    observations: List[Dict[str, Any]],
    target_metric: str,
    requested_context: Optional[str] = None,
    target_year: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    candidates = [o for o in observations if o.get("metric_name") == target_metric]
    if not candidates:
        return None
    if requested_context:
        req_lower = requested_context.lower()
        if "standalone" in req_lower:
            standalone_cands = [c for c in candidates if "standalone" in c.get("statement_context", "").lower()]
            if standalone_cands:
                candidates = standalone_cands
        elif "segment" in req_lower:
            segment_cands = [c for c in candidates if "segment" in c.get("statement_context", "").lower()]
            if segment_cands:
                candidates = segment_cands
        elif "consolidated" in req_lower:
            consol_cands = [c for c in candidates if "consolidated" in c.get("statement_context", "").lower() or "audited" in c.get("statement_context", "").lower()]
            if consol_cands:
                candidates = consol_cands
    if target_year:
        year_matched = [c for c in candidates if c.get("report_year") == target_year]
        if year_matched:
            candidates = year_matched
    def _rank_candidate(cand: Dict[str, Any]) -> tuple:
        ctx = cand.get("statement_context", "").lower()
        auth_rank = 3 if any(w in ctx for w in ["audited", "income_statement", "balance_sheet", "cash_flow"]) else (2 if "segment" in ctx else 1)
        curr = cand.get("currency", "")
        curr_rank = 2 if curr != "USD" or ("USD" in curr and "translated" not in ctx) else 1
        has_chunk = 1 if cand.get("source_chunk_id") else 0
        return (auth_rank, curr_rank, has_chunk)
    sorted_candidates = sorted(candidates, key=_rank_candidate, reverse=True)
    return sorted_candidates[0]


# ---------------------------------------------------------------------------
# 6. Multi-Year Financial Table & Narrative Parsing
# ---------------------------------------------------------------------------

def _extract_multi_year_financial_tables(
    text: str,
    chunk_records: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    yearly: Dict[str, List[Dict[str, Any]]] = {}
    observations: List[Dict[str, Any]] = []
    if not text:
        return yearly, observations
    detected_curr, detected_unit = extract_table_header_units(text)
    curr_prefix = "₹" if detected_curr == "INR" else ("$" if detected_curr == "USD" else ("€" if detected_curr == "EUR" else ""))
    table_unit = detected_unit or "million"
    table_curr = detected_curr or "USD"
    table_metric_patterns = [
        ("revenue", "Revenue", r"(?:Total\s+revenue|Revenues?|Revenue\s+from\s+operations)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)"),
        ("gross_profit", "Gross Profit", r"Gross\s+profit\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)"),
        ("operating_income", "Operating Income", r"(?:Operating\s+income|Operating\s+profit|Income\s+from\s+continuing\s+operations|EBIT)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)"),
        ("pretax_income", "Pre-tax Income", r"(?:Income\s+from\s+continuing\s+operations\s+before\s+income\s+taxes|Profit\s+before\s+tax)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)"),
        ("net_income", "Net Income", r"(?:Net\s+income|Profit\s+for\s+the\s+year|Profit\s+attributable\s+to\s+shareholders)\s*\n+\s*[$€£₹]?\s*([\d,]+(?:\.\d+)?)\s*\n+\s*[$€£₹]?([\d,]+(?:\.\d+)?)[^\n]*?\n+\s*([\d,]+(?:\.\d+)?)"),
        ("operating_cash_flow", "Operating Cash Flow", r"(?:Net\s+cash\s+(?:provided\s+by|generated\s+from)\s+operating\s+activities|Cash\s+generated\s+from\s+operations)\s*\n+\s*[$€£₹]?\s*([\d,]+(?:\.\d+)?)\s*\n+\s*[$€£₹]?([\d,]+(?:\.\d+)?)[^\n]*?\n+\s*([\d,]+(?:\.\d+)?)"),
        ("rd_expense", "R&D Expense", r"(?:Research\s+and\s+development|R&D\s+expenditure)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d,]+(?:\.\d+)?)"),
        ("software_revenue", "Software Segment", r"Total\s+Software\s*\n+\s*[$€£₹]?\s*([\d,]+(?:\.\d+)?)\s*\n+\s*[$€£₹]?([\d,]+(?:\.\d+)?)[^\n]*?\n+\s*([\d,]+(?:\.\d+)?)"),
        ("consulting_revenue", "Consulting Segment", r"Total\s+Consulting\s*\n+\s*[$€£₹]?\s*([\d,]+(?:\.\d+)?)\s*\n+\s*[$€£₹]?([\d,]+(?:\.\d+)?)[^\n]*?\n+\s*([\d,]+(?:\.\d+)?)"),
        ("infrastructure_revenue", "Infrastructure Segment", r"Total\s+Infrastructure\s*\n+\s*[$€£₹]?\s*([\d,]+(?:\.\d+)?)\s*\n+\s*[$€£₹]?([\d,]+(?:\.\d+)?)[^\n]*?\n+\s*([\d,]+(?:\.\d+)?)"),
    ]
    for m_key, canonical_label, pattern in table_metric_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            preceding = text[max(0, match.start() - 400):match.start()]
            row_curr, row_unit = extract_table_header_units(preceding)
            effective_curr = row_curr or table_curr
            effective_unit = row_unit or table_unit
            pfx = "₹" if effective_curr == "INR" else ("$" if effective_curr == "USD" else ("€" if effective_curr == "EUR" else ""))
            v25_raw = match.group(1).replace(",", "")
            v24_raw = match.group(2).replace(",", "")
            v23_raw = match.group(3).replace(",", "")
            v25_val = f"{pfx}{match.group(1)} {effective_unit}".strip()
            v24_val = f"{pfx}{match.group(2)} {effective_unit}".strip()
            v23_val = f"{pfx}{match.group(3)} {effective_unit}".strip()
            series = [
                {"year": 2023, "value": v23_val, "numeric_value": float(v23_raw), "unit": f"{effective_unit} {effective_curr}"},
                {"year": 2024, "value": v24_val, "numeric_value": float(v24_raw), "unit": f"{effective_unit} {effective_curr}"},
                {"year": 2025, "value": v25_val, "numeric_value": float(v25_raw), "unit": f"{effective_unit} {effective_curr}"},
            ]
            yearly[canonical_label] = series
            for yr, v_val, num_val in [(2023, v23_val, float(v23_raw)), (2024, v24_val, float(v24_raw)), (2025, v25_val, float(v25_raw))]:
                observations.append({
                    "metric_name": m_key,
                    "canonical_label": canonical_label,
                    "raw_value": v_val,
                    "numeric_value": num_val,
                    "currency": effective_curr,
                    "unit": effective_unit,
                    "statement_context": "income_statement_audited",
                    "report_year": yr,
                    "is_canonical": (yr == 2024 or yr == 2025),
                })
    two_col_table = _extract_table_yearly_metrics_legacy(text)
    for k, v in two_col_table.items():
        if k not in yearly:
            yearly[k] = v
    return yearly, observations


def _extract_table_yearly_metrics_legacy(text: str) -> Dict[str, List[Dict[str, Any]]]:
    if not text:
        return {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    table_start = None
    for idx, line in enumerate(lines):
        if re.search(r"(?i)^Metric\s*(?:FY\d{4}\s+FY\d{4}\s+Change|FY\d{4}\s+FY\d{4}\s+Change)?$", line):
            table_start = idx
            break
        if re.search(r"(?i)^Metric$", line) and idx + 3 < len(lines):
            next_chunk = " ".join(lines[idx: idx + 4])
            if re.search(r"(?i)FY\d{4}.*FY\d{4}.*Change", next_chunk):
                table_start = idx
                break
    if table_start is None:
        return {}
    yearly: Dict[str, List[Dict[str, Any]]] = {}
    metric_match_re = re.compile(r"^(Revenue|Operating Income|Net Income|Total Assets|Total Liabilities|Operating Cash Flow|Cash Flow|EPS)\s*$", re.I)
    header_years: List[int] = []
    for header_line in lines[table_start + 1: min(table_start + 8, len(lines))]:
        if not re.search(r"(?:19|20)\d{2}", header_line):
            continue
        matches = re.findall(r"(?:19|20)\d{2}", header_line)
        for year_text in matches:
            header_years.append(int(year_text))
    for idx in range(table_start + 1, len(lines)):
        match = metric_match_re.match(lines[idx])
        if not match:
            continue
        label = match.group(1)
        canonical = _canonical_yearly_metric_name(label)
        values: List[str] = []
        for offset in range(1, 4):
            candidate = lines[idx + offset].strip() if idx + offset < len(lines) else ""
            if not candidate:
                continue
            if re.search(r"(?i)^\+?[$€£₹]?[-+]?\d[\d,]*\.?\d*\s*(?:billion|million|thousand|crores?|lakhs?|k|bn|m)?$", candidate):
                values.append(candidate)
                if len(values) >= 2:
                    break
        if len(values) >= 2:
            if len(header_years) >= 2:
                paired = [
                    {"year": int(header_years[i]), "value": values[i]}
                    for i in range(2)
                ]
                yearly[canonical] = sorted(paired, key=lambda item: int(item["year"]))
            else:
                yearly[canonical] = [
                    {"year": 2024, "value": values[0]},
                    {"year": 2025, "value": values[1]},
                ]
        elif label.lower() == "operating cash flow" and "Cash Flow" not in yearly:
            fallback_years = [2024, 2025]
            if len(header_years) >= 2:
                fallback_years = [int(header_years[i]) for i in range(2)]
            yearly["Cash Flow"] = [
                {"year": fallback_years[0], "value": values[0] if values else ""},
                {"year": fallback_years[1], "value": values[1] if len(values) > 1 else ""},
            ]
    return yearly


def _extract_field_observations(
    text: str,
    metric_key: str,
    labels: Iterable[str],
    is_per_share: bool = False,
    is_percent: bool = False,
    inherited_currency: Optional[str] = None,
    inherited_unit: Optional[str] = None,
    statement_context: str = "narrative_overview",
    report_year: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if not text:
        return []
    observations: List[Dict[str, Any]] = []
    seen_raw: set = set()
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    spec = METRIC_TAXONOMY.get(metric_key, {})
    aliases = spec.get("aliases", [metric_key])
    for sentence in sentences:
        for alias in aliases:
            match = re.search(rf"{alias}", sentence, flags=re.I)
            if not match:
                continue
            tail = sentence[match.end():]
            parsed = parse_financial_number(
                tail,
                inherited_currency=inherited_currency,
                inherited_unit=inherited_unit,
                is_per_share=is_per_share or spec.get("is_per_share", False),
                is_percent=is_percent or spec.get("is_percent", False),
            )
            if parsed and parsed["raw_value"] not in seen_raw:
                seen_raw.add(parsed["raw_value"])
                obs = dict(parsed)
                obs["metric_name"] = metric_key
                obs["canonical_label"] = spec.get("canonical_name", metric_key.replace("_", " ").title())
                obs["statement_context"] = statement_context
                obs["report_year"] = report_year or 2024
                obs["is_canonical"] = False
                observations.append(obs)
    for alias in aliases:
        pattern = rf"(?i){alias}\s*[:\n\-]+\s*([^\n●]+)"
        for m in re.finditer(pattern, text):
            snippet = m.group(1)
            parsed = parse_financial_number(
                snippet,
                inherited_currency=inherited_currency,
                inherited_unit=inherited_unit,
                is_per_share=is_per_share or spec.get("is_per_share", False),
                is_percent=is_percent or spec.get("is_percent", False),
            )
            if parsed and parsed["raw_value"] not in seen_raw:
                seen_raw.add(parsed["raw_value"])
                obs = dict(parsed)
                obs["metric_name"] = metric_key
                obs["canonical_label"] = spec.get("canonical_name", metric_key.replace("_", " ").title())
                obs["statement_context"] = statement_context
                obs["report_year"] = report_year or 2024
                obs["is_canonical"] = False
                observations.append(obs)
    return observations


def _extract_accounting_notes_and_risks(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    accounting_info: List[Dict[str, Any]] = []
    risk_metrics: List[Dict[str, Any]] = []
    if not text:
        return accounting_info, risk_metrics
    rev_match = re.search(r"(?:Revenue\s+Recognition|Accounting\s+Policy\s+for\s+Revenue)\s*:\s*([^\n●]+(?:\n[^\n●]+){1,4})", text, re.I)
    if rev_match:
        accounting_info.append({
            "category": "Accounting Policy",
            "topic": "Revenue Recognition",
            "summary": rev_match.group(1).strip().replace("\n", " "),
            "evidence": rev_match.group(0)[:300],
        })
    tax_match = re.search(r"(?:Unrecognized\s+Tax\s+Benefits|Tax\s+Contingenc(?:y|ies))\s*:\s*([^\n●]+(?:\n[^\n●]+){1,3})", text, re.I)
    if tax_match:
        raw_snippet = tax_match.group(1).strip().replace("\n", " ")
        parsed = parse_financial_number(raw_snippet)
        amt = parsed["raw_value"] if parsed else None
        accounting_info.append({
            "category": "Tax Contingency",
            "topic": "Unrecognized Tax Benefits",
            "amount": amt,
            "summary": raw_snippet,
            "evidence": tax_match.group(0)[:300],
        })
        if amt:
            risk_metrics.append({
                "category": "Tax Risk",
                "description": "Unrecognized tax benefits under dispute",
                "amount": amt,
            })
    pension_match = re.search(r"(?:Underfunded\s+Pension\s+Plans?|Pension\s+Obligations?|Retirement\s+Benefit\s+Plans?)\s*:\s*([^\n●]+(?:\n[^\n●]+){1,3})", text, re.I)
    if pension_match:
        raw_snippet = pension_match.group(1).strip().replace("\n", " ")
        parsed = parse_financial_number(raw_snippet)
        amt = parsed["raw_value"] if parsed else None
        accounting_info.append({
            "category": "Pension Obligation",
            "topic": "Underfunded Pension Plans",
            "amount": amt,
            "summary": raw_snippet,
            "evidence": pension_match.group(0)[:300],
        })
        if amt:
            risk_metrics.append({
                "category": "Retirement Plans",
                "description": "Net underfunded retirement and postretirement obligations",
                "amount": amt,
            })
    currency_match = re.search(r"(?:foreign\s+currency\s+exchange\s+rates?[^\n●]+?([$€£₹]\s*[\d,.]+\s*(?:billion|million|crore|lakh))|decrease\s+in\s+the\s+fair\s+value\s+of\s+financial\s+instruments\s+of\s+approximately\s+([$€£₹]\s*[\d,.]+\s*(?:billion|million|crore|lakh)))", text, re.I)
    if currency_match:
        amt = currency_match.group(1) or currency_match.group(2)
        risk_metrics.append({
            "category": "Currency Risk",
            "description": "Potential impact on fair value of financial instruments from adverse FX moves",
            "amount": amt.strip(),
            "evidence": currency_match.group(0)[:250],
        })
    return accounting_info, risk_metrics


# ---------------------------------------------------------------------------
# 7. Core Extraction Agent Public API
# ---------------------------------------------------------------------------

def _extract_report_metrics(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_records: Optional[List[Dict[str, Any]]] = None,
    enable_llm: bool = True,
    requested_context: Optional[str] = None,
) -> Dict[str, Any]:
    text = text or ""
    metadata = metadata or {}
    chunk_records = chunk_records or []
    company_name = _extract_company_name(text, metadata)
    report_year = _extract_report_year(text, metadata)
    target_year_int = _normalize_year_value(report_year) or 2024
    table_curr, table_unit = extract_table_header_units(text)
    yearly_metrics, table_observations = _extract_multi_year_financial_tables(text, chunk_records=chunk_records)
    accounting_info, risk_metrics = _extract_accounting_notes_and_risks(text)
    all_observations: List[Dict[str, Any]] = list(table_observations)
    for metric_key in METRIC_TAXONOMY.keys():
        obs_list = _extract_field_observations(
            text,
            metric_key,
            labels=METRIC_TAXONOMY[metric_key]["aliases"],
            is_per_share=METRIC_TAXONOMY[metric_key]["is_per_share"],
            is_percent=METRIC_TAXONOMY[metric_key]["is_percent"],
            inherited_currency=table_curr,
            inherited_unit=table_unit,
            statement_context="narrative_overview",
            report_year=target_year_int,
        )
        all_observations.extend(obs_list)
    source_name = metadata.get("source") or metadata.get("source_file") or "document"
    for obs in all_observations:
        c_id, p_num, ev_text, score = _find_grounded_chunk_for_observation(
            obs,
            chunk_records=chunk_records,
            target_year=obs.get("report_year", target_year_int),
        )
        obs["source_chunk_id"] = c_id or metadata.get("chunk_id")
        obs["source_file"] = source_name
        obs["page_number"] = p_num
        obs["exact_evidence"] = ev_text
        obs["grounding_score"] = score
    canonical_metrics: Dict[str, Optional[str]] = {}
    for metric_key in (
        "revenue", "gross_profit", "operating_income", "pretax_income",
        "net_income", "eps", "basic_eps", "diluted_eps", "trend_eps",
        "total_assets", "total_liabilities", "total_equity", "cash_flow",
        "operating_cash_flow", "free_cash_flow", "rd_expense", "total_debt"
    ):
        cand = select_canonical_observation(
            all_observations,
            target_metric=metric_key,
            requested_context=requested_context,
            target_year=target_year_int,
        )
        if cand:
            cand["is_canonical"] = True
            canonical_metrics[metric_key] = cand["raw_value"]
        else:
            canonical_metrics[metric_key] = None
    for key, series_name in {
        "revenue": "Revenue",
        "gross_profit": "Gross Profit",
        "operating_income": "Operating Income",
        "pretax_income": "Pre-tax Income",
        "net_income": "Net Income",
        "total_assets": "Total Assets",
        "total_liabilities": "Total Liabilities",
        "total_equity": "Total Equity",
        "total_debt": "Total Debt",
        "cash_flow": "Cash Flow",
        "operating_cash_flow": "Operating Cash Flow",
        "free_cash_flow": "Free Cash Flow",
        "rd_expense": "R&D Expense",
        "eps": "EPS",
    }.items():
        if not canonical_metrics.get(key) and series_name in yearly_metrics:
            series = yearly_metrics[series_name]
            matched = next((item for item in series if item.get("year") == target_year_int), series[-1] if series else None)
            if matched and matched.get("value"):
                canonical_metrics[key] = str(matched["value"])
    if not canonical_metrics.get("operating_cash_flow") and canonical_metrics.get("cash_flow"):
        canonical_metrics["operating_cash_flow"] = canonical_metrics["cash_flow"]
    if not canonical_metrics.get("cash_flow") and canonical_metrics.get("operating_cash_flow"):
        canonical_metrics["cash_flow"] = canonical_metrics["operating_cash_flow"]
    if not canonical_metrics.get("basic_eps") and canonical_metrics.get("eps"):
        canonical_metrics["basic_eps"] = canonical_metrics["eps"]
    if not canonical_metrics.get("diluted_eps") and canonical_metrics.get("basic_eps"):
        canonical_metrics["diluted_eps"] = canonical_metrics["basic_eps"]
    if not canonical_metrics.get("eps") and canonical_metrics.get("basic_eps"):
        canonical_metrics["eps"] = canonical_metrics["basic_eps"]
    software_val = None
    consulting_val = None
    infra_val = None
    if "Software Segment" in yearly_metrics:
        matched = next((itm for itm in yearly_metrics["Software Segment"] if itm.get("year") == target_year_int), None)
        if matched:
            software_val = matched.get("value")
    if "Consulting Segment" in yearly_metrics:
        matched = next((itm for itm in yearly_metrics["Consulting Segment"] if itm.get("year") == target_year_int), None)
        if matched:
            consulting_val = matched.get("value")
    if "Infrastructure Segment" in yearly_metrics:
        matched = next((itm for itm in yearly_metrics["Infrastructure Segment"] if itm.get("year") == target_year_int), None)
        if matched:
            infra_val = matched.get("value")
    geo_breakdown: Dict[str, Optional[str]] = {}
    for geo in ["Americas", "Europe", "Asia Pacific", "India", "Middle East", "Africa", "United States", "United Kingdom"]:
        m_geo = re.search(rf"(?i)\b{re.escape(geo)}\b\s*[:\n\-]+\s*([^\n●]+)", text)
        if m_geo:
            parsed_geo = parse_financial_number(m_geo.group(1), inherited_currency=table_curr, inherited_unit=table_unit)
            if parsed_geo:
                geo_breakdown[geo] = parsed_geo["raw_value"]
    traceability: Dict[str, Dict[str, Any]] = {}
    detailed_metrics: List[Dict[str, Any]] = []
    for obs in all_observations:
        m_key = obs.get("metric_name", "")
        spec = METRIC_TAXONOMY.get(m_key, {})
        val = obs.get("raw_value")
        c_id = obs.get("source_chunk_id")
        p_num = obs.get("page_number", 1)
        ev_snippet = obs.get("exact_evidence", "")
        detailed_metrics.append({
            "metric": spec.get("canonical_name", m_key),
            "normalized_name": m_key,
            "value": val,
            "raw_value": val,
            "numeric_value": obs.get("numeric_value"),
            "currency": obs.get("currency"),
            "unit": obs.get("unit"),
            "statement_context": obs.get("statement_context"),
            "is_canonical": obs.get("is_canonical", False),
            "source_chunk_id": c_id,
            "source_file": source_name,
            "page_number": p_num,
            "evidence": ev_snippet,
        })
        if obs.get("is_canonical") or m_key not in traceability:
            traceability[m_key] = {
                "metric": spec.get("canonical_name", m_key),
                "value": val,
                "source_chunk_id": c_id,
                "source_file": source_name,
                "page_number": p_num,
                "original_label": obs.get("canonical_label", spec.get("canonical_name", m_key)),
                "evidence": ev_snippet,
            }
    result: Dict[str, Any] = {
        "company_name": company_name,
        "report_year": report_year,
        "revenue": canonical_metrics.get("revenue"),
        "gross_profit": canonical_metrics.get("gross_profit"),
        "operating_income": canonical_metrics.get("operating_income"),
        "pretax_income": canonical_metrics.get("pretax_income"),
        "net_income": canonical_metrics.get("net_income"),
        "eps": canonical_metrics.get("eps"),
        "basic_eps": canonical_metrics.get("basic_eps"),
        "diluted_eps": canonical_metrics.get("diluted_eps"),
        "trend_eps": canonical_metrics.get("trend_eps"),
        "total_assets": canonical_metrics.get("total_assets"),
        "total_liabilities": canonical_metrics.get("total_liabilities"),
        "total_equity": canonical_metrics.get("total_equity"),
        "cash_flow": canonical_metrics.get("cash_flow"),
        "operating_cash_flow": canonical_metrics.get("operating_cash_flow"),
        "free_cash_flow": canonical_metrics.get("free_cash_flow"),
        "rd_expense": canonical_metrics.get("rd_expense"),
        "total_debt": canonical_metrics.get("total_debt"),
        "yearly_metrics": yearly_metrics,
        "accounting_information": accounting_info,
        "risk_related_metrics": risk_metrics,
        "segment_metrics": {
            "software_revenue": software_val,
            "consulting_revenue": consulting_val,
            "infrastructure_revenue": infra_val,
            "geographic_breakdown": geo_breakdown,
        },
        "income_statement": {
            "revenue": canonical_metrics.get("revenue"),
            "gross_profit": canonical_metrics.get("gross_profit"),
            "operating_income": canonical_metrics.get("operating_income"),
            "pretax_income": canonical_metrics.get("pretax_income"),
            "net_income": canonical_metrics.get("net_income"),
            "eps": canonical_metrics.get("eps"),
            "basic_eps": canonical_metrics.get("basic_eps"),
            "diluted_eps": canonical_metrics.get("diluted_eps"),
            "trend_eps": canonical_metrics.get("trend_eps"),
            "rd_expense": canonical_metrics.get("rd_expense"),
        },
        "balance_sheet": {
            "total_assets": canonical_metrics.get("total_assets"),
            "total_liabilities": canonical_metrics.get("total_liabilities"),
            "total_equity": canonical_metrics.get("total_equity"),
            "total_debt": canonical_metrics.get("total_debt"),
            "cash_and_equivalents": canonical_metrics.get("cash_and_equivalents"),
        },
        "cash_flow_statement": {
            "operating_cash_flow": canonical_metrics.get("operating_cash_flow"),
            "free_cash_flow": canonical_metrics.get("free_cash_flow"),
            "capex": canonical_metrics.get("capex"),
        },
        "observations": all_observations,
        "detailed_metrics": detailed_metrics,
        "traceability": traceability,
    }
    if metadata:
        for key in ("analysis_id", "document_id", "chunk_id", "source", "source_file"):
            if key in metadata and metadata.get(key) not in (None, ""):
                result[key] = str(metadata[key])
    for key in (
        "revenue", "gross_profit", "operating_income", "pretax_income",
        "net_income", "total_assets", "total_liabilities", "total_equity",
        "cash_flow", "operating_cash_flow", "free_cash_flow", "rd_expense",
        "total_debt", "eps", "basic_eps", "diluted_eps", "trend_eps"
    ):
        if result.get(key) in ("", "Not Found", "not found", "null", "None"):
            result[key] = None
    return result


def extract_report_metrics(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_records: Optional[List[Dict[str, Any]]] = None,
    enable_llm: bool = True,
    requested_context: Optional[str] = None,
) -> Dict[str, Any]:
    return _extract_report_metrics(
        text,
        metadata=metadata,
        chunk_records=chunk_records,
        enable_llm=enable_llm,
        requested_context=requested_context,
    )
