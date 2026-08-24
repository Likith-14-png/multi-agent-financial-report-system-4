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
        source_chunks = entry.get("source_chunks")
        if isinstance(source_chunks, list):
            for chunk in source_chunks:
                cleaned = _clean_source_chunk_value(chunk)
                if cleaned and cleaned not in chunks:
                    chunks.append(cleaned)
        elif isinstance(source_chunks, tuple):
            for chunk in source_chunks:
                cleaned = _clean_source_chunk_value(chunk)
                if cleaned and cleaned not in chunks:
                    chunks.append(cleaned)
        elif isinstance(source_chunks, str) and source_chunks.strip():
            cleaned = _clean_source_chunk_value(source_chunks)
            if cleaned:
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

    direct_value = registry.get("direct") or registry.get("alt")
    direct_year = _normalize_year_value(extracted_metrics.get("report_year"))
    if "yearly" in registry and direct_value is not None and direct_year is not None:
        series = registry["yearly"]
        if isinstance(series, list):
            normalized = []
            for item in series:
                if isinstance(item, dict):
                    year = item.get("year") or item.get("period") or item.get("report_year")
                    value = item.get("value") or item.get("amount")
                    if year is not None and value is not None:
                        normalized.append({
                            "year": year,
                            "value": value,
                            "source": item.get("source"),
                            "chunk_id": item.get("chunk_id"),
                            "source_chunks": item.get("source_chunks"),
                        })
            if not any(_normalize_year_value(item.get("year")) == direct_year for item in normalized):
                normalized.insert(0, {
                    "year": direct_year,
                    "value": direct_value,
                    "source": extracted_metrics.get("source"),
                    "chunk_id": extracted_metrics.get("chunk_id"),
                    "source_chunks": extracted_metrics.get("source_chunks"),
                })
            return normalized

    if "yearly" in registry:
        series = registry["yearly"]
        if isinstance(series, list):
            normalized = []
            for item in series:
                if isinstance(item, dict):
                    year = item.get("year") or item.get("period") or item.get("report_year")
                    value = item.get("value") or item.get("amount")
                    if year is not None and value is not None:
                        normalized.append({
                            "year": year,
                            "value": value,
                            "source": item.get("source"),
                            "chunk_id": item.get("chunk_id"),
                            "source_chunks": item.get("source_chunks"),
                        })
            return normalized
        return []

    if "list" in registry:
        items = registry["list"]
        normalized = []
        for item in items:
            year = item.get("year") or item.get("period") or item.get("report_year")
            value = item.get("value") or item.get("amount")
            if value is not None:
                normalized.append({
                    "year": year,
                    "value": value,
                    "source": item.get("source"),
                    "chunk_id": item.get("chunk_id"),
                    "source_chunks": item.get("source_chunks"),
                })
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
                    normalized.append({
                        "year": year,
                        "value": value,
                        "source": item.get("source"),
                        "chunk_id": item.get("chunk_id"),
                        "source_chunks": item.get("source_chunks"),
                    })
        return normalized
    year = extracted_metrics.get("report_year")
    return [{
        "year": year,
        "value": direct_value,
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
    value = ((current_value - previous_value) / abs(previous_value)) * 100.0
    return round(value, 2)


def _rounded_float(value: Optional[float], digits: int = 10) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _serialize_record(metric_name: str, current_year: Any, current_value: Any, unit: Any, previous_year: Any = None, previous_value: Any = None, source: Any = None, source_chunks: Optional[List[str]] = None) -> Dict[str, Any]:
    current_numeric, current_unit = _parse_numeric_value(current_value)
    previous_numeric, previous_unit = _parse_numeric_value(previous_value)
    chosen_unit = unit or current_unit or "unitless"

    if previous_numeric is not None and current_numeric is not None and chosen_unit not in (None, "unitless") and previous_unit is not None and previous_unit != chosen_unit:
        previous_numeric = _convert_to_unit(previous_numeric, previous_unit, chosen_unit)
        current_numeric = _convert_to_unit(current_numeric, current_unit or chosen_unit, chosen_unit)

    record: Dict[str, Any] = {
        "metric": metric_name,
        "Metric": metric_name,
        "value": current_numeric if current_numeric is not None else current_value,
        "Value": current_numeric if current_numeric is not None else current_value,
        "unit": chosen_unit,
        "Unit": chosen_unit,
        "current_year": current_year,
        "CurrentYear": current_year,
        "current_value": current_numeric,
        "CurrentValue": current_numeric,
        "source": source or "Extracted Financial Metrics",
        "Source": source or "Extracted Financial Metrics",
        "source_chunks": source_chunks or [],
        "SourceChunks": source_chunks or [],
    }

    if previous_year is not None:
        record["previous_year"] = previous_year
        record["PreviousYear"] = previous_year
        record["previous_value"] = previous_numeric
        record["PreviousValue"] = previous_numeric
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


def compare_company_metrics(company_a: Dict[str, Any], company_b: Dict[str, Any], metric_name: Optional[str] = None) -> Dict[str, Any]:
    metric_label = metric_name or company_a.get("metric") or company_b.get("metric") or "Revenue"
    m_key = metric_label.lower().replace(" ", "_")
    a_raw = company_a.get("value") or company_a.get("current_value") or company_a.get("amount") or company_a.get(m_key) or company_a.get(metric_label)
    b_raw = company_b.get("value") or company_b.get("current_value") or company_b.get("amount") or company_b.get(m_key) or company_b.get(metric_label)
    a_value, a_unit = _parse_numeric_value(a_raw)
    b_value, b_unit = _parse_numeric_value(b_raw)
    if a_value is None or b_value is None:
        return {
            "metric": metric_label,
            "company_a": {"company_name": company_a.get("company_name") or "Company A", "value": company_a.get("value") or company_a.get("current_value"), "unit": a_unit},
            "company_b": {"company_name": company_b.get("company_name") or "Company B", "value": company_b.get("value") or company_b.get("current_value"), "unit": b_unit},
            "difference": None,
            "direction": "unavailable",
            "unit": None,
        }

    target_unit = a_unit if a_unit == b_unit else "billion" if a_unit in {"thousand", "million", "billion"} and b_unit in {"thousand", "million", "billion"} else None
    if target_unit is None:
        return {
            "metric": metric_label,
            "company_a": {"company_name": company_a.get("company_name") or "Company A", "value": a_value, "unit": a_unit},
            "company_b": {"company_name": company_b.get("company_name") or "Company B", "value": b_value, "unit": b_unit},
            "difference": None,
            "direction": "unavailable",
            "unit": None,
        }

    normalized_a = _convert_to_unit(a_value, a_unit, target_unit)
    normalized_b = _convert_to_unit(b_value, b_unit, target_unit)
    difference = _rounded_float(normalized_b - normalized_a)
    direction = "increase" if difference > 0 else "decrease" if difference < 0 else "unchanged"
    return {
        "metric": metric_label,
        "company_a": {"company_name": company_a.get("company_name") or "Company A", "value": _rounded_float(normalized_a), "unit": target_unit},
        "company_b": {"company_name": company_b.get("company_name") or "Company B", "value": _rounded_float(normalized_b), "unit": target_unit},
        "difference": difference,
        "direction": direction,
        "unit": target_unit,
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
                previous_value = item.get("value")
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
            previous_year = canonical_year - 1 if isinstance(canonical_year, int) else None
            if previous_year is not None:
                previous_value = None
        elif current_year is not None and previous_year is None and sorted_series:
            prev_candidate = max(
                (item for item in sorted_series if _normalize_year_value(item.get("year")) is not None and _normalize_year_value(item.get("year")) < current_year),
                key=lambda item: _normalize_year_value(item.get("year")) if _normalize_year_value(item.get("year")) is not None else -1,
                default=None,
            )
            if prev_candidate is not None:
                previous_year = _normalize_year_value(prev_candidate.get("year"))
                previous_value = prev_candidate.get("value")

        if current_year is None and previous_year is None:
            continue

        record = _serialize_record(
            metric_name,
            current_year,
            current_value,
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

