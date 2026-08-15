"""Conservative financial extraction for report text.

This keeps the Extraction Agent lightweight while forcing it to prefer exact
field labels and exact value captures instead of surrounding prose.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _normalize_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip(" \t\n\r.;,)")
    cleaned = cleaned.strip("\"'")
    return cleaned or None


def _coalesce_metadata(metadata: Optional[Dict[str, Any]], *keys: str) -> Optional[str]:
    if not metadata:
        return None
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _first_match(text: str, patterns: Iterable[str], flags: int = 0) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=flags)
        if match:
            return match.group(1).strip() if match.lastindex else match.group(0).strip()
    return None


def _extract_company_name(text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    metadata_value = _coalesce_metadata(metadata, "company_name")
    if metadata_value:
        return metadata_value.strip()

    patterns = [
        r"(?im)^\s*Company\s*[:\-]\s*([A-Z][A-Za-z0-9&.\- ]+?)(?:\s*(?:Ltd\.?|Inc\.?|Corp\.?|Corporation|Holdings|Group|PLC|LLC))?\s*$",
        r"(?im)^\s*([A-Z][A-Za-z0-9&.\- ]+?)\s+Annual Report\s+\d{4}\s*$",
        r"(?im)^\s*([A-Z][A-Za-z0-9&.\- ]+?)\s+(?:Ltd\.?|Inc\.?|Corp\.?|Corporation|Holdings|Group|PLC|LLC)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if value and not re.search(r"\b(?:Annual Report|Management Discussion and Analysis|Risk Factors|Balance Sheet|For the year ended)\b", value, re.I):
                return value

    return None


def _extract_report_year(text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    metadata_value = _coalesce_metadata(metadata, "report_year", "year")
    if metadata_value:
        return str(metadata_value).strip()

    for pattern in [
        r"(?i)\b(?:for the year ended|year ended|FY|Fiscal year)\s+[A-Za-z]+\s+\d{1,2},?\s+(\d{4})\b",
        r"(?i)\b([12]\d{3})\b(?:\s+Annual Report)?",
    ]:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def _extract_field_value(text: str, labels: Iterable[str]) -> Optional[str]:
    if not text:
        return None

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    label_aliases = {
        "operating income": ["operating income", "operating loss"],
        "net income": ["net income", "net loss"],
    }
    money_patterns = [
        r"(?:[+-]?(?:[$€£]\s*)?\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|k|m|bn))",
        r"(?:[+-]?\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|k|m|bn))",
    ]
    percent_pattern = r"(?<![\d.])[-+]?\d[\d,]*(?:\.\d+)?\s*%"

    for label in labels:
        aliases = label_aliases.get(label, [label])
        for sentence in sentences:
            for alias in aliases:
                alias_match = re.search(rf"\b{re.escape(alias)}\b", sentence, flags=re.I)
                if not alias_match:
                    continue

                tail = sentence[alias_match.end():]
                money_candidates: list[str] = []
                for money_pattern in money_patterns:
                    for match in re.finditer(money_pattern, tail, flags=re.I):
                        candidate = _normalize_value(match.group(0))
                        if not candidate:
                            continue
                        prev_char = tail[match.start() - 1] if match.start() > 0 else ""
                        if prev_char in {".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
                            continue
                        if match.start() > 0 and tail[match.start() - 1] in {"$", "€", "£"}:
                            candidate = tail[match.start() - 1] + candidate
                        money_candidates.append(candidate)

                if money_candidates:
                    return money_candidates[0]

                percent_candidates: list[str] = []
                for match in re.finditer(percent_pattern, tail, flags=re.I):
                    candidate = _normalize_value(match.group(0))
                    if candidate:
                        percent_candidates.append(candidate)

                if percent_candidates:
                    return percent_candidates[0]
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
        "operating cash flow": "Cash Flow",
        "eps": "EPS",
        "earnings per share": "EPS",
    }
    return aliases.get(normalized, metric_name.strip())


def _extract_table_yearly_metrics(text: str) -> Dict[str, List[Dict[str, Any]]]:
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
    metric_names = [
        "Revenue",
        "Operating Income",
        "Net Income",
        "Total Assets",
        "Total Liabilities",
        "Operating Cash Flow",
        "EPS",
    ]
    metric_match_re = re.compile(
        r"^(Revenue|Operating Income|Net Income|Total Assets|Total Liabilities|Operating Cash Flow|Cash Flow|EPS)\s*$",
        re.I,
    )

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
            if re.search(r"(?i)^\+?\$?[-+]?\d[\d,]*\.?\d*\s*(?:billion|million|thousand|k|bn|m)$", candidate):
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

    if not yearly:
        for metric in metric_names:
            if metric.lower() == "operating cash flow":
                canonical = "Cash Flow"
            else:
                canonical = _canonical_yearly_metric_name(metric)
            if canonical in yearly:
                continue
    return yearly


def _extract_yearly_metric_values(text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
    table_values = _extract_table_yearly_metrics(text)
    if table_values:
        return table_values

    if not text:
        return {}

    metrics = {
        "Revenue": ["revenue"],
        "Operating Income": ["operating income", "operating loss"],
        "Net Income": ["net income", "net loss"],
        "Total Assets": ["total assets", "assets"],
        "Total Liabilities": ["total liabilities", "liabilities"],
        "Cash Flow": ["cash flow", "cash flow from operations", "operating cash flow"],
        "EPS": ["earnings per share", "eps"],
    }

    metadata_year = metadata.get("report_year") if isinstance(metadata, dict) else None
    current_year = None
    if metadata_year is not None:
        try:
            current_year = int(str(metadata_year).strip())
        except (TypeError, ValueError):
            current_year = None
    if current_year is None:
        raw_years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", text)]
        if not raw_years:
            return {}
        current_year = max(raw_years)

    yearly: Dict[str, List[Dict[str, Any]]] = {}
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    money_patterns = [
        r"(?:[+-]?(?:[$€£]\s*)?\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|k|m|bn))",
        r"(?:[+-]?\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|k|m|bn))",
    ]

    def _money_candidates(snippet: str) -> list[Dict[str, Any]]:
        candidates: list[Dict[str, Any]] = []
        for pattern in money_patterns:
            for match in re.finditer(pattern, snippet, flags=re.I):
                candidate = _normalize_value(match.group(0))
                if not candidate:
                    continue
                if re.fullmatch(r"(?:19|20)\d{2}", candidate.replace("$", "").replace("€", "").replace("£", "").strip()):
                    continue
                prev_char = snippet[match.start() - 1] if match.start() > 0 else ""
                if prev_char in {".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
                    continue
                if match.start() > 0 and snippet[match.start() - 1] in {"$", "€", "£"}:
                    candidate = snippet[match.start() - 1] + candidate
                candidates.append({"value": candidate, "start": match.start()})
        return sorted(candidates, key=lambda item: item["start"])

    def _pair_years_to_values(values: list[Dict[str, Any]], year_positions: list[tuple[int, int]]) -> list[Dict[str, Any]]:
        assigned: list[Dict[str, Any]] = []
        used_indexes: set[int] = set()
        for year_index, year in year_positions:
            best_index = None
            best_start = None
            for idx, candidate in enumerate(values):
                if idx in used_indexes:
                    continue
                if candidate["start"] < year_index and (best_start is None or candidate["start"] > best_start):
                    best_index = idx
                    best_start = candidate["start"]
            if best_index is not None:
                assigned.append({"year": year, "value": values[best_index]["value"]})
                used_indexes.add(best_index)
        return sorted(assigned, key=lambda item: int(item["year"]))

    for metric_name, aliases in metrics.items():
        for sentence in sentences:
            for alias in aliases:
                alias_match = re.search(rf"\b{re.escape(alias)}\b", sentence, flags=re.I)
                if not alias_match:
                    continue

                snippet = sentence[alias_match.start():]
                money_values = _money_candidates(snippet)
                if not money_values:
                    continue

                year_positions = []
                for year_match in re.finditer(r"\b(?:19|20)\d{2}\b", snippet):
                    year_positions.append((year_match.start(), int(year_match.group(0))))

                if len(year_positions) >= 2 and len(money_values) >= 2:
                    paired = _pair_years_to_values(money_values, year_positions)
                    if len(paired) >= 2:
                        yearly[metric_name] = paired
                        break
                yearly[metric_name] = [{"year": current_year, "value": money_values[0]["value"]}]
                break
            if metric_name in yearly:
                break

    return yearly


def _extract_report_metrics(text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    text = text or ""
    metadata = metadata or {}
    yearly_metrics = _extract_yearly_metric_values(text, metadata)
    result: Dict[str, Any] = {
        "company_name": _extract_company_name(text, metadata),
        "report_year": _extract_report_year(text, metadata),
        "revenue": _extract_field_value(text, ["revenue"]),
        "operating_income": _extract_field_value(text, ["operating income"]),
        "net_income": _extract_field_value(text, ["net income"]),
        "total_assets": _extract_field_value(text, ["total assets"]),
        "total_liabilities": _extract_field_value(text, ["total liabilities"]),
        "cash_flow": _extract_field_value(text, ["cash flow from operations", "cash flow"]),
        "eps": _extract_field_value(text, ["earnings per share", "eps"]),
        "yearly_metrics": yearly_metrics,
    }

    target_year = None
    try:
        target_year = int(str(metadata.get("report_year") or _extract_report_year(text, metadata) or "").strip())
    except (TypeError, ValueError):
        target_year = None
    if target_year is None:
        candidate_years = [int(item.get("year")) for items in yearly_metrics.values() for item in items if isinstance(item, dict) and item.get("year") is not None]
        if candidate_years:
            target_year = max(candidate_years)

    for key, metric_name in {
        "revenue": "Revenue",
        "operating_income": "Operating Income",
        "net_income": "Net Income",
        "total_assets": "Total Assets",
        "total_liabilities": "Total Liabilities",
        "cash_flow": "Cash Flow",
        "eps": "EPS",
    }.items():
        series = yearly_metrics.get(metric_name)
        if series:
            current_value = None
            for item in series:
                if isinstance(item, dict) and _normalize_year_value(item.get("year")) == target_year:
                    current_value = item.get("value")
                    break
            if current_value is None:
                current_value = series[-1].get("value") if isinstance(series[-1], dict) else None
            if current_value is not None:
                result[key] = str(current_value)

    if metadata:
        for key in ("analysis_id", "document_id", "chunk_id"):
            if key in metadata and metadata.get(key) not in (None, ""):
                result[key] = str(metadata[key])

    for key in ("revenue", "operating_income", "net_income", "total_assets", "total_liabilities", "cash_flow", "eps"):
        if result.get(key) in ("", "Not Found", "not found"):
            result[key] = None

    return result


def extract_report_metrics(text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _extract_report_metrics(text, metadata)


if __name__ == "__main__":
    report_path = Path(__file__).with_name("sample_report.txt")
    report_text = report_path.read_text(encoding="utf-8")
    metadata = {
        "analysis_id": "demo-analysis-id",
        "document_id": "demo-document-id",
        "company_name": "ABB",
        "report_year": "2025",
        "chunk_id": "demo-chunk-id",
    }
    result = extract_report_metrics(report_text, metadata=metadata)
    print("==============================")
    print("EXTRACTION OUTPUT")
    print("==============================")
    print(json.dumps({
        "company_name": result.get("company_name"),
        "report_year": result.get("report_year"),
        "revenue": result.get("revenue"),
        "operating_income": result.get("operating_income"),
        "net_income": result.get("net_income"),
        "total_assets": result.get("total_assets"),
        "total_liabilities": result.get("total_liabilities"),
        "cash_flow": result.get("cash_flow"),
        "eps": result.get("eps"),
    }, indent=2, ensure_ascii=False))
    print()
    print("==============================")
    print("METADATA")
    print("==============================")
    print(json.dumps({
        "analysis_id": result.get("analysis_id"),
        "document_id": result.get("document_id"),
        "company_name": result.get("company_name"),
        "report_year": result.get("report_year"),
        "chunk_id": result.get("chunk_id"),
    }, indent=2, ensure_ascii=False))