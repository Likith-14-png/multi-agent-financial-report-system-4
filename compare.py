from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


METRIC_SEQUENCE = [
    "Revenue",
    "Operating Income",
    "Net Income",
    "Total Assets",
    "Total Liabilities",
    "Cash Flow",
    "EPS",
]


LEGACY_METRIC_ALIASES = {
    "revenue": "Revenue",
    "operating income": "Operating Income",
    "operating loss": "Operating Income",
    "net income": "Net Income",
    "net loss": "Net Income",
    "total assets": "Total Assets",
    "assets": "Total Assets",
    "total liabilities": "Total Liabilities",
    "liabilities": "Total Liabilities",
    "cash flow": "Cash Flow",
    "cash flow from operations": "Cash Flow",
    "eps": "EPS",
    "earnings per share": "EPS",
}


class ComparisonResult(dict):
    """Dictionary-like comparison payload with DataFrame-like compatibility."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        super().__init__(payload)
        self.columns = self._infer_columns(payload)

    @staticmethod
    def _infer_columns(payload: Dict[str, Any]) -> List[str]:
        records = payload.get("records") or []
        if not records:
            return [
                "Metric",
                "Value",
                "Unit",
                "PreviousYear",
                "PreviousValue",
                "CurrentYear",
                "CurrentValue",
                "AbsoluteChange",
                "PercentageChange",
                "Direction",
                "SourceChunks",
                "Source",
            ]
        columns: List[str] = []
        for key in records[0].keys():
            columns.append(key)
        return columns

    def to_dict(self, orient: str = "records") -> Any:
        if orient == "records":
            return list(self.get("records", []))
        if orient == "dict":
            return {"metadata": self.get("metadata"), "records": self.get("records", [])}
        return dict(self)


def _normalize_year_value(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        year = int(value)
        if 1900 <= year <= 2100:
            return year
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("FY", "").replace("FY ", "").strip()
    candidates = re.findall(r"(?:19|20)\d{2}", text)
    if not candidates:
        return None
    year = int(candidates[-1])
    return year if 1900 <= year <= 2100 else None


def _normalize_metric_name(metric_name: str) -> str:
    normalized = metric_name.strip().lower().replace("_", " ")
    return normalized


def _metric_key_for_lookup(metric_name: str) -> str:
    key = _normalize_metric_name(metric_name)
    return LEGACY_METRIC_ALIASES.get(key, key)


def _canonical_metric_name(metric_name: str) -> str:
    if not metric_name:
        return ""
    normalized = _normalize_metric_name(metric_name)
    for candidate, canonical in LEGACY_METRIC_ALIASES.items():
        if normalized == candidate:
            return canonical
    return metric_name.strip()


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "not available", "unavailable", "none", "null"}:
        return None
    cleaned = text.replace("$", "").replace("€", "").replace("£", "").replace(",", "").replace("%", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_numeric_value(value: Any) -> Tuple[Optional[float], Optional[str]]:
    if value is None or value == "":
        return None, None
    if isinstance(value, (int, float)):
        return float(value), "unitless"
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "not available", "unavailable", "none", "null"}:
        return None, None

    lower = text.lower().replace(" ", "")
    if "%" in lower:
        match = re.search(r"[-+]?\d*\.?\d+", lower)
        return (float(match.group(0)), "percent") if match else (None, None)
    unit = "unitless"
    if "crore" in lower or "cr" in lower:
        unit = "crore"
        lower = lower.replace("crores", "").replace("crore", "").replace("crs", "").replace("cr", "")
    elif "lakh" in lower or "lac" in lower:
        unit = "lakh"
        lower = lower.replace("lakhs", "").replace("lakh", "").replace("lacs", "").replace("lac", "")
    elif "billion" in lower:
        unit = "billion"
        lower = lower.replace("billion", "")
    elif "million" in lower:
        unit = "million"
        lower = lower.replace("million", "")
    elif "thousand" in lower:
        unit = "thousand"
        lower = lower.replace("thousand", "")
    elif lower.endswith("bn"):
        unit = "billion"
        lower = lower[:-2]
    elif lower.endswith("m") and not lower.endswith("mm"):
        unit = "million"
        lower = lower[:-1]
    elif lower.endswith("k"):
        unit = "thousand"
        lower = lower[:-1]

    cleaned = lower.replace("₹", "").replace("rs.", "").replace("rs", "").replace("inr", "").replace("$", "").replace("€", "").replace("£", "").replace(",", "")
    match = re.search(r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?", cleaned)
    if not match:
        return None, None
    numeric = float(match.group(0))
    return numeric, unit


def _convert_to_unit(value: float, source_unit: Optional[str], target_unit: str) -> float:
    if value is None:
        return value
    if source_unit in (None, "unitless") or target_unit in (None, "unitless") or source_unit == target_unit:
        return value
    conversion_map = {
        "thousand": {"thousand": 1.0, "million": 1_000.0, "billion": 1_000_000.0},
        "million": {"thousand": 1.0 / 1_000.0, "million": 1.0, "billion": 1.0 / 1_000.0},
        "billion": {"thousand": 1.0 / 1_000_000.0, "million": 1.0 / 1_000.0, "billion": 1.0},
        "crore": {"crore": 1.0, "lakh": 100.0},
        "lakh": {"crore": 0.01, "lakh": 1.0},
    }
    factor = conversion_map.get(source_unit, {}).get(target_unit)
    if factor is None:
        return value
    return value * factor


def _currency_for_value(value: Any, record: Dict[str, Any]) -> Optional[str]:
    explicit = record.get("currency") or record.get("currency_code")
    if explicit:
        return str(explicit).upper()
    text = str(value or "")
    if "₹" in text or re.search(r"\b(?:INR|Rs\.?)\b", text, re.I):
        return "INR"
    if "€" in text or re.search(r"\bEUR\b", text, re.I):
        return "EUR"
    if "£" in text or re.search(r"\bGBP\b", text, re.I):
        return "GBP"
    if "$" in text or re.search(r"\bUSD\b", text, re.I):
        return "USD"
    if "¥" in text or re.search(r"\b(?:JPY|CNY)\b", text, re.I):
        return "JPY"
    return None


def _comparison_metric_key(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9%]+", " ", str(value or "").lower()).strip()
    aliases = {
        "sales": "revenue",
        "net sales": "revenue",
        "net profit": "net income",
        "profit": "net income",
        "operating profit": "operating income",
        "ebit": "operating income",
        "operating margin": "operating margin",
        "debt to equity": "debt to equity",
        "debt equity": "debt to equity",
        "total debt": "debt",
        "borrowings": "debt",
        "total shareholders equity": "total equity",
        "shareholders equity": "total equity",
        "total stockholders equity": "total equity",
    }
    return aliases.get(normalized, normalized)


def _comparison_unit_value(value: float, unit: Optional[str], target_unit: Optional[str]) -> Optional[float]:
    if value is None or target_unit is None:
        return None
    base_units = {
        "thousand": 1_000.0,
        "million": 1_000_000.0,
        "billion": 1_000_000_000.0,
        "crore": 10_000_000.0,
        "lakh": 100_000.0,
        "percent": 0.01,
        "unitless": 1.0,
    }
    source_factor = base_units.get(unit or "unitless")
    target_factor = base_units.get(target_unit)
    if source_factor is None or target_factor is None:
        return None
    return value * source_factor / target_factor


def _comparison_period(record: Dict[str, Any]) -> Optional[int]:
    return _normalize_year_value(record.get("report_year") or record.get("year") or record.get("period"))


def _comparison_period_kind(record: Dict[str, Any]) -> Optional[str]:
    if not isinstance(record, dict):
        return None
    period_value = record.get("period") or record.get("report_period") or record.get("report_year") or record.get("year")
    if period_value in (None, ""):
        return None
    text = str(period_value).strip().lower()
    if not text:
        return None
    if re.search(r"\bq[1-4]\b|\bquarter\b", text):
        return "quarter"
    if re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|month)\b", text):
        return "month"
    if re.search(r"(?:19|20)\d{2}|fy\d{2,4}|fiscal", text):
        return "year"
    if re.fullmatch(r"\d{4}", text):
        return "year"
    return None


def _comparison_context(record: Dict[str, Any]) -> Optional[str]:
    value = record.get("statement_context") or record.get("context") or record.get("section_type") or record.get("section")
    if not value:
        return None
    text = re.sub(r"[^a-z]+", " ", str(value).lower()).strip()
    if "segment" in text or "division" in text or "geographic" in text:
        return "segment"
    if "standalone" in text or "separate" in text:
        return "standalone"
    if "consolidated" in text or "group" in text:
        return "consolidated"
    if "income statement" in text or "balance sheet" in text or "cash flow" in text or "financial statement" in text:
        return "financial_statement"
    return text


def _comparison_definition(record: Dict[str, Any], metric_key: str) -> Optional[str]:
    value = record.get("metric_definition") or record.get("definition") or record.get("metric_type")
    if value:
        return re.sub(r"[^a-z]+", " ", str(value).lower()).strip()
    if metric_key in {"revenue", "operating income", "net income", "total assets", "total liabilities", "total equity", "debt", "cash flow"}:
        return "financial_amount"
    if metric_key in {"operating margin", "net margin", "gross margin", "debt to equity"}:
        return "financial_ratio"
    if metric_key == "eps":
        return "per_share"
    return None


def _comparison_metric_type(metric_name: str, unit: Optional[str] = None) -> str:
    """Classify a metric before applying any unit conversion."""
    normalized = _normalize_metric_name(metric_name)
    unit_name = str(unit or "").lower().replace("-", "_")
    if unit_name in {"per_share", "per share"} or normalized in {"eps", "basic eps", "diluted eps"}:
        return "per_share"
    if unit_name in {"percent", "%"} or "margin" in normalized or "growth" in normalized:
        return "percentage"
    if unit_name in {"x", "ratio", "multiple"} or "ratio" in normalized or "debt to equity" in normalized:
        return "ratio"
    if unit_name == "days" or normalized.endswith(" days"):
        return "days"
    if normalized in {
        "revenue", "gross profit", "cost of revenue", "operating income", "net income",
        "total assets", "total liabilities", "total equity", "debt", "total debt",
        "cash", "cash flow", "operating cash flow", "free cash flow",
    }:
        return "monetary"
    return "other"


def resolve_comparison_context(
    metric_name: str,
    numeric_value: Optional[float],
    currency: Optional[str] = None,
    unit: Optional[str] = None,
    unit_multiplier: Optional[float] = None,
    raw_value: Any = None,
) -> Dict[str, Any]:
    """Resolve authoritative comparison metadata without reinterpreting it."""
    metric_type = _comparison_metric_type(metric_name, unit)
    normalized_unit = str(unit).lower().replace(" ", "_") if unit else None
    if metric_type == "per_share":
        normalized_unit = "per_share"
    elif metric_type == "percentage":
        normalized_unit = "percent"
    elif metric_type == "ratio":
        normalized_unit = "x"
    if unit_multiplier is None:
        unit_multiplier = {
            "thousand": 1_000.0,
            "million": 1_000_000.0,
            "billion": 1_000_000_000.0,
            "lakh": 100_000.0,
            "crore": 10_000_000.0,
        }.get(normalized_unit, 1.0)
    return {
        "numeric_value": numeric_value,
        "currency": str(currency).upper() if currency else None,
        "unit": normalized_unit or ("unitless" if metric_type == "other" else None),
        "unit_multiplier": 1.0 if metric_type in {"per_share", "percentage", "ratio", "days", "other"} else float(unit_multiplier),
        "metric_type": metric_type,
        "is_monetary": metric_type == "monetary",
        "raw_value": raw_value,
    }


def _coalesce_first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _structured_comparison_value(record: Dict[str, Any], metric_name: str) -> Dict[str, Any]:
    """Use structured extraction fields first and parse raw values only as fallback."""
    nested_value = record.get("value") if isinstance(record.get("value"), dict) else None
    source_record = {**record, **(nested_value or {})}
    raw_value = record.get("raw_value")
    if raw_value is None:
        raw_value = source_record.get("display_value")
    if raw_value is None:
        metric_key = _comparison_metric_key(metric_name)
        raw_value = _coalesce_first_non_none(
            record.get("value"),
            record.get("current_value"),
            record.get("amount"),
            record.get(metric_key),
            record.get(metric_key.replace(" ", "_")),
            record.get(metric_name),
        )
    numeric_value = source_record.get("numeric_value")
    unit = source_record.get("unit") or source_record.get("unit_scale")
    currency = source_record.get("currency") or source_record.get("currency_code")
    unit_multiplier = source_record.get("unit_multiplier")
    if numeric_value is None:
        numeric_value, parsed_unit = _parse_numeric_value(raw_value)
        unit = unit or parsed_unit
    context = resolve_comparison_context(
        metric_name,
        numeric_value,
        currency=currency or _currency_for_value(raw_value, record),
        unit=unit,
        unit_multiplier=unit_multiplier,
        raw_value=raw_value,
    )
    return context


def _normalized_comparison_value(context: Dict[str, Any]) -> Optional[float]:
    if context.get("numeric_value") is None:
        return None
    if context.get("is_monetary"):
        return context["numeric_value"] * context.get("unit_multiplier", 1.0)
    return context["numeric_value"]


def _comparison_pair_values(
    metric_name: str,
    first: Dict[str, Any],
    second: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Normalize a pair only when monetary source units differ."""
    first_value = first.get("numeric_value")
    second_value = second.get("numeric_value")
    if first_value is None or second_value is None:
        return first_value, second_value, first.get("unit") or second.get("unit")
    if first.get("metric_type") != "monetary" or first.get("unit") == second.get("unit"):
        return first_value, second_value, first.get("unit") or second.get("unit")
    return _normalized_comparison_value(first), _normalized_comparison_value(second), "absolute"


