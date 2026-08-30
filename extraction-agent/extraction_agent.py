"""Enterprise Multi-Agent Financial Extraction Agent.

Combines Semantic understanding with deterministic financial table parsing,
universal multi-currency detection (INR, USD, EUR, GBP), unit-multiplier detection (crore, lakh, billion, million),
context-driven canonical selection, independent EPS observation models, and multi-factor
matrix evidence traceability.
"""

from __future__ import annotations

import json
import logging
import math
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
    "cost_of_revenue": {
        "canonical_name": "Cost of Revenue",
        "aliases": [r"\bcost of revenue\b", r"\bcost of sales\b", r"\bcost of goods sold\b", r"\bcogs\b"],
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
    "operating_margin": {
        "canonical_name": "Operating Margin",
        "aliases": [r"\boperating margin\b"],
        "category": "income_statement",
        "is_per_share": False,
        "is_percent": True,
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
            r"\bgross debt\b",
            r"\bgross borrowings\b",
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
        "canonical_name": "Operating Cash Flow",
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
    "cash_flow": {
        "canonical_name": "Cash Flow",
        "aliases": [r"\bcash flow\b"],
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


def _is_temporal_year_label(text: str) -> bool:
    """Return true when a year is acting as a period label, not an amount."""
    normalized = re.sub(r"\s+", " ", str(text or "")).strip(" .:;=-")
    if not normalized:
        return False
    if re.fullmatch(r"FY\s*(?:19|20)\d{2}", normalized, re.I):
        return True
    return bool(re.fullmatch(
        r"(?:for|during|as of|year ended|fiscal year|financial year)\s+(?:the\s+year\s+ended\s+)?(?:FY\s*)?(?:19|20)\d{2}",
        normalized,
        re.I,
    ))


def extract_table_header_units(text: str) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    extracted_rupee_header = re.search(
        r"(?im)(?:\(\s*(?:in\s+)?|\b(?:all\s+(?:amounts|figures|values)\s+are\s+in|"
        r"(?:primary|reporting)\s+unit\s*[:=\-]?|unit(?:\s+of\s+measure)?\s*[:=\-]?)\s*)I\s+"
        r"(thousands?|millions?|billions?|crores?|lakhs?)\b",
        text,
    )
    if extracted_rupee_header:
        return "INR", _normalize_unit_name(extracted_rupee_header.group(1))
    symbol_header = re.search(
        r"(?i)\(\s*(?:in\s+)?(\u20b9|Rs\.?|\$|US\$|\u20ac|\u00a3|\u00a5|CN\u00a5)\s+(thousands?|millions?|billions?|crores?|lakhs?)\s*\)",
        text,
    )
    if symbol_header:
        symbol = symbol_header.group(1).casefold().replace(".", "")
        currency = {
            "₹": "INR",
            "rs": "INR",
            "$": "USD",
            "us$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
            "cn¥": "CNY",
        }.get(symbol)
        if currency:
            return currency, _normalize_unit_name(symbol_header.group(2))
    symbol_context = re.search(
        r"(?i)(?:^|[\s(:])(?:in\s+)?(\u20b9|Rs\.?|\$|US\$|\u20ac|\u00a3|\u00a5|CN\u00a5)\s+(thousands?|millions?|billions?|crores?|lakhs?)\b",
        text,
    )
    if symbol_context:
        symbol = symbol_context.group(1).casefold().replace(".", "")
        currency = {
            "₹": "INR",
            "rs": "INR",
            "$": "USD",
            "us$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
            "cn¥": "CNY",
        }.get(symbol)
        if currency:
            return currency, _normalize_unit_name(symbol_context.group(2))
    explicit_header = re.search(
        r"(?i)\(\s*(?:in\s+)?(INR|USD|EUR|GBP|JPY|CNY)\s+(thousands?|millions?|billions?|crores?|lakhs?)\s*\)",
        text,
    )
    if explicit_header:
        currency = explicit_header.group(1).upper()
        unit = explicit_header.group(2).lower().rstrip("s")
        return currency, unit
    header_patterns = [
        (r"(?i)\(\s*(?:in\s+)?INR\s+millions?\s*\)", "INR", "million"),
        (r"(?i)\(\s*(?:in\s+)?USD\s+millions?\s*\)", "USD", "million"),
        (r"(?i)\(\s*(?:in\s+)?EUR\s+millions?\s*\)", "EUR", "million"),
        (r"(?i)\(\s*(?:in\s+)?GBP\s+millions?\s*\)", "GBP", "million"),
        (r"(?i)\(\s*(?:in\s+)?(?:INR|USD|EUR|GBP|JPY|CNY)\s+billions?\s*\)", "USD", "billion"),
        (r"(?i)\(\s*(?:in\s+)?(?:INR|USD|EUR|GBP|JPY|CNY)\s+thousands?\s*\)", "USD", "thousand"),
        (r"(?i)\b(?:all\s+)?(?:amounts|figures|values)\s+are\s+in\s+₹\s*millions?\b", "INR", "million"),
        (r"(?i)\b(?:all\s+)?(?:amounts|figures|values)\s+are\s+in\s+₹\s*crores?\b", "INR", "crore"),
        (r"(?i)\b(?:all\s+)?(?:amounts|figures|values)\s+are\s+in\s+(?:\$|USD)\s*millions?\b", "USD", "million"),
        (r"(?i)\b(?:all\s+)?(?:amounts|figures|values)\s+are\s+in\s+(?:\$|USD)\s*billions?\b", "USD", "billion"),
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


def _normalize_unit_name(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    norm = re.sub(r"\s+", "", str(unit)).lower()
    aliases = {
        "crore": "crore",
        "crores": "crore",
        "cr": "crore",
        "lakh": "lakh",
        "lakhs": "lakh",
        "lac": "lakh",
        "billion": "billion",
        "billions": "billion",
        "bn": "billion",
        "million": "million",
        "millions": "million",
        "mn": "million",
        "thousand": "thousand",
        "thousands": "thousand",
        "k": "thousand",
    }
    return aliases.get(norm)


def _detect_context_currency_and_unit(
    snippet: str,
    inherited_currency: Optional[str],
    inherited_unit: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    if not snippet:
        return inherited_currency, inherited_unit
    normalized = re.sub(r"\s+", " ", str(snippet).strip())
    if not normalized:
        return inherited_currency, inherited_unit

    explicit_match = re.search(
        r"(?i)\(\s*(?:in\s+)?(INR|USD|EUR|GBP|JPY|CNY)\s+(thousands?|millions?|billions?|crores?|lakhs?)\s*\)",
        normalized,
    )
    if explicit_match:
        return explicit_match.group(1).upper(), _normalize_unit_name(explicit_match.group(2))

    plain_match = re.search(
        r"(?i)\b(?:in\s+)?(INR|USD|EUR|GBP|JPY|CNY)\s+(thousands?|millions?|billions?|crores?|lakhs?)\b",
        normalized,
    )
    if plain_match:
        return plain_match.group(1).upper(), _normalize_unit_name(plain_match.group(2))

    symbol_to_currency = {
        "₹": "INR",
        "Rs": "INR",
        "Rs.": "INR",
        "INR": "INR",
        "$": "USD",
        "US$": "USD",
        "USD": "USD",
        "€": "EUR",
        "EUR": "EUR",
        "£": "GBP",
        "GBP": "GBP",
        "¥": "JPY",
        "JPY": "JPY",
        "CN¥": "CNY",
        "CNY": "CNY",
    }
    for symbol, curr in symbol_to_currency.items():
        match = re.search(rf"(?i)\b{re.escape(symbol)}\s*(?:in\s+)?(thousands?|millions?|billions?|crores?|lakhs?)\b", normalized)
        if match:
            unit = _normalize_unit_name(match.group(1))
            if unit:
                return curr, unit

    if inherited_currency and inherited_unit:
        return inherited_currency, _normalize_unit_name(inherited_unit) or inherited_unit
    return inherited_currency, inherited_unit


def _context_currency_unit(context: Any) -> Tuple[Optional[str], Optional[str]]:
    """Read independently supported currency and unit values from one context."""
    if not context:
        return None, None
    if isinstance(context, dict):
        currency = context.get("currency") or context.get("currency_code")
        unit = context.get("unit") or context.get("primary_unit") or context.get("unit_scale")
        return (str(currency).upper() if currency else None), _normalize_unit_name(unit) or (str(unit) if unit else None)
    text = re.sub(r"\s+", " ", str(context).strip())
    currency_aliases = {
        "₹": "INR", "$": "USD", "us$": "USD", "€": "EUR",
        "£": "GBP", "¥": "JPY", "cn¥": "CNY",
    }
    currency = None
    code_match = re.search(r"(?i)\b(INR|USD|EUR|GBP|JPY|CNY|CHF)\b", text)
    if code_match:
        currency = code_match.group(1).upper()
    else:
        folded_text = text.casefold()
        for token, code in currency_aliases.items():
            if token.casefold() in folded_text:
                currency = code
                break
    unit_match = re.search(
        r"(?i)\b(crores?|cr|lakhs?|lac|billions?|bn|millions?|mn|thousands?|k|percent|%)\b|%",
        text,
    )
    unit = _normalize_unit_name(unit_match.group(1)) if unit_match and unit_match.group(1) else ("percent" if unit_match else None)
    return currency, unit


def resolve_currency_unit_context(
    value_context: Any = None,
    table_context: Any = None,
    section_context: Any = None,
    document_context: Any = None,
) -> Dict[str, Any]:
    """Resolve currency and unit independently from most to least specific evidence."""
    value_currency, value_unit = _context_currency_unit(value_context)
    table_currency, table_unit = _context_currency_unit(table_context)
    section_currency, section_unit = _context_currency_unit(section_context)
    document_currency, document_unit = _context_currency_unit(document_context)
    currency = value_currency or table_currency or section_currency or document_currency or "UNKNOWN"
    unit = value_unit or table_unit or section_unit or document_unit or "units"
    if unit in {"percent", "%"}:
        return {"currency": "PERCENT", "unit": "percent", "unit_multiplier": 0.01}
    if unit in {"per_share", "x", "days", "units"}:
        return {"currency": currency, "unit": unit, "unit_multiplier": 1.0}
    return {
        "currency": currency,
        "unit": unit,
        "unit_multiplier": UNIT_MULTIPLIERS.get(unit, 1.0),
    }


def _detect_document_currency_unit(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Detect explicit document-level currency and primary-unit metadata."""
    if not text:
        return None, None
    normalized = re.sub(r"[ \t]+", " ", text)
    currency_match = re.search(
        r"(?i)\b(?:currency|reporting currency|presentation currency)\s*[:=\-]?\s*"
        r"(INR|USD|EUR|GBP|JPY|CNY|CHF)\b",
        normalized,
    )
    unit_match = re.search(
        r"(?i)\b(?:primary\s+unit|reporting unit|unit of measure|unit)\s*[:=\-]?\s*"
        r"(?:₹|INR|I\s+)?\s*(crores?|cr|lakhs?|lac|billions?|bn|millions?|mn|thousands?|k|units?)\b",
        normalized,
    )
    return (
        currency_match.group(1).upper() if currency_match else None,
        _normalize_unit_name(unit_match.group(1)) if unit_match else None,
    )


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
    if _is_temporal_year_label(cleaned_snippet):
        return None
    resolved_context = resolve_currency_unit_context(
        value_context=cleaned_snippet,
        document_context={"currency": inherited_currency, "unit": inherited_unit},
    )
    inherited_currency = resolved_context["currency"] if resolved_context["currency"] != "UNKNOWN" else inherited_currency
    inherited_unit = resolved_context["unit"] if resolved_context["unit"] != "units" else inherited_unit
    sentinel_match = re.search(r"\b(nil|n\.a\.|n/a|not available|not disclosed)\b", cleaned_snippet, re.I)
    if sentinel_match:
        sentinel = sentinel_match.group(1).lower()
        return {
            "raw_value": "NIL" if sentinel == "nil" else sentinel_match.group(1),
            "numeric_value": 0.0 if sentinel == "nil" else None,
            "currency": inherited_currency or "UNKNOWN",
            "unit": inherited_unit or ("per_share" if is_per_share else "units"),
            "unit_multiplier": UNIT_MULTIPLIERS.get(inherited_unit or "", 1.0),
            "normalized_base_value": 0.0 if sentinel == "nil" else None,
            "status": "reported_zero" if sentinel == "nil" else "missing",
        }
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
    if is_per_share:
        detected_unit = "per_share"
        unit_mult = 1.0
    # Strip growth rates if parsing monetary metrics
    cleaned_snippet = re.sub(r"(?i)(?:increased|decreased|grew|fell|dropped|rose|up|down)?\s*[-+]?\d+(?:\.\d+)?%\s*(?:to\s*)?", "", cleaned_snippet)
    cleaned_snippet = re.sub(r"[-+]?\d+(?:\.\d+)?%", "", cleaned_snippet)
    curr_anchored_match = re.search(rf"(?:[₹$€£]|Rs\.?\s*|US\$\s*|INR\s*)({NUM_PATTERN_STR})", cleaned_snippet, re.I)
    if curr_anchored_match:
        raw_num_str = curr_anchored_match.group(1)
        selected_end = curr_anchored_match.end()
    else:
        matches = list(re.finditer(NUM_PATTERN_STR, cleaned_snippet))
        if not matches:
            return None
        match = matches[0]
        if re.fullmatch(r"(?:19|20)\d{2}", match.group(0)) and len(matches) > 1:
            match = matches[1]
        raw_num_str = match.group(0)
        selected_end = match.end()
    selected_prefix = cleaned_snippet[:selected_end]
    negative_value = bool(re.search(r"(?:^|[\s(])-\s*(?=(?:US\$|[$€£₹]|Rs\.?|INR)?\s*\d)", selected_prefix))
    parenthesized_value = bool(re.search(r"\(\s*(?:US\$|[$€£₹]|Rs\.?|INR)?\s*\d[\d,.]*$", selected_prefix))
    negative_value = negative_value or parenthesized_value
    try:
        numeric_val = float(raw_num_str.replace(",", ""))
    except ValueError:
        return None
    if negative_value:
        numeric_val = -abs(numeric_val)
    value_status = "zero" if numeric_val == 0 else "available"
    if is_per_share:
        raw_number = f"{abs(numeric_val):.2f}"
        raw_val = f"{'-' if negative_value else ''}{curr_prefix}{raw_number}" if curr_prefix else f"{'-' if negative_value else ''}{raw_number}"
    elif detected_unit and detected_unit != "units" and detected_unit != "per_share":
        raw_val = f"{'-' if negative_value else ''}{curr_prefix}{raw_num_str.lstrip('+-')} {detected_unit}".strip()
    else:
        raw_val = f"{'-' if negative_value else ''}{curr_prefix}{raw_num_str.lstrip('+-')}".strip()
    return {
        "raw_value": raw_val,
        "numeric_value": numeric_val,
        "currency": detected_currency,
        "unit": detected_unit,
        "unit_multiplier": unit_mult,
        "normalized_base_value": numeric_val * unit_mult,
        "status": value_status,
    }


def classify_financial_value_status(value: Any) -> str:
    """Classify an explicitly reported value without collapsing its state."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "MISSING"
    text = str(value).strip().lower()
    if text in {"nil", "n/a", "n.a.", "not available", "not reported", "not disclosed"}:
        return "NIL" if text == "nil" else "MISSING"
    parsed = parse_financial_number(str(value))
    if parsed is None or parsed.get("numeric_value") is None:
        return "INVALID/UNVERIFIABLE"
    return "ZERO" if parsed.get("numeric_value") == 0 else "REPORTED"


def reconcile_cash_flow(
    beginning_cash: Any,
    net_change_in_cash: Any,
    ending_cash: Any,
    inherited_currency: Optional[str] = None,
    inherited_unit: Optional[str] = None,
) -> Dict[str, Any]:
    """Reconcile source cash balances without replacing any source value."""
    source_values = {
        "beginning_cash": beginning_cash,
        "net_change_in_cash": net_change_in_cash,
        "ending_cash": ending_cash,
    }
    parsed_values: Dict[str, Optional[float]] = {}
    for key, value in source_values.items():
        parsed = parse_financial_number(
            str(value),
            inherited_currency=inherited_currency,
            inherited_unit=inherited_unit,
        ) if value is not None else None
        parsed_values[key] = parsed.get("numeric_value") if parsed else None
    missing = [key for key, value in parsed_values.items() if value is None]
    if missing:
        return {
            **source_values,
            "status": "unverifiable",
            "reconciliation_status": "unverifiable",
            "reason": f"Missing or invalid source value: {', '.join(missing)}",
            "calculated_ending_cash": None,
            "difference": None,
        }
    calculated_ending = parsed_values["beginning_cash"] + parsed_values["net_change_in_cash"]
    difference = calculated_ending - parsed_values["ending_cash"]
    reconciled = math.isclose(difference, 0.0, rel_tol=0.0, abs_tol=1e-9)
    return {
        **source_values,
        "status": "reconciled" if reconciled else "inconsistent",
        "reconciliation_status": "reconciled" if reconciled else "inconsistent",
        "reason": None if reconciled else "Beginning cash plus net change does not equal ending cash",
        "calculated_ending_cash": calculated_ending,
        "difference": difference,
    }


reconcile_cash_flows = reconcile_cash_flow


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
    invalid_metadata = {"unknown", "none", "null", "not found"}

    def valid_candidate(value: Any) -> bool:
        candidate = _normalize_value(str(value)) if value is not None else None
        if not candidate or len(candidate) < 3 or len(candidate.split()) > 10:
            return False
        lowered = candidate.casefold()
        blocked_fragments = (
            "million", "billion", "thousand", "crore", "lakh", "percent", "percentage",
            "revenue", "sales", "income", "profit", "loss", "assets", "liabilities",
            "equity", "debt", "cash flow", "margin", "balance sheet", "income statement",
            "financial statement", "table", "metric", "fiscal year", "annual report",
        )
        if any(fragment in lowered for fragment in blocked_fragments):
            return False
        if re.fullmatch(r"(?:[$€£₹]|usd|inr|eur|gbp|jpy)?\s*[-+]?\d[\d,]*(?:\.\d+)?%?", candidate, re.I):
            return False
        if re.fullmatch(r"(?:19|20)\d{2}", candidate):
            return False
        punctuation_probe = re.sub(r"\b(?:ltd|inc|corp|co)\.", "", candidate, flags=re.I)
        if not re.search(r"[A-Za-z]", candidate) or re.search(r"[!?]", punctuation_probe) or re.search(r"\.(?!\s*\(?[A-Z]{1,5}\)?)", punctuation_probe):
            return False
        return True

    def clean_explicit(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip(" \t:;,.-")
        value = re.sub(r"\s+(?:annual|financial|integrated|sustainability)\s+report(?:\s+(?:19|20)\d{2})?$", "", value, flags=re.I)
        return value.strip()

    candidates: List[Tuple[int, int, str]] = []
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]

    explicit_pattern = re.compile(
        r"^\s*(?:company(?:\s+name)?|legal\s+entity|registered\s+name|issuer(?:\s+name)?|registrant(?:\s+name)?)\s*[:\-]\s*(.+?)\s*$",
        re.I,
    )
    for index, line in enumerate(lines[:80]):
        match = explicit_pattern.match(line)
        if match:
            candidate = clean_explicit(match.group(1))
            if valid_candidate(candidate):
                candidates.append((0, index, candidate))

    title_patterns = (
        re.compile(r"^\s*(.+?)\s+(?:annual|financial|integrated|sustainability)\s+report\b.*$", re.I),
        re.compile(r"^\s*(.+?)\s*\|\s*(?:fiscal|financial|annual)\s+year\b.*$", re.I),
    )
    for index, line in enumerate(lines[:30]):
        for pattern in title_patterns:
            match = pattern.match(line)
            if match:
                candidate = clean_explicit(match.group(1))
                if valid_candidate(candidate):
                    candidates.append((1, index, candidate))

    for index, line in enumerate(lines[:40]):
        match = re.match(r"^\s*(.+?)\s+(?:Ltd\.?|Limited|Inc\.?|Incorporated|Corp\.?|Corporation|Holdings|Group|PLC|LLC)\.?\s*$", line, re.I)
        if match:
            candidate = clean_explicit(line)
            if valid_candidate(candidate):
                candidates.append((3, index, candidate)
                )

    for index, line in enumerate(lines[:40]):
        candidate = clean_explicit(line)
        if valid_candidate(candidate) and len(candidate.split()) <= 8:
            candidates.append((3, index, candidate))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

    if metadata_value and str(metadata_value).casefold() not in invalid_metadata and not re.fullmatch(r"(?:of|page)\s+\d+", str(metadata_value).strip(), re.I):
        normalized_metadata = clean_explicit(str(metadata_value))
        if valid_candidate(normalized_metadata):
            return normalized_metadata
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


def _year_from_text(text: str, fallback: Optional[int]) -> Optional[int]:
    fy_match = re.search(r"\bFY\s*((?:19|20)\d{2})\b", text, re.I)
    if fy_match:
        return int(fy_match.group(1))
    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    return int(years[-1]) if years else fallback


def _is_temporal_metric_candidate(
    text: str,
    metric_start: int,
    parsed: Optional[Dict[str, Any]],
) -> bool:
    """Reject a year-valued parse only when nearby text identifies it as a period."""
    if not parsed or parsed.get("numeric_value") is None:
        return False
    numeric_value = parsed.get("numeric_value")
    if not isinstance(numeric_value, (int, float)) or not 1900 <= numeric_value <= 2100:
        return False
    prefix = text[max(0, metric_start - 40):metric_start]
    suffix = text[metric_start:metric_start + 80]
    if re.search(r"\bFY\s*(?:19|20)\d{2}\s*$", prefix, re.I):
        return True
    if re.search(r"\b(?:for|during|as of|year ended|fiscal year|financial year)\s+(?:FY\s*)?(?:19|20)\d{2}\s*$", prefix, re.I):
        return True
    if re.search(r"\bFY\s*(?:19|20)\d{2}\b\s*(?:[-:|]|$)", suffix, re.I) and not re.search(r"(?:=|was|were|is|are|stood at|reached|to)\s*$", suffix, re.I):
        return True
    return False


def _is_semantically_compatible_metric(metric_key: str, sentence: str, parsed: Optional[Dict[str, Any]]) -> bool:
    """Reject false matches such as ratios, percentages, EPS, or years from monetary metrics."""
    if parsed is None:
        return False
    lowered = sentence.casefold()
    ratio_context = re.search(
        r"\b(?:debt\s*[-/]?\s*to\s*[-/]?\s*equity|debt\s*/\s*equity|equity\s+ratio|"
        r"return\s+on\s+equity|asset\s+turnover|asset\s+ratio|liability\s+ratio|"
        r"debt\s+ratio|leverage\s+ratio)\b",
        lowered,
        re.I,
    )
    if ratio_context:
        return False
    if parsed.get("currency") == "PERCENT" or parsed.get("unit") == "percent":
        return metric_key == "operating_margin"
    if re.search(r"\b(?:earnings?\s+per\s+share|eps|basic\s+eps|diluted\s+eps|per[- ]share|share price)\b", lowered, re.I):
        return metric_key in {"eps", "basic_eps", "diluted_eps", "trend_eps"}
    if isinstance(parsed.get("numeric_value"), (int, float)) and 1900 <= parsed["numeric_value"] <= 2100:
        return False
    if metric_key == "revenue" and re.search(r"\bcredit\s+sales\b", lowered, re.I):
        return False
    if metric_key == "revenue" and re.search(r"\brevenue\s+(?:growth|margin|percentage|ratio)\b", lowered, re.I):
        return False
    if metric_key == "total_equity" and re.search(r"\b(?:equity\s+percentage|equity\s+multiple)\b", lowered, re.I):
        return False
    if metric_key == "total_debt" and re.search(r"\bnet\s+debt\b", lowered, re.I):
        return False
    if metric_key == "total_assets" and re.search(r"\b(?:current|non[- ]current|cash|asset)\s+(?:assets?|turnover|ratio)\b", lowered, re.I):
        return False
    if metric_key == "total_liabilities" and re.search(r"\b(?:current|non[- ]current|debt|liability|liabilities)\s+(?:liabilities|ratio)\b", lowered, re.I):
        return False
    return True


def _classify_metric_candidate(
    metric_key: str,
    sentence: str,
    alias: str,
    parsed: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Return the supported metric bucket, or None for a conflicting concept."""
    if parsed is None:
        return None
    lowered = sentence.casefold()
    alias_lower = alias.casefold()
    explicit_basic_eps = bool(re.search(r"\b(?:basic\s+)?(?:earnings?\s+per\s+share|eps|per[- ]share)\b", lowered) and re.search(r"\bbasic\b", lowered))
    explicit_diluted_eps = bool(re.search(r"\b(?:diluted\s+)?(?:earnings?\s+per\s+share|eps|per[- ]share)\b", lowered) and re.search(r"\bdiluted\b", lowered))
    explicit_trend_eps = bool(re.search(r"\b(?:performance[- ]trend|trend|adjusted|operating)\s+eps\b", lowered))
    if metric_key == "eps":
        if explicit_basic_eps:
            return "basic_eps"
        if explicit_diluted_eps:
            return "diluted_eps"
        if explicit_trend_eps:
            return "trend_eps"
    elif metric_key == "basic_eps" and explicit_diluted_eps:
        return None
    elif metric_key == "diluted_eps" and explicit_basic_eps:
        return None
    if not _is_semantically_compatible_metric(metric_key, sentence, parsed):
        return None
    if metric_key == "revenue" and re.search(r"\bcost\s+of\s+(?:revenue|sales|goods sold)\b", lowered):
        return None
    if metric_key == "total_equity" and re.search(r"\bdebt\s*[- ]?to\s*[- ]?equity\b|\bequity\s+ratio\b", lowered):
        return None
    if metric_key == "revenue" and re.search(r"\b(?:segment|division|services?|business line|geographic|regional)\b", lowered) and "consolidated" not in lowered:
        return "segment_revenue"
    if metric_key == "operating_cash_flow":
        if re.search(r"\b(?:free|investing|financing)\s+cash flow\b", lowered):
            return None
        if "operating" not in lowered and "cash from operations" not in lowered and "cash flow from operations" not in lowered:
            return None
    if metric_key == "cash_flow" and re.search(
        r"\b(?:operating|free|investing|financing)\s+cash flow\b|\bcash flow statement\b",
        lowered,
    ):
        return None
    if metric_key == "total_assets" and "total assets" not in lowered and alias_lower.strip() != r"\btotal assets\b":
        return None
    if metric_key == "total_liabilities" and "total liabilities" not in lowered and alias_lower.strip() != r"\btotal liabilities\b":
        return None
    return metric_key


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
        "cash flow from operations": "Operating Cash Flow",
        "operating cash flow": "Operating Cash Flow",
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
) -> Tuple[Optional[str], int, str, float, str]:
    if not chunk_records:
        return None, 1, "", 0.0, ""
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
    best_section = ""
    for chunk in chunk_records:
        c_text = chunk.get("text", "")
        if not c_text:
            continue
        c_text_lower = c_text.lower()
        c_meta = chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), dict) else {}
        sec_title = str(
            chunk.get("section_title") or c_meta.get("section_title") or c_meta.get("section") or ""
        ).lower()
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
        matching_line_index = -1
        for line_index, line in enumerate(lines):
            line_lower = line.lower()
            number_tokens = re.findall(r"(?<!\d)\d[\d,]*(?:\.\d+)?", line)
            exact_number_match = any(re.sub(r"[^\d.]", "", token) == raw_digits for token in number_tokens) if metric_name == "free_cash_flow" else False
            if (num_str and num_str in line) or (raw_digits and raw_digits in re.sub(r"[^\d.]", "", line)) or (raw_val.lower() in line_lower):
                if metric_name == "free_cash_flow" and not exact_number_match and not any(re.search(alias, line, re.I) for alias in aliases):
                    continue
                if any(re.search(alias, line, re.I) for alias in aliases):
                    matching_line = line.strip()
                    matching_line_index = line_index
                    found_in_same_line = True
                    score += 15.0
                    break
                if metric_name == "revenue":
                    prior_window = 12
                    prior_label_index = next(
                        (
                            prior_index
                            for prior_index in range(line_index - 1, max(-1, line_index - prior_window), -1)
                            if any(re.search(alias, lines[prior_index], re.I) for alias in aliases)
                        ),
                        None,
                    )
                    if prior_label_index is not None:
                        matching_line = line.strip()
                        matching_line_index = line_index
                        break
                if metric_name == "free_cash_flow" and exact_number_match:
                    prior_label_index = next(
                        (
                            prior_index
                            for prior_index in range(line_index - 1, max(-1, line_index - 12), -1)
                            if any(re.search(alias, lines[prior_index], re.I) for alias in aliases)
                        ),
                        None,
                    )
                    if prior_label_index is not None:
                        matching_line = line.strip()
                        matching_line_index = line_index
                        break
                if matching_line_index < 0:
                    matching_line = line.strip()
                    matching_line_index = line_index
        occurrence_index = matching_line_index
        if occurrence_index >= 0 and not any(re.search(alias, lines[occurrence_index], re.I) for alias in aliases):
            prior_window = 12 if metric_name == "revenue" else 4
            for prior_index in range(occurrence_index - 1, max(-1, occurrence_index - prior_window), -1):
                if any(re.search(alias, lines[prior_index], re.I) for alias in aliases):
                    occurrence_index = prior_index
                    break
        if metric_name == "operating_cash_flow" and occurrence_index >= 0 and occurrence_index != matching_line_index:
            score += 15.0
        if metric_name == "free_cash_flow" and occurrence_index >= 0 and occurrence_index != matching_line_index:
            score += 15.0
        if metric_name == "revenue" and occurrence_index >= 0 and occurrence_index != matching_line_index:
            score += 15.0
        current_section = sec_title
        occurrence_section = sec_title
        occurrence_page = None
        for line_index, line in enumerate(lines):
            heading = re.sub(r"^[\d.)\s:-]+", "", line).strip()
            if line_index <= occurrence_index:
                page_match = re.fullmatch(r"(?i)page\s+(\d+)", heading)
                if page_match:
                    occurrence_page = int(page_match.group(1))
            if re.fullmatch(
                r"(?i)(?:consolidated\s+)?(?:income|profit and loss|statement of operations|operations)\s+statement|"
                r"(?:consolidated\s+)?balance sheet|(?:consolidated\s+)?cash flow statement|"
                r"accounting notes(?: and risk indicators)?|risk indicators?|"
                r"(?:debt|liquidity|capital structure)[^:]*",
                heading,
            ) or (
                metric_name in {"operating_cash_flow", "free_cash_flow"}
                and re.fullmatch(r"(?i)(?:consolidated\s+)?cash flows?", heading)
            ):
                current_section = heading
            if line_index == occurrence_index:
                occurrence_section = current_section
        occurrence_context = " ".join(lines[max(0, occurrence_index - 1): occurrence_index + 2]).lower() if occurrence_index >= 0 else ""
        ranking_context = f"{occurrence_section} {occurrence_context}" if metric_name in {"revenue", "operating_cash_flow", "free_cash_flow"} else f"{sec_title} {c_text_lower[:150]}"
        if category == "income_statement" and any(w in ranking_context for w in ["profit", "loss", "income statement", "operations", "financial performance", "p&l"]):
            score += 8.0
        elif category == "balance_sheet" and any(w in ranking_context for w in ["balance sheet", "financial position", "assets", "liabilities"]):
            score += 8.0
        elif category == "cash_flow" and any(w in ranking_context for w in ["cash flow", "cash flows", "operating activities"]):
            score += 8.0
        if target_year_str and target_year_str in c_text:
            score += 5.0
        if any(w in c_text_lower for w in ["scope 1", "scope 2", "greenhouse gas", "learning hours per employee", "carbon emissions", "sustainability initiative"]):
            if metric_name in ["eps", "basic_eps", "diluted_eps", "trend_eps", "total_liabilities", "total_equity", "revenue", "operating_income", "net_income"]:
                score -= 30.0
        if score > best_score and score >= 10.0:
            best_score = score
            best_chunk_id = chunk.get("chunk_id") or c_meta.get("chunk_id")
            best_page = occurrence_page if occurrence_page is not None else (
                chunk.get("page_start") or c_meta.get("page_start") or c_meta.get("page_number") or 1
            )
            evidence_lines = [matching_line] if matching_line else [c_text[:200]]
            if metric_name in {"revenue", "operating_cash_flow", "free_cash_flow"} and occurrence_index >= 0 and occurrence_index != matching_line_index:
                evidence_lines.insert(0, lines[occurrence_index])
            best_snippet = " ".join(evidence_lines).replace("\n", " ")
            best_section = occurrence_section
    return best_chunk_id, best_page, best_snippet, best_score, best_section


# ---------------------------------------------------------------------------
# 5. Context-Driven Canonical Selection Hierarchy
# ---------------------------------------------------------------------------

def _provenance_score(observation: Dict[str, Any], target_year: Optional[int] = None) -> float:
    """Score semantic source quality; page order is intentionally not primary."""
    context = " ".join(
        str(observation.get(key) or "")
        for key in ("statement_context", "source_section", "section", "source_type", "exact_evidence")
    ).casefold().replace("_", " ")
    statement_context = str(observation.get("statement_context") or "").casefold().replace("_", " ")
    source_context = " ".join(
        str(observation.get(key) or "")
        for key in ("source_section", "section", "source_type", "exact_evidence")
    ).casefold().replace("_", " ")
    reference_terms = (
        "expected cross-document", "expected comparison", "test values",
        "reference", "illustrative example", "comparison example", "expected results",
    )
    if any(term in context for term in reference_terms):
        return float("-inf")

    if any(term in source_context for term in (
        "income statement", "statement of profit", "statement of loss",
        "balance sheet", "statement of financial position", "cash flow statement",
        "statement of cash flows", "financial statements",
    )) or "income statement audited" in statement_context:
        score = 100.0
    elif "income statement consolidated" in statement_context:
        score = 80.0
    elif "financial metrics table" in context or "revenue table" in context or "financial table" in context:
        score = 90.0
    elif "consolidated" in context and any(term in context for term in ("statement", "financial")):
        score = 80.0
    elif any(term in context for term in ("accounting note", "accounting notes", "note to", "notes to", "disclosure")):
        score = 40.0
    elif any(term in context for term in ("narrative", "management discussion", "commentary")):
        score = 20.0
    else:
        score = 10.0

    if target_year is not None and _normalize_year_value(observation.get("report_year")) == _normalize_year_value(target_year):
        score += 20.0
    if observation.get("canonical_label") or observation.get("metric_name"):
        score += 10.0
    if any(term in context for term in ("statement", "financial", "table", "disclosure")):
        score += 10.0
    if observation.get("source_chunk_id") or observation.get("source_page") is not None:
        score += 5.0
    return score

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
        if not year_matched:
            return None
        candidates = year_matched
    def _rank_candidate(cand: Dict[str, Any]) -> tuple:
        page = _normalize_year_value(cand.get("source_page"))
        chunk_index = _normalize_year_value(cand.get("chunk_index"))
        return (
            _provenance_score(cand, target_year=target_year),
            1 if cand.get("canonical_label") else 0,
            1 if cand.get("source_chunk_id") else 0,
            -(page if page is not None else 10**9),
            -(chunk_index if chunk_index is not None else 10**9),
        )
    sorted_candidates = sorted(candidates, key=_rank_candidate, reverse=True)
    return sorted_candidates[0]


# ---------------------------------------------------------------------------
# 6. Multi-Year Financial Table & Narrative Parsing
# ---------------------------------------------------------------------------

def _extract_multi_year_financial_tables(
    text: str,
    chunk_records: Optional[List[Dict[str, Any]]] = None,
    document_context: Any = None,
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    yearly: Dict[str, List[Dict[str, Any]]] = {}
    observations: List[Dict[str, Any]] = []
    if not text:
        return yearly, observations
    detected_curr, detected_unit = extract_table_header_units(text)
    resolved_context = resolve_currency_unit_context(
        table_context={"currency": detected_curr, "unit": detected_unit},
        document_context=document_context,
    )
    detected_curr = resolved_context["currency"] if resolved_context["currency"] != "UNKNOWN" else None
    detected_unit = resolved_context["unit"] if resolved_context["unit"] != "units" else None
    curr_prefix = "₹" if detected_curr == "INR" else ("$" if detected_curr == "USD" else ("€" if detected_curr == "EUR" else ""))
    table_unit = detected_unit or "units"
    table_curr = detected_curr or "UNKNOWN"
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
        match = _find_non_reference_match(pattern, text, re.I)
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
    two_col_table = _extract_table_yearly_metrics_legacy(text, table_curr, table_unit)
    for k, v in two_col_table.items():
        if k not in yearly:
            yearly[k] = v
    return yearly, observations


def _observation_context_key(observation: Dict[str, Any]) -> Tuple[Any, ...]:
    """Identify the period and reporting context of an observation."""
    return (
        observation.get("metric_name"),
        _normalize_year_value(observation.get("report_year")),
        (observation.get("statement_context") or "").casefold(),
        (observation.get("currency") or "").casefold(),
        (observation.get("unit") or "").casefold(),
    )


def _observation_identity(observation: Dict[str, Any]) -> Tuple[Any, ...]:
    """Identify an exact repeat without collapsing distinct evidence."""
    identity = _observation_context_key(observation) + (
        observation.get("numeric_value"),
        observation.get("raw_value"),
        observation.get("exact_evidence") or "",
    )
    if observation.get("exact_evidence"):
        return identity
    return identity + (observation.get("source_chunk_id"), observation.get("source_page"))


def _deduplicate_observations(observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: List[Dict[str, Any]] = []
    seen: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for observation in observations:
        metric = observation.get("metric_name")
        year = _normalize_year_value(observation.get("report_year"))
        value = observation.get("numeric_value")
        currency = (observation.get("currency") or "").casefold()
        unit = (observation.get("unit") or "").casefold()
        identity = (metric, year, currency, unit, value)
        existing = seen.get(identity)
        if existing is None:
            seen[identity] = observation
            unique.append(observation)
            continue
        if not existing.get("exact_evidence") and observation.get("exact_evidence"):
            index = unique.index(existing)
            unique[index] = observation
            seen[identity] = observation
    return unique


def _conflict_record(observation: Dict[str, Any]) -> Dict[str, Any]:
    """Expose the existing conflict shape with complete observation provenance."""
    return {
        "metric": observation.get("metric_name"),
        "value": observation.get("raw_value"),
        "raw_value": observation.get("raw_value"),
        "numeric_value": observation.get("numeric_value"),
        "currency": observation.get("currency"),
        "unit": observation.get("unit"),
        "year": observation.get("report_year"),
        "period": observation.get("report_year"),
        "statement_context": observation.get("statement_context"),
        "page": observation.get("source_page"),
        "source_page": observation.get("source_page"),
        "chunk": observation.get("source_chunk_id"),
        "source_chunk_id": observation.get("source_chunk_id"),
        "evidence": observation.get("exact_evidence"),
        "provenance": {
            "source_file": observation.get("source_file"),
            "page": observation.get("source_page"),
            "chunk_id": observation.get("source_chunk_id"),
            "section": observation.get("source_section"),
        },
    }


def _conflict_comparison_value(observation: Dict[str, Any]) -> Any:
    """Compare expense presentation signs by magnitude without changing source values."""
    value = observation.get("numeric_value")
    if observation.get("metric_name") == "interest_expense" and isinstance(value, (int, float)):
        return abs(value)
    return value


def _find_observation_conflicts(observations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for observation in observations:
        if observation.get("numeric_value") is None:
            continue
        metric_name = observation.get("metric_name")
        year = _normalize_year_value(observation.get("report_year"))
        conflict_key = (metric_name, year)
        grouped.setdefault(conflict_key, []).append(observation)

    conflicts: Dict[str, List[Dict[str, Any]]] = {}
    for context_key, group in grouped.items():
        distinct_values = set()
        for observation in group:
            numeric_value = observation.get("numeric_value")
            if numeric_value is None:
                continue
            unit = (observation.get("unit") or "").casefold()
            scale = {
                "thousand": 1_000.0,
                "million": 1_000_000.0,
                "billion": 1_000_000_000.0,
                "lakh": 100_000.0,
                "crore": 10_000_000.0,
                "percent": 1.0,
                "unitless": 1.0,
            }
            multiplier = scale.get(unit, 1.0)
            distinct_values.add(round(float(numeric_value) * multiplier, 10))
        if len(distinct_values) <= 1:
            continue
        metric_key = context_key[0]
        for observation in group:
            observation["conflict_status"] = "conflict"
        conflicts.setdefault(metric_key, []).extend(_conflict_record(observation) for observation in group)
    return conflicts


def _infer_statement_context(sentence: str, nearby_context: str, default: str) -> str:
    sentence_lower = sentence.casefold()
    if re.search(r"\b(?:disclosure|disclosed|note to|notes to|narrative)\b", sentence_lower):
        return "disclosure"
    if re.search(r"\b(?:segment|division|services?|business line|geographic|regional)\b", sentence_lower):
        return "segment_metrics"
    if "consolidated" in sentence_lower:
        return "income_statement_consolidated"
    if re.search(r"statement of (?:profit|income|operations)|income statement|financial statements?", sentence_lower):
        return "income_statement_audited"
    context = f"{nearby_context} {sentence_lower}"
    if re.search(r"statement of (?:profit|income|operations)|income statement|financial statements?", context):
        return "income_statement_audited"
    if "consolidated" in context:
        return "income_statement_consolidated"
    if re.search(r"\b(?:segment|division|services?|business line|geographic|regional)\b", context):
        return "segment_metrics"
    if re.search(r"\b(?:disclosure|disclosed|note to|notes to|narrative)\b", context):
        return "disclosure"
    return default


_REFERENCE_SECTION_HEADING_RE = re.compile(
    r"(?im)^\s*(?:expected\s+(?:cross[- ]document\s+checks?|comparison\s+behavior|results?)|"
    r"(?:test|reference)\s+values?|comparison\s+examples?|illustrative\s+examples?|"
    r"expected\s+results?|reference\s+examples?)\s*[:\-]?\s*$"
)

_FINANCIAL_SECTION_HEADING_RE = re.compile(
    r"(?im)^\s*(?:consolidated\s+income\s+statement|income\s+statement|"
    r"statement\s+of\s+(?:income|operations|profit(?:\s+and\s+loss)?|cash\s+flows?)|"
    r"balance\s+sheet|cash\s+flow\s+statement|notes?\s+to\s+(?:the\s+)?financial\s+statements?)\s*[:\-]?\s*$"
)


def _is_reference_context(text: str, position: int) -> bool:
    """Return true when a match is under an instructional/reference heading."""
    if not text or position < 0:
        return False
    current_line_start = text.rfind("\n", 0, position) + 1
    current_line = text[current_line_start:text.find("\n", position) if "\n" in text[position:] else len(text)]
    if _REFERENCE_SECTION_HEADING_RE.search(current_line):
        return True
    last_reference = list(_REFERENCE_SECTION_HEADING_RE.finditer(text[:position + 1]))
    if not last_reference:
        return False
    last_reference_position = last_reference[-1].start()
    financial_headings = list(_FINANCIAL_SECTION_HEADING_RE.finditer(text[:position + 1]))
    last_financial_position = financial_headings[-1].start() if financial_headings else -1
    return last_reference_position > last_financial_position


def _find_non_reference_match(pattern: str, text: str, flags: int = 0) -> Optional[re.Match[str]]:
    """Find the first match that is not located in a reference section."""
    for match in re.finditer(pattern, text, flags):
        if not _is_reference_context(text, match.start()):
            return match
    return None


def _enrich_yearly_value(
    value: Any,
    currency: Optional[str],
    unit: Optional[str],
) -> Dict[str, Any]:
    parsed = parse_financial_number(
        str(value),
        inherited_currency=currency,
        inherited_unit=unit,
    )
    if parsed:
        return {
            "value": parsed["raw_value"],
            "numeric_value": parsed["numeric_value"],
            "currency": parsed["currency"],
            "unit": parsed["unit"],
            "unit_multiplier": parsed["unit_multiplier"],
        }
    return {
        "value": value,
        "numeric_value": None,
        "currency": currency,
        "unit": unit,
        "unit_multiplier": UNIT_MULTIPLIERS.get(unit or "", 1.0),
    }


def _extract_table_yearly_metrics_legacy(
    text: str,
    currency: Optional[str] = None,
    unit: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    if not text:
        return {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    table_start = None
    char_offsets: List[int] = []
    running_offset = 0
    for line in text.splitlines(True):
        if line.strip():
            char_offsets.append(running_offset)
        running_offset += len(line)
    for idx, line in enumerate(lines):
        line_position = char_offsets[idx] if idx < len(char_offsets) else 0
        if _is_reference_context(text, line_position):
            continue
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
        line_position = char_offsets[idx] if idx < len(char_offsets) else 0
        if _is_reference_context(text, line_position):
            continue
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
            if _is_temporal_year_label(candidate):
                continue
            if re.search(r"(?i)^\+?[$€£₹]?[-+]?\d[\d,]*\.?\d*\s*(?:billion|million|thousand|crores?|lakhs?|k|bn|m)?$", candidate):
                values.append(candidate)
                if len(values) >= 2:
                    break
        if len(values) >= 2:
            if len(header_years) >= 2:
                paired = [
                    {
                        "year": int(header_years[i]),
                        **_enrich_yearly_value(values[i], currency, unit),
                    }
                    for i in range(2)
                ]
                yearly[canonical] = sorted(paired, key=lambda item: int(item["year"]))
            else:
                yearly[canonical] = [
                    {"year": 2024, **_enrich_yearly_value(values[0], currency, unit)},
                    {"year": 2025, **_enrich_yearly_value(values[1], currency, unit)},
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
            sentence_position = text.find(sentence)
            if _is_reference_context(text, sentence_position):
                continue
            explicit_years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", sentence)]
            amount_tokens = re.findall(
                r"\(?\s*[-+]?\s*(?:US\$|[$€£₹]|Rs\.?|INR)?\s*\d[\d,]*(?:\.\d+)?\s*(?:crores?|cr|lakhs?|lac|billions?|bn|millions?|mn|thousands?|k|m)?\s*\)?",
                sentence,
                re.I,
            )
            amount_tokens = [
                token.strip() for token in amount_tokens
                if not re.fullmatch(r"(?:19|20)\d{2}", re.sub(r"\D", "", token))
                and re.search(r"(?:US\$|[$€£₹]|Rs\.?|INR|crores?|cr|lakhs?|lac|billions?|bn|millions?|mn|thousands?|k|m)\b", token, re.I)
            ]
            if len(explicit_years) >= 2 and len(amount_tokens) >= 2:
                for year, token in zip(explicit_years[-len(amount_tokens):], amount_tokens[-len(explicit_years):]):
                    parsed = parse_financial_number(
                        token,
                        inherited_currency=inherited_currency,
                        inherited_unit=inherited_unit,
                        is_per_share=is_per_share or spec.get("is_per_share", False),
                        is_percent=is_percent or spec.get("is_percent", False),
                    )
                    classified_metric = _classify_metric_candidate(metric_key, sentence, alias, parsed)
                    if classified_metric and not _is_temporal_metric_candidate(sentence, match.start(), parsed) and ((classified_metric == "revenue" and not re.search(r"\bsegment\b", sentence, re.I)) or parsed["raw_value"] not in seen_raw):
                        if classified_metric != "revenue":
                            seen_raw.add(parsed["raw_value"])
                        obs = dict(parsed)
                        obs.update({
                            "metric_name": classified_metric,
                            "canonical_label": "Segment Revenue" if classified_metric == "segment_revenue" else spec.get("canonical_name", metric_key.replace("_", " ").title()),
                            "statement_context": statement_context,
                            "report_year": year,
                            "is_canonical": False,
                        })
                        observations.append(obs)
                continue
            tail = sentence[match.end():]
            parsed = parse_financial_number(
                tail,
                inherited_currency=inherited_currency,
                inherited_unit=inherited_unit,
                is_per_share=is_per_share or spec.get("is_per_share", False),
                is_percent=is_percent or spec.get("is_percent", False),
            )
            if not parsed:
                continuation = re.search(rf"(?im)^\s*{alias}[^\n]*\n\s*([^\n]+)", text)
                if continuation:
                    parsed = parse_financial_number(
                        continuation.group(1),
                        inherited_currency=inherited_currency,
                        inherited_unit=inherited_unit,
                        is_per_share=is_per_share or spec.get("is_per_share", False),
                        is_percent=is_percent or spec.get("is_percent", False),
                    )
                    if parsed:
                        sentence = f"{sentence} {continuation.group(1)}"
            classified_metric = _classify_metric_candidate(metric_key, sentence, alias, parsed)
            if classified_metric and not _is_temporal_metric_candidate(sentence, match.start(), parsed) and ((classified_metric == "revenue" and not re.search(r"\bsegment\b", sentence, re.I)) or parsed["raw_value"] not in seen_raw):
                if classified_metric != "revenue":
                    seen_raw.add(parsed["raw_value"])
                obs = dict(parsed)
                obs["metric_name"] = classified_metric
                obs["canonical_label"] = "Segment Revenue" if classified_metric == "segment_revenue" else spec.get("canonical_name", metric_key.replace("_", " ").title())
                sentence_offset = text.find(sentence)
                nearby_context = text[max(0, sentence_offset - 160):sentence_offset].lower() if sentence_offset >= 0 else ""
                obs["statement_context"] = _infer_statement_context(sentence, nearby_context, statement_context)
                obs["report_year"] = _year_from_text(sentence, report_year or 2024)
                obs["is_canonical"] = False
                observations.append(obs)
    for alias in aliases:
        pattern = rf"(?i){alias}\s*[:\n\-]+\s*([^\n●]+)"
        for m in re.finditer(pattern, text):
            if _is_reference_context(text, m.start()):
                continue
            snippet = m.group(1)
            parsed = parse_financial_number(
                snippet,
                inherited_currency=inherited_currency,
                inherited_unit=inherited_unit,
                is_per_share=is_per_share or spec.get("is_per_share", False),
                is_percent=is_percent or spec.get("is_percent", False),
            )
            candidate_context = text[max(0, m.start() - 80):m.end()]
            classified_metric = _classify_metric_candidate(metric_key, candidate_context, alias, parsed)
            if classified_metric and not _is_temporal_metric_candidate(text, m.start(), parsed) and ((classified_metric == "revenue" and not re.search(r"\bsegment\b", text[max(0, m.start() - 80):m.end()], re.I)) or parsed["raw_value"] not in seen_raw):
                if classified_metric != "revenue":
                    seen_raw.add(parsed["raw_value"])
                obs = dict(parsed)
                obs["metric_name"] = classified_metric
                obs["canonical_label"] = "Segment Revenue" if classified_metric == "segment_revenue" else spec.get("canonical_name", metric_key.replace("_", " ").title())
                nearby_context = text[max(0, m.start() - 160):m.start()].lower()
                obs["statement_context"] = _infer_statement_context(candidate_context, nearby_context, statement_context)
                obs["report_year"] = _year_from_text(text[m.start():m.end()], report_year or 2024)
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


def _extract_material_weakness(text: str) -> Dict[str, Any]:
    matches = list(re.finditer(r"[^.!?\n]*(?:material weakness|material weaknesses)[^.!?\n]*[.!?]?", text or "", re.I))
    if not matches:
        return {"status": "not_found", "value": None, "evidence": None}
    sentence = matches[0].group(0).strip()
    negated = bool(
        re.search(r"\b(?:no|not|never|none|without)\b[^.!?\n]{0,80}\bmaterial\s+weakness(?:es)?\b", sentence, re.I)
        or re.search(r"\b(?:did|was|were|has|have)\s+not\b[^.!?\n]{0,80}\bmaterial\s+weakness(?:es)?\b", sentence, re.I)
        or re.search(r"\bmaterial\s+weakness(?:es)?\b[^.!?\n]{0,50}\b(?:not identified|not reported|does not exist)\b", sentence, re.I)
    )
    return {"status": "none_identified" if negated else "identified", "value": not negated, "evidence": sentence}


def _extract_cash_flow_reconciliation(
    text: str,
    inherited_currency: Optional[str] = None,
    inherited_unit: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    labels = {
        "beginning_cash": r"(?:beginning|opening)\s+cash(?:\s+and\s+cash\s+equivalents)?",
        "net_change_in_cash": r"(?:net\s+)?change\s+in\s+cash(?:\s+and\s+cash\s+equivalents)?",
        "ending_cash": r"(?:ending|closing)\s+cash(?:\s+and\s+cash\s+equivalents)?",
    }
    values: Dict[str, Any] = {}
    for key, label in labels.items():
        match = re.search(rf"{label}\s*(?:was|is|:|=)?\s*([^.;\n]+)", text or "", re.I)
        if match:
            parsed = parse_financial_number(
                match.group(1),
                inherited_currency=inherited_currency,
                inherited_unit=inherited_unit,
            )
            values[key] = parsed.get("raw_value") if parsed else match.group(1).strip()
        else:
            values[key] = None
    if not any(value is not None for value in values.values()):
        return None
    return reconcile_cash_flow(
        **values,
        inherited_currency=inherited_currency,
        inherited_unit=inherited_unit,
    )


def _get_evidence_for_financial_value(
    candidate: Optional[Dict[str, Any]],
    metric_label: str,
    display_value: Optional[str],
) -> Optional[str]:
    """
    Extract or construct evidence for a financial value.

    Priority order:
    1. exact_evidence from observation grounding (text snippet where metric was found)
    2. Fallback: constructed evidence from observation data
    3. None: if no evidence can be determined
    """
    if not candidate:
        return None

    # First priority: grounded evidence from text search
    exact_evidence = candidate.get("exact_evidence")
    if exact_evidence and exact_evidence.strip():
        return exact_evidence.strip()

    # Second priority: construct evidence from observation metadata
    # This ensures every metric has evidence even if grounding wasn't perfect
    raw_value = candidate.get("raw_value")
    statement_context = candidate.get("statement_context", "")

    if raw_value:
        evidence_parts = [f"{metric_label}: {raw_value}"]
        if statement_context and statement_context not in {"", "unknown"}:
            evidence_parts.append(f"(from {statement_context})")
        return " ".join(evidence_parts)

    # Final fallback: if we have display_value, use that
    if display_value:
        return f"{metric_label}: {display_value}"

    return None


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
    document_currency, document_unit = _detect_document_currency_unit(text)
    document_context = {"currency": document_currency, "unit": document_unit}
    table_curr, table_unit = extract_table_header_units(text)
    resolved_context = resolve_currency_unit_context(
        table_context={"currency": table_curr, "unit": table_unit},
        document_context=document_context,
    )
    table_curr = resolved_context["currency"] if resolved_context["currency"] != "UNKNOWN" else None
    table_unit = resolved_context["unit"] if resolved_context["unit"] != "units" else None
    yearly_metrics, table_observations = _extract_multi_year_financial_tables(
        text,
        chunk_records=chunk_records,
        document_context=document_context,
    )
    accounting_info, risk_metrics = _extract_accounting_notes_and_risks(text)
    material_weakness = _extract_material_weakness(text)
    cash_reconciliation = _extract_cash_flow_reconciliation(
        text,
        inherited_currency=table_curr,
        inherited_unit=table_unit,
    )
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
        c_id, p_num, ev_text, score, occurrence_section = _find_grounded_chunk_for_observation(
            obs,
            chunk_records=chunk_records,
            target_year=obs.get("report_year", target_year_int),
        )
        obs["source_chunk_id"] = c_id or metadata.get("chunk_id")
        matched_chunk = next((chunk for chunk in chunk_records if str(chunk.get("chunk_id")) == str(obs["source_chunk_id"])), None)
        matched_metadata = matched_chunk.get("metadata", {}) if isinstance(matched_chunk, dict) and isinstance(matched_chunk.get("metadata", {}), dict) else {}
        obs["source_file"] = matched_metadata.get("source_file") or matched_metadata.get("source") or source_name
        obs["page_number"] = p_num
        obs["exact_evidence"] = ev_text
        obs["source_page"] = p_num
        obs["source_page_end"] = (
            matched_chunk.get("page_end") or matched_metadata.get("page_end") or p_num
            if isinstance(matched_chunk, dict) else p_num
        )
        obs["source_section"] = occurrence_section or (
            matched_chunk.get("section_title") or matched_metadata.get("section_title") or matched_metadata.get("section")
            if isinstance(matched_chunk, dict) else matched_metadata.get("section_title") or matched_metadata.get("section")
        )
        obs["grounding_score"] = score
    all_observations = _deduplicate_observations(all_observations)
    observation_conflicts = _find_observation_conflicts(all_observations)
    for metric_key in METRIC_TAXONOMY:
        observations_by_year: Dict[int, Dict[str, Any]] = {}
        for obs in all_observations:
            if obs.get("metric_name") != metric_key:
                continue
            year = _normalize_year_value(obs.get("report_year"))
            if year is not None and obs.get("raw_value") is not None:
                observations_by_year.setdefault(year, obs)
        if len(observations_by_year) >= 2:
            label = METRIC_TAXONOMY[metric_key].get("canonical_name", metric_key.replace("_", " ").title())
            yearly_series = [
                {
                    "year": year,
                    "value": observations_by_year[year].get("raw_value"),
                    "numeric_value": observations_by_year[year].get("numeric_value"),
                    "unit": observations_by_year[year].get("unit"),
                    "currency": observations_by_year[year].get("currency"),
                    "chunk_id": observations_by_year[year].get("source_chunk_id"),
                    "source": observations_by_year[year].get("source_file"),
                }
                for year in sorted(observations_by_year)
            ]
            yearly_metrics[label] = yearly_series
    canonical_metrics: Dict[str, Optional[str]] = {}
    canonical_observations: Dict[str, Dict[str, Any]] = {}
    for metric_key in (
        "revenue", "gross_profit", "cost_of_revenue", "operating_income", "pretax_income",
        "net_income", "operating_margin", "eps", "basic_eps", "diluted_eps", "trend_eps",
        "total_assets", "total_liabilities", "total_equity", "cash_and_equivalents", "cash_flow",
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
            canonical_observations[metric_key] = cand
            canonical_metrics[metric_key] = cand["raw_value"]
        else:
            canonical_metrics[metric_key] = None
    for key, series_name in {
        "revenue": "Revenue",
        "gross_profit": "Gross Profit",
        "cost_of_revenue": "Cost of Revenue",
        "operating_income": "Operating Income",
        "pretax_income": "Pre-tax Income",
        "net_income": "Net Income",
        "operating_margin": "Operating Margin",
        "total_assets": "Total Assets",
        "total_liabilities": "Total Liabilities",
        "total_equity": "Total Equity",
        "cash_and_equivalents": "Cash and Cash Equivalents",
        "total_debt": "Total Debt",
        "cash_flow": "Cash Flow",
        "operating_cash_flow": "Operating Cash Flow",
        "free_cash_flow": "Free Cash Flow",
        "rd_expense": "R&D Expense",
        "eps": "EPS",
    }.items():
        if series_name in yearly_metrics:
            series = yearly_metrics[series_name]
            matched = next((item for item in series if item.get("year") == target_year_int), None)
            if matched and matched.get("value") and (
                canonical_metrics.get(key) is None
                or any(item.get("year") == target_year_int for item in series)
            ):
                canonical_metrics[key] = str(matched["value"])
    if not canonical_metrics.get("operating_cash_flow") and canonical_metrics.get("cash_flow"):
        canonical_metrics["operating_cash_flow"] = canonical_metrics["cash_flow"]
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
            "source_file": obs.get("source_file") or source_name,
            "page_number": p_num,
            "evidence": ev_snippet,
        })
        if obs.get("is_canonical") or m_key not in traceability:
            traceability[m_key] = {
                "metric": spec.get("canonical_name", m_key),
                "value": val,
                "numeric_value": obs.get("numeric_value"),
                "currency": obs.get("currency"),
                "unit": obs.get("unit"),
                "year": obs.get("report_year"),
                "source_chunk_id": c_id,
                "source_file": obs.get("source_file") or source_name,
                "page_number": p_num,
                "original_label": obs.get("canonical_label", spec.get("canonical_name", m_key)),
                "evidence": ev_snippet,
            }
    if "eps" not in traceability:
        eps_observation = next(
            (obs for obs in all_observations if obs.get("metric_name") == "basic_eps" and obs.get("is_canonical")),
            None,
        ) or next(
            (obs for obs in all_observations if obs.get("metric_name") == "diluted_eps" and obs.get("is_canonical")),
            None,
        )
        if eps_observation:
            traceability["eps"] = {
                "metric": "EPS",
                "value": eps_observation.get("raw_value"),
                "numeric_value": eps_observation.get("numeric_value"),
                "currency": eps_observation.get("currency"),
                "unit": eps_observation.get("unit"),
                "year": eps_observation.get("report_year"),
                "source_chunk_id": eps_observation.get("source_chunk_id"),
                "source_file": eps_observation.get("source_file") or source_name,
                "page_number": eps_observation.get("page_number"),
                "original_label": eps_observation.get("canonical_label", "EPS"),
                "evidence": eps_observation.get("exact_evidence", ""),
            }
    financial_value_keys = {
        "revenue": "Revenue",
        "gross_profit": "Gross Profit",
        "cost_of_revenue": "Cost of Revenue",
        "operating_income": "Operating Income",
        "pretax_income": "Pre-tax Income",
        "net_income": "Net Income",
        "operating_margin": "Operating Margin",
        "eps": "EPS",
        "basic_eps": "Basic EPS",
        "diluted_eps": "Diluted EPS",
        "trend_eps": "Performance Trend EPS",
        "total_assets": "Total Assets",
        "total_liabilities": "Total Liabilities",
        "total_equity": "Total Equity",
        "cash_and_equivalents": "Cash and Cash Equivalents",
        "cash_flow": "Cash Flow",
        "operating_cash_flow": "Operating Cash Flow",
        "free_cash_flow": "Free Cash Flow",
        "rd_expense": "R&D Expense",
        "total_debt": "Total Debt",
    }
    financial_values: Dict[str, Dict[str, Any]] = {}
    financial_value_conflicts: Dict[str, List[Dict[str, Any]]] = dict(observation_conflicts)
    for key, label in financial_value_keys.items():
        display_value = canonical_metrics.get(key)
        if display_value is None and key == "operating_cash_flow":
            display_value = canonical_metrics.get("cash_flow")
        candidates = [
            obs for obs in all_observations
            if obs.get("metric_name") == key and obs.get("raw_value") == display_value
        ]
        if not candidates and key == "eps":
            candidates = [
                obs for obs in all_observations
                if obs.get("metric_name") in {"basic_eps", "diluted_eps"}
                and obs.get("raw_value") == display_value
            ]
        candidate = canonical_observations.get(key)
        if candidate is None:
            candidate = next((obs for obs in candidates if obs.get("report_year") == target_year_int), None) or (candidates[0] if candidates else None)
        parsed = parse_financial_number(
            str(display_value),
            inherited_currency=table_curr,
            inherited_unit=table_unit,
            is_per_share=key in {"eps", "basic_eps", "diluted_eps", "trend_eps"},
        ) if display_value is not None else None
        financial_values[key] = {
            "metric": label,
            "value": parsed.get("numeric_value") if parsed else None,
            "display_value": display_value,
            "raw_value": display_value,
            "currency": candidate.get("currency") if candidate else (parsed.get("currency") if parsed else None),
            "unit_scale": candidate.get("unit") if candidate else (parsed.get("unit") if parsed else None),
            "period": candidate.get("report_year") if candidate else (target_year_int if display_value is not None else None),
            "year": candidate.get("report_year") if candidate else (target_year_int if display_value is not None else None),
            "status": (candidate.get("status") if candidate else (parsed.get("status") if parsed else "not_found")),
            "semantic_status": classify_financial_value_status(display_value),
            "source_file": candidate.get("source_file") if candidate else source_name,
            "source_page": candidate.get("source_page") if candidate else None,
            "source_page_end": candidate.get("source_page_end") if candidate else None,
            "source_chunk": candidate.get("source_chunk_id") if candidate else metadata.get("chunk_id"),
            "section": candidate.get("source_section") if candidate else None,
            "evidence": _get_evidence_for_financial_value(candidate, label, display_value) if candidate else None,
            "provenance": {
                "source_file": candidate.get("source_file") if candidate else source_name,
                "page": candidate.get("source_page") if candidate else None,
                "page_end": candidate.get("source_page_end") if candidate else None,
                "chunk_id": candidate.get("source_chunk_id") if candidate else metadata.get("chunk_id"),
                "section": candidate.get("source_section") if candidate else None,
            },
            "metric_type": "per_share" if key in {"eps", "basic_eps", "diluted_eps", "trend_eps"} else "financial",
            "conflict_status": "conflict" if key in financial_value_conflicts else "none_detected",
            "conflicts": financial_value_conflicts.get(key, []),
        }
    if financial_values.get("total_debt", {}).get("status") == "reported_zero":
        financial_values["total_debt"]["source_status"] = "nil"
    result: Dict[str, Any] = {
        "company_name": company_name,
        "report_year": report_year,
        "revenue": canonical_metrics.get("revenue"),
        "gross_profit": canonical_metrics.get("gross_profit"),
        "cost_of_revenue": canonical_metrics.get("cost_of_revenue"),
        "operating_income": canonical_metrics.get("operating_income"),
        "pretax_income": canonical_metrics.get("pretax_income"),
        "net_income": canonical_metrics.get("net_income"),
        "operating_margin": canonical_metrics.get("operating_margin"),
        "eps": canonical_metrics.get("eps"),
        "basic_eps": canonical_metrics.get("basic_eps"),
        "diluted_eps": canonical_metrics.get("diluted_eps"),
        "trend_eps": canonical_metrics.get("trend_eps"),
        "total_assets": canonical_metrics.get("total_assets"),
        "total_liabilities": canonical_metrics.get("total_liabilities"),
        "total_equity": canonical_metrics.get("total_equity"),
        "cash_and_equivalents": canonical_metrics.get("cash_and_equivalents"),
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
        "financial_values": financial_values,
        "material_weakness": material_weakness,
        "cash_reconciliation": cash_reconciliation,
        "financial_value_conflicts": financial_value_conflicts,
    }
    if metadata:
        for key in ("analysis_id", "document_id", "chunk_id", "source", "source_file"):
            if key in metadata and metadata.get(key) not in (None, ""):
                result[key] = str(metadata[key])
    for key in (
        "revenue", "gross_profit", "operating_income", "pretax_income",
        "net_income", "total_assets", "total_liabilities", "total_equity",
        "cash_flow", "operating_cash_flow", "free_cash_flow", "rd_expense",
        "total_debt", "cash_and_equivalents", "eps", "basic_eps", "diluted_eps", "trend_eps"
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