def _comparison_payload(
    metric_label: str,
    company_a: Dict[str, Any],
    company_b: Dict[str, Any],
    a_raw: Any,
    b_raw: Any,
    a_value: Optional[float],
    b_value: Optional[float],
    a_unit: Optional[str],
    b_unit: Optional[str],
    reason: str,
) -> Dict[str, Any]:
    context_a = _structured_comparison_value(company_a, metric_label)
    context_b = _structured_comparison_value(company_b, metric_label)
    return {
        "metric": metric_label,
        "company_a": {"company_name": company_a.get("company_name") or "Company A", "value": a_raw, "currency": context_a.get("currency"), "unit": context_a.get("unit")},
        "company_b": {"company_name": company_b.get("company_name") or "Company B", "value": b_raw, "currency": context_b.get("currency"), "unit": context_b.get("unit")},
        "difference": None,
        "direction": "unavailable",
        "unit": None,
        "comparison_status": "not_comparable",
        "absolute_difference": None,
        "percentage_difference": None,
        "difference_basis": "company_b_minus_company_a",
        "metric_direction": None,
        "better_company": None,
        "interpretation": f"Comparison cannot be performed because {reason}.",
        "not_comparable_reason": reason,
        "comparability_metadata": {
            "original_company_a_value": company_a,
            "original_company_b_value": company_b,
            "normalized_company_a_value": None,
            "normalized_company_b_value": None,
            "currency": None,
            "unit_scale": None,
            "reporting_period": None,
            "metric_name": metric_label,
            "metric_equivalence": False,
            "normalization_status": "rejected",
        },
    }


def _has_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return False
    if isinstance(value, dict):
        if _has_missing_value(value.get("value")):
            return True
        status = value.get("status")
        semantic_status = value.get("semantic_status")
        for label in (status, semantic_status):
            if isinstance(label, str):
                normalized = label.strip().lower()
                if normalized in {"not_found", "missing", "not available", "unavailable", "none", "null", "not disclosed"}:
                    return True
        return False
    text = str(value).strip()
    return not text or text.lower() in {
        "na",
        "n/a",
        "not available",
        "unavailable",
        "none",
        "null",
        "not disclosed",
    }


def _has_missing_status(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    if isinstance(record.get("value"), dict) and _has_missing_status(record["value"]):
        return True
    for key in ("status", "semantic_status", "value_status"):
        status_value = record.get(key)
        if isinstance(status_value, str):
            normalized = status_value.strip().lower()
            if normalized in {"not_found", "missing", "not available", "unavailable", "none", "null", "not disclosed"}:
                return True
    return False


def _clean_source_chunk_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lower = text.lower()
    if lower.endswith(".pdf") or lower.endswith(".txt") or lower.endswith(".docx"):
        return None
    if re.fullmatch(r".*\.(?:pdf|txt|docx)", text, re.I):
        return None
    return text


def _extract_source_chunks(entry: Any) -> List[str]:
    if isinstance(entry, dict):
        chunks: List[str] = []
        for key in ("source_chunks", "evidence", "evidence_text", "citation", "source"):
            value = entry.get(key)
            if isinstance(value, list):
                for item in value:
                    cleaned = _clean_source_chunk_value(item)
                    if cleaned and cleaned not in chunks:
                        chunks.append(cleaned)
            elif isinstance(value, tuple):
                for item in value:
                    cleaned = _clean_source_chunk_value(item)
                    if cleaned and cleaned not in chunks:
                        chunks.append(cleaned)
            elif isinstance(value, str) and value.strip():
                cleaned = _clean_source_chunk_value(value)
                if cleaned and cleaned not in chunks:
                    chunks.append(cleaned)

        chunk_id = entry.get("chunk_id")
        cleaned_chunk_id = _clean_source_chunk_value(chunk_id)
        if cleaned_chunk_id and cleaned_chunk_id not in chunks:
            chunks.append(cleaned_chunk_id)
        return list(dict.fromkeys(chunks))
    if isinstance(entry, list):
        chunks = []
        for item in entry:
            for chunk in _extract_source_chunks(item):
                if chunk and chunk not in chunks:
                    chunks.append(chunk)
        return chunks
    return []


def _filter_valid_source_chunks(chunks: Iterable[Any]) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for chunk in chunks or []:
        value = _clean_source_chunk_value(chunk)
        if value is None:
            continue
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _extract_yearly_metrics_from_text(text: str, current_year: Any = None) -> Dict[str, List[Dict[str, Any]]]:
    if not isinstance(text, str) or not text.strip():
        return {}

    lines = [line.strip() for line in text.splitlines()]
    year_tokens = sorted({int(year) for year in re.findall(r"(?:19|20)\d{2}", text)})
    if not year_tokens:
        return {}

    current_year_value = _normalize_year_value(current_year) or max(year_tokens)
    prior_year_value = max((year for year in year_tokens if year < current_year_value), default=None)
    metric_years = {"current": current_year_value, "prior": prior_year_value}

    def _extract_numeric_tokens_from_block(block_lines: List[str]) -> List[str]:
        tokens: List[str] = []
        for line in block_lines:
            for match in re.findall(r"[-+]?\$?\d[\d,]*(?:\.\d+)?\s*(?:billion|million|thousand|k|bn|m)?", line, flags=re.I):
                cleaned = match.strip().replace("$", "").replace(",", "").replace(" ", "")
                if not cleaned:
                    continue
                if re.fullmatch(r"(?:19|20)\d{2}", cleaned):
                    continue
                if re.fullmatch(r"\d{1,2}", cleaned) and not re.search(r"(?:billion|million|thousand|k|bn|m)", line, flags=re.I):
                    continue
                if cleaned.endswith("."):
                    cleaned = cleaned[:-1]
                if cleaned.count(".") > 1:
                    continue
                tokens.append(cleaned)
        return tokens

    result: Dict[str, List[Dict[str, Any]]] = {}
    for metric_name in METRIC_SEQUENCE:
        label = metric_name.lower()
        matches: List[Dict[str, Any]] = []
        for idx, line in enumerate(lines):
            if label not in line.lower():
                continue
            window = lines[idx + 1: idx + 8]
            numeric_tokens = _extract_numeric_tokens_from_block(window)
            if len(numeric_tokens) >= 2:
                ordered = []
                for token in numeric_tokens[:4]:
                    if token not in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}:
                        ordered.append(token)
                if len(ordered) >= 2:
                    numeric_tokens = ordered[:2]
                else:
                    numeric_tokens = numeric_tokens[:2]
                for token_index, raw_value in enumerate(numeric_tokens):
                    metric_year = metric_years["prior" if token_index == 0 and prior_year_value is not None else "current"]
                    matches.append({"year": metric_year, "value": raw_value})
                break
        if matches:
            result[metric_name] = matches
    return result


def _metric_series_for_name(metric_name: str, extracted_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    canonical = _canonical_metric_name(metric_name)
    registry: Dict[str, Any] = {}

    direct_key = _metric_key_for_lookup(metric_name)
    if direct_key in extracted_metrics:
        registry["direct"] = extracted_metrics.get(direct_key)

    for alt_key in (metric_name, canonical.lower().replace(" ", "_"), canonical.lower()):
        if alt_key in extracted_metrics:
            registry["alt"] = extracted_metrics.get(alt_key)

    yearly = extracted_metrics.get("yearly_metrics") or extracted_metrics.get("metrics_by_year")
    if not isinstance(yearly, dict):
        source_text = extracted_metrics.get("source_text") or extracted_metrics.get("text") or ""
        source_year = extracted_metrics.get("report_year")
        yearly = _extract_yearly_metrics_from_text(source_text, source_year)

    if isinstance(yearly, dict):
        for yearly_metric_name, yearly_values in yearly.items():
            if _canonical_metric_name(yearly_metric_name) == canonical or _canonical_metric_name(yearly_metric_name) == metric_name:
                registry["yearly"] = yearly_values

    metrics_list = extracted_metrics.get("metrics")
    if isinstance(metrics_list, list):
        matches = []
        for item in metrics_list:
            if not isinstance(item, dict):
                continue
            item_metric = item.get("metric") or item.get("name")
            if _canonical_metric_name(item_metric) == canonical:
                matches.append(item)
        if matches:
            registry["list"] = matches

    observation_list = extracted_metrics.get("observations") or extracted_metrics.get("detailed_metrics") or []
    if isinstance(observation_list, list):
        matches = []
        for item in observation_list:
            if not isinstance(item, dict):
                continue
            item_metric = item.get("metric") or item.get("metric_name") or item.get("normalized_name") or item.get("name")
            if _canonical_metric_name(item_metric) == canonical or _canonical_metric_name(item_metric) == metric_name:
                year = item.get("report_year") or item.get("year") or item.get("period")
                value = item.get("raw_value") if item.get("raw_value") is not None else item.get("value")
                if year is not None and value is not None:
                    matches.append({**item, "year": year, "value": value})
        if matches:
            registry["observations"] = matches

    combined: List[Dict[str, Any]] = []
    deduped: set[Tuple[Any, Any]] = set()
    for source_key in ("yearly", "observations", "list"):
        series = registry.get(source_key)
        if not isinstance(series, list):
            continue
        for item in series:
            if not isinstance(item, dict):
                continue
            year = item.get("year") or item.get("period") or item.get("report_year")
            value = item.get("value") or item.get("amount") or item.get("raw_value")
            if year is None or value is None:
                continue
            key = (_normalize_year_value(year), value)
            if key in deduped:
                continue
            deduped.add(key)
            combined.append({**item, "year": year, "value": value})

    direct_value = registry.get("direct") or registry.get("alt")
    direct_year = _normalize_year_value(extracted_metrics.get("report_year"))
    if combined:
        if direct_value is not None and direct_year is not None and not any(_normalize_year_value(item.get("year")) == direct_year for item in combined):
            combined.insert(0, {
                "year": direct_year,
                "value": direct_value,
                "numeric_value": extracted_metrics.get("numeric_value"),
                "currency": extracted_metrics.get("currency"),
                "unit": extracted_metrics.get("unit") or extracted_metrics.get("unit_scale"),
                "unit_multiplier": extracted_metrics.get("unit_multiplier"),
                "source": extracted_metrics.get("source"),
                "chunk_id": extracted_metrics.get("chunk_id"),
                "source_chunks": extracted_metrics.get("source_chunks"),
            })
        return sorted(combined, key=lambda item: _normalize_year_value(item.get("year")) or -1)

    if "list" in registry:
        items = registry["list"]
        normalized = []
        for item in items:
            year = item.get("year") or item.get("period") or item.get("report_year")
            value = item.get("value") or item.get("amount")
            if value is not None:
                normalized.append({**item, "year": year, "value": value})
        return normalized

    if direct_value is None:
        return []
    if isinstance(direct_value, list):
        normalized = []
        for item in direct_value:
            if isinstance(item, dict):
                year = item.get("year") or item.get("period") or item.get("report_year")
                value = item.get("value") or item.get("amount")
                if value is not None:
                    normalized.append({**item, "year": year, "value": value})
        return normalized
    year = extracted_metrics.get("report_year")
    return [{
        "year": year,
        "value": direct_value,
        "numeric_value": extracted_metrics.get("numeric_value"),
        "currency": extracted_metrics.get("currency"),
        "unit": extracted_metrics.get("unit") or extracted_metrics.get("unit_scale"),
        "unit_multiplier": extracted_metrics.get("unit_multiplier"),
        "source": extracted_metrics.get("source"),
        "chunk_id": extracted_metrics.get("chunk_id"),
        "source_chunks": extracted_metrics.get("source_chunks"),
    }]


def _direction_for_change(current_value: float, previous_value: float) -> str:
    if current_value > previous_value:
        return "increase"
    if current_value < previous_value:
        return "decrease"
    return "unchanged"


def _percentage_change(current_value: float, previous_value: float) -> Optional[float]:
    if previous_value == 0:
        if current_value == 0:
            return 0.0
        return None
    value = ((current_value - previous_value) / previous_value) * 100.0
    return round(value, 2)


def _rounded_float(value: Optional[float], digits: int = 10) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _serialize_record(metric_name: str, current_year: Any, current_value: Any, unit: Any, previous_year: Any = None, previous_value: Any = None, source: Any = None, source_chunks: Optional[List[str]] = None) -> Dict[str, Any]:
    current_observation = current_value if isinstance(current_value, dict) else {"value": current_value}
    previous_observation = previous_value if isinstance(previous_value, dict) else {"value": previous_value}
    current_context = _structured_comparison_value(current_observation, metric_name)
    previous_context = _structured_comparison_value(previous_observation, metric_name)
    current_source_numeric = current_context.get("numeric_value")
    previous_source_numeric = previous_context.get("numeric_value")
    current_numeric, previous_numeric, comparison_unit = _comparison_pair_values(metric_name, current_context, previous_context)
    chosen_unit = unit or comparison_unit or current_context.get("unit") or "unitless"
    chosen_currency = current_context.get("currency") or previous_context.get("currency")
    observation_source = (
        source
        or current_observation.get("source")
        or current_observation.get("source_file")
        or current_observation.get("evidence")
        or current_observation.get("evidence_text")
        or "Extracted Financial Metrics"
    )
    observation_chunks = (
        source_chunks
        or current_observation.get("source_chunks")
        or _extract_source_chunks(current_observation)
        or []
    )
    evidence_text = (
        current_observation.get("evidence")
        or current_observation.get("evidence_text")
        or current_observation.get("exact_evidence")
        or current_observation.get("raw_value")
    )

    record: Dict[str, Any] = {
        "metric": metric_name,
        "Metric": metric_name,
        "value": current_source_numeric if current_source_numeric is not None else current_value,
        "Value": current_source_numeric if current_source_numeric is not None else current_value,
        "unit": chosen_unit,
        "Unit": chosen_unit,
        "currency": chosen_currency,
        "metric_type": current_context.get("metric_type"),
        "unit_multiplier": current_context.get("unit_multiplier"),
        "comparison_value": current_numeric,
        "current_year": current_year,
        "CurrentYear": current_year,
        "current_value": current_numeric,
        "CurrentValue": current_numeric,
        "source": observation_source,
        "Source": observation_source,
        "evidence": evidence_text,
        "source_chunks": observation_chunks,
        "SourceChunks": observation_chunks,
    }

    record["previous_year"] = previous_year
    record["PreviousYear"] = previous_year
    record["previous_value"] = previous_numeric
    record["PreviousValue"] = previous_numeric
    record["previous_source_value"] = previous_source_numeric

    if previous_year is not None:
        if current_numeric is not None and previous_numeric is not None:
            absolute_change = _rounded_float(current_numeric - previous_numeric)
            record["absolute_change"] = absolute_change
            record["AbsoluteChange"] = absolute_change
            percent_change = _percentage_change(current_numeric, previous_numeric)
            record["percentage_change"] = percent_change
            record["PercentageChange"] = percent_change
            direction = _direction_for_change(current_numeric, previous_numeric)
            record["direction"] = direction
            record["Direction"] = direction
        else:
            record["absolute_change"] = None
            record["AbsoluteChange"] = None
            record["percentage_change"] = None
            record["PercentageChange"] = None
            record["direction"] = "unavailable"
            record["Direction"] = "unavailable"
    else:
        record["absolute_change"] = None
        record["AbsoluteChange"] = None
        record["percentage_change"] = None
        record["PercentageChange"] = None
        record["direction"] = "unavailable"
        record["Direction"] = "unavailable"

    return record


def _coalesce_first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def compare_company_metrics(company_a: Dict[str, Any], company_b: Dict[str, Any], metric_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Compare two companies' metrics with strict isolation of observations.

    Company A and Company B observations are kept completely separate:
    - Conflicts are company-specific and never mixed across companies
    - Evidence is preserved per company
    - Company identities are never reversed or contaminated
    """
    metric_label = metric_name or company_a.get("metric") or company_b.get("metric") or "Revenue"
    m_key = metric_label.lower().replace(" ", "_")

    # Company A observation extraction with strict scoping
    a_raw = _coalesce_first_non_none(
        company_a.get("value"),
        company_a.get("current_value"),
        company_a.get("amount"),
        company_a.get(m_key),
        company_a.get(metric_label),
    )
    a_raw = None if isinstance(a_raw, dict) and "value" in a_raw else a_raw  # Sanitize dict with conflicts

    # Company B observation extraction with strict scoping
    b_raw = _coalesce_first_non_none(
        company_b.get("value"),
        company_b.get("current_value"),
        company_b.get("amount"),
        company_b.get(m_key),
        company_b.get(metric_label),
    )
    b_raw = None if isinstance(b_raw, dict) and "value" in b_raw else b_raw  # Sanitize dict with conflicts
    metric_a = _comparison_metric_key(company_a.get("metric") or metric_label)
    metric_b = _comparison_metric_key(company_b.get("metric") or metric_label)
    requested_metric = _comparison_metric_key(metric_label)
    a_context = _structured_comparison_value(company_a, metric_label)
    b_context = _structured_comparison_value(company_b, metric_label)
    a_value = a_context.get("numeric_value")
    b_value = b_context.get("numeric_value")
    a_unit = a_context.get("unit")
    b_unit = b_context.get("unit")
    if metric_a != requested_metric or metric_b != requested_metric or metric_a != metric_b:
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "the metrics are not equivalent")

    currency_a = a_context.get("currency")
    currency_b = b_context.get("currency")
    if currency_a and currency_b and currency_a != currency_b:
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "the currencies differ")

    period_a = _comparison_period(company_a)
    period_b = _comparison_period(company_b)
    period_kind_a = _comparison_period_kind(company_a)
    period_kind_b = _comparison_period_kind(company_b)
    if (
        period_a is not None
        and period_b is not None
        and period_kind_a is not None
        and period_kind_b is not None
        and period_kind_a != period_kind_b
    ):
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "the reporting periods differ in granularity")

    context_a = _comparison_context(company_a)
    context_b = _comparison_context(company_b)
    if context_a and context_b and context_a != context_b:
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "the statement contexts differ")
    definition_a = _comparison_definition(company_a, requested_metric)
    definition_b = _comparison_definition(company_b, requested_metric)
    if definition_a and definition_b and definition_a != definition_b:
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "the metric definitions differ")

    if _has_missing_status(company_a) or _has_missing_status(company_b):
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "a value is missing")

    if _has_missing_value(a_raw) or _has_missing_value(b_raw) or a_value is None or b_value is None:
        reason = "a value is missing" if _has_missing_value(a_raw) or _has_missing_value(b_raw) else "a value is not numeric"
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, reason)

    metric_type = a_context.get("metric_type")
    if metric_type != b_context.get("metric_type"):
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "the metric types differ")
    if metric_type == "monetary" and (a_unit is None or b_unit is None):
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "a monetary unit is unknown")
    normalized_a, normalized_b, target_unit = _comparison_pair_values(metric_label, a_context, b_context)
    target_unit = target_unit or "unitless"
    if normalized_a is None or normalized_b is None:
        return _comparison_payload(metric_label, company_a, company_b, a_raw, b_raw, a_value, b_value, a_unit, b_unit, "the units cannot be normalized")

    if period_a is not None and period_b is not None and period_a != period_b:
        if period_a > period_b:
            previous_value = normalized_b
            current_value = normalized_a
            previous_company = company_b
            current_company = company_a
        else:
            previous_value = normalized_a
            current_value = normalized_b
            previous_company = company_a
            current_company = company_b
    else:
        previous_value = normalized_a
        current_value = normalized_b
        previous_company = company_a
        current_company = company_b

    difference = _rounded_float(current_value - previous_value)
    direction = "increase" if difference > 0 else "decrease" if difference < 0 else "unchanged"
    status = "equal" if math.isclose(previous_value, current_value, rel_tol=0.0, abs_tol=1e-10) else "comparable"
    if previous_value == 0 and current_value == 0:
        percentage_difference = 0.0
    elif previous_value == 0:
        percentage_difference = None
    else:
        percentage_difference = _percentage_change(current_value, previous_value)
    direction_rules = {
        "revenue": "higher_better",
        "operating income": "higher_better",
        "operating margin": "higher_better",
        "net income": "higher_better",
        "total liabilities": "lower_better",
        "debt": "lower_better",
        "debt to equity": "lower_better",
        "cash flow": "higher_better",
        "total assets": "neutral",
        "total equity": "neutral",
    }
    metric_direction = direction_rules.get(requested_metric, "higher_better")
    better_company = None
    if status != "equal" and metric_direction != "neutral":
        if metric_direction == "higher_better":
            if current_value > previous_value:
                better_company = current_company.get("company_name") or "Company B"
            elif current_value < previous_value:
                better_company = previous_company.get("company_name") or "Company A"
        else:
            if current_value < previous_value:
                better_company = current_company.get("company_name") or "Company B"
            elif current_value > previous_value:
                better_company = previous_company.get("company_name") or "Company A"
    if status == "equal":
        interpretation = "The companies have equal normalized values."
    elif better_company:
        other_company = previous_company.get("company_name") or "Company A" if better_company == (current_company.get("company_name") or "Company B") else current_company.get("company_name") or "Company B"
        interpretation = f"{better_company} has {'higher' if metric_direction == 'higher_better' else 'lower'} {metric_label.lower()} than {other_company}."
    else:
        interpretation = f"The companies have different {metric_label.lower()} values; the metric direction is neutral."

    # Build company sections with strict identity preservation and evidence retention
    company_a_section = {
        "company_name": company_a.get("company_name") or "Company A",
        "value": normalized_a,
        "currency": currency_a,
        "unit": a_unit,
        "comparison_value": _rounded_float(normalized_a),
    }
    # Preserve evidence and provenance from Company A's observation
    if company_a.get("evidence"):
        company_a_section["evidence"] = company_a.get("evidence")
    if company_a.get("source_file"):
        company_a_section["source_file"] = company_a.get("source_file")
    if company_a.get("source_page") is not None:
        company_a_section["source_page"] = company_a.get("source_page")
    if company_a.get("source_chunk_id"):
        company_a_section["source_chunk_id"] = company_a.get("source_chunk_id")

    company_b_section = {
        "company_name": company_b.get("company_name") or "Company B",
        "value": normalized_b,
        "currency": currency_b,
        "unit": b_unit,
        "comparison_value": _rounded_float(normalized_b),
    }
    # Preserve evidence and provenance from Company B's observation
    if company_b.get("evidence"):
        company_b_section["evidence"] = company_b.get("evidence")
    if company_b.get("source_file"):
        company_b_section["source_file"] = company_b.get("source_file")
    if company_b.get("source_page") is not None:
        company_b_section["source_page"] = company_b.get("source_page")
    if company_b.get("source_chunk_id"):
        company_b_section["source_chunk_id"] = company_b.get("source_chunk_id")

    return {
        "metric": metric_label,
        "company_a": company_a_section,
        "company_b": company_b_section,
        "difference": difference,
        "direction": direction,
        "unit": target_unit,
        "comparison_status": status,
        "absolute_difference": _rounded_float(abs(difference)),
        "percentage_difference": percentage_difference,
        "difference_basis": "company_b_minus_company_a",
        "metric_direction": metric_direction,
        "better_company": better_company,
        "interpretation": interpretation,
        "comparability_metadata": {
            "original_company_a_value": a_raw,
            "original_company_b_value": b_raw,
            "normalized_company_a_value": _rounded_float(normalized_a),
            "normalized_company_b_value": _rounded_float(normalized_b),
            "currency": currency_a or currency_b,
            "unit_scale": target_unit,
            "reporting_period": period_a if period_a is not None else period_b,
            "statement_context": context_a or context_b,
            "metric_name": metric_label,
            "metric_definition": definition_a or definition_b,
            "metric_equivalence": True,
            "normalization_status": "equal" if status == "equal" else "normalized",
        },
    }


def compare_extracted_metrics(extracted_metrics: Dict[str, Any]) -> ComparisonResult:
    """Compare the canonical extracted metrics from the workflow."""
    metadata = {
        "analysis_id": extracted_metrics.get("analysis_id") or extracted_metrics.get("metadata", {}).get("analysis_id"),
        "document_id": extracted_metrics.get("document_id") or extracted_metrics.get("metadata", {}).get("document_id"),
        "company_name": extracted_metrics.get("company_name") or extracted_metrics.get("metadata", {}).get("company_name") or "Unknown Company",
        "report_year": extracted_metrics.get("report_year") or extracted_metrics.get("metadata", {}).get("report_year"),
        "chunk_id": extracted_metrics.get("chunk_id") or extracted_metrics.get("metadata", {}).get("chunk_id"),
    }

    records: List[Dict[str, Any]] = []
    seen_metrics: set[str] = set()
    for metric_name in METRIC_SEQUENCE:
        series = _metric_series_for_name(metric_name, extracted_metrics)
        if not series:
            continue

        normalized_years = [
            _normalize_year_value(item.get("year"))
            for item in series
            if _normalize_year_value(item.get("year")) is not None
        ]
        canonical_year = _normalize_year_value(metadata.get("report_year") or extracted_metrics.get("report_year"))
        if canonical_year is None and normalized_years:
            canonical_year = max(normalized_years)

        direct_value = None
        direct_key = _metric_key_for_lookup(metric_name)
        if direct_key in extracted_metrics:
            direct_value = extracted_metrics.get(direct_key)
        if direct_value is None:
            for alt_key in (metric_name, _canonical_metric_name(metric_name).lower().replace(" ", "_"), _canonical_metric_name(metric_name).lower()):
                if alt_key in extracted_metrics:
                    direct_value = extracted_metrics.get(alt_key)
                    break

        matched_item = next(
            (item for item in series if _normalize_year_value(item.get("year")) == canonical_year),
            None,
        )
        if matched_item is None and direct_value is not None and canonical_year is not None:
            current_item = {"year": canonical_year, "value": direct_value, "source": extracted_metrics.get("source"), "chunk_id": extracted_metrics.get("chunk_id"), "source_chunks": extracted_metrics.get("source_chunks")}
            current_year = canonical_year
            current_value = direct_value
        elif matched_item is None:
            current_item = max(series, key=lambda item: _normalize_year_value(item.get("year")) if _normalize_year_value(item.get("year")) is not None else -1)
            current_year = canonical_year if canonical_year is not None else _normalize_year_value(current_item.get("year"))
            current_value = current_item.get("value")
        else:
            current_item = matched_item
            current_year = canonical_year if canonical_year is not None else _normalize_year_value(current_item.get("year"))
            current_value = current_item.get("value")

        current_numeric, current_unit = _parse_numeric_value(current_value)
        if current_numeric is None:
            current_context = _structured_comparison_value(current_item, metric_name)
            current_numeric = current_context.get("numeric_value")
        if current_numeric is None:
            continue

        previous_year = None
        previous_value = None
        related_sources = []
        metric_evidence_sources: List[str] = []
        sorted_series = sorted(series, key=lambda entry: _normalize_year_value(entry.get("year")) or -1)
        for item in sorted_series:
            item_year = _normalize_year_value(item.get("year"))
            if item_year is not None and item_year < current_year:
                previous_year = item_year
                previous_value = item
            for chunk in _extract_source_chunks(item):
                if chunk and chunk not in metric_evidence_sources:
                    metric_evidence_sources.append(chunk)
            if item.get("chunk_id"):
                chunk_id = str(item.get("chunk_id")).strip()
                if chunk_id and chunk_id not in metric_evidence_sources:
                    metric_evidence_sources.append(chunk_id)

        if not metric_evidence_sources:
            metric_evidence_sources = _filter_valid_source_chunks(
                _extract_source_chunks(extracted_metrics)
                + _extract_source_chunks(current_item)
            )
        else:
            metric_evidence_sources = _filter_valid_source_chunks(metric_evidence_sources)

        if current_year is not None and previous_year is None and canonical_year is not None:
            # Only set a prior period when an actual historical observation exists.
            # A current-only extraction payload should remain single-year/unavailable,
            # not infer a prior year that has no matching value.
            previous_year = None
            previous_value = None
        elif current_year is not None and previous_year is None and sorted_series:
            prev_candidate = max(
                (item for item in sorted_series if _normalize_year_value(item.get("year")) is not None and _normalize_year_value(item.get("year")) < current_year),
                key=lambda item: _normalize_year_value(item.get("year")) if _normalize_year_value(item.get("year")) is not None else -1,
                default=None,
            )
            if prev_candidate is not None:
                previous_year = _normalize_year_value(prev_candidate.get("year"))
                previous_value = prev_candidate

        if current_year is None and previous_year is None:
            continue

        record = _serialize_record(
            metric_name,
            current_year,
            current_item,
            current_unit,
            previous_year=previous_year,
            previous_value=previous_value,
            source=current_item.get("source") or "Extracted Financial Metrics",
            source_chunks=_filter_valid_source_chunks(
                metric_evidence_sources
                + related_sources
            ),
        )
        records.append(record)
        seen_metrics.add(metric_name)

    if not records:
        return ComparisonResult({
            "metadata": metadata,
            "comparison_type": "single_year",
            "records": [],
            "summary": {
                "metrics_compared": 0,
                "increased": 0,
                "decreased": 0,
                "unchanged": 0,
                "unavailable": 0,
            },
        })

    summary = {
        "metrics_compared": len(records),
        "increased": 0,
        "decreased": 0,
        "unchanged": 0,
        "unavailable": 0,
    }
    for row in records:
        direction = row.get("Direction")
        if direction == "increase":
            summary["increased"] += 1
        elif direction == "decrease":
            summary["decreased"] += 1
        elif direction == "unchanged":
            summary["unchanged"] += 1
        else:
            summary["unavailable"] += 1

    payload = {
        "metadata": metadata,
        "comparison_type": "year_over_year" if any(row.get("PreviousYear") is not None for row in records) else "single_year",
        "records": records,
        "summary": summary,
    }
    return ComparisonResult(payload)


def compare_report_metrics(report_metrics: Dict[str, Any], include_missing: bool = False) -> ComparisonResult:
    """Return a JSON-serializable comparison payload backed by real extraction output."""
    result = compare_extracted_metrics(report_metrics)
    if include_missing:
        return result
    return result


def load_company(file):
    """Legacy helper retained only for backward compatibility with older demos/tests."""
    import pandas as pd
    return pd.read_csv(file)


def compare_companies(file1, file2):
    """Legacy CSV-based comparison retained only for backward compatibility.

    The production workflow does not use this path.
    """
    return load_company(file1).merge(load_company(file2), on="Metric", suffixes=("_Company1", "_Company2"))

