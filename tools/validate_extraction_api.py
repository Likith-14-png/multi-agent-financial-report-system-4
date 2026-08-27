#!/usr/bin/env python3
"""Validate Extraction API output against metric evidence in a PDF.

Configuration is supplied through environment variables or command-line options:
  BASE_URL       API base URL, for example http://localhost:8000
  API_KEY        API key (never logged)
  API_KEY_HEADER Header name, default Authorization
  API_KEY_PREFIX Prefix before API_KEY, default "Bearer "

The script performs one POST upload and one GET extraction request. It never
modifies the PDF and never calls destructive API endpoints.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from PyPDF2 import PdfReader

DEFAULT_PDF = r"C:\Users\rajan\Downloads\financial_cross_check_test_fixture.pdf"
DEFAULT_TIMEOUT = 30.0
METRIC_PATTERNS = {
    "Revenue": r"revenue|sales|turnover",
    "Gross Profit": r"gross profit",
    "Operating Income": r"operating income|operating profit|income from operations",
    "Pre-tax Income": r"pre[- ]tax income|income before tax|profit before tax",
    "Net Income": r"net income|net profit|profit for the year",
    "Total Assets": r"total assets",
    "Total Liabilities": r"total liabilities",
    "Total Equity": r"total equity|total shareholders'? equity|total stockholders'? equity",
    "Cash and Cash Equivalents": r"cash and cash equivalents",
    "Operating Cash Flow": r"operating cash flow|net cash (?:provided by|from) operating activities",
    "Free Cash Flow": r"free cash flow",
    "Total Debt": r"total debt|total borrowings",
    "EPS": r"earnings per share|\beps\b",
}
VALUE_RE = re.compile(
    r"(?P<value>\(?\s*(?:US\$|[$€£₹]|Rs\.?|INR)?\s*[-+]?\d[\d,.]*"
    r"(?:\s*(?:crores?|cr|lakhs?|lac|billions?|bn|millions?|mn|thousands?|k|m))?\s*%?\s*\)?)",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(?:FY\s*)?(19|20)\d{2}\b", re.IGNORECASE)


def extract_pdf_pages(pdf_path: Path) -> List[str]:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    try:
        reader = PdfReader(str(pdf_path))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise RuntimeError(f"Unable to read PDF: {exc}") from exc


def _normalize_value(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")") or text.startswith("-")
    number_match = re.search(r"\d[\d,.]*(?:\.\d+)?", text)
    if not number_match:
        return None
    number = float(number_match.group(0).replace(",", ""))
    if negative:
        number = -abs(number)
    lowered = text.lower()
    unit = next((unit for unit in ("crore", "lakh", "billion", "million", "thousand", "percent") if unit in lowered), "")
    currency = "INR" if "₹" in text or re.search(r"\b(?:rs\.?|inr)\b", text, re.I) else (
        "USD" if "$" in text or re.search(r"\b(?:us\$|usd)\b", text, re.I) else (
            "EUR" if "€" in text else ("GBP" if "£" in text else None)
        )
    )
    return {"numeric_value": number, "unit": unit, "currency": currency, "raw": text}


def extract_expected_occurrences(pages: Iterable[str]) -> List[Dict[str, Any]]:
    occurrences: List[Dict[str, Any]] = []
    for page_number, page_text in enumerate(pages, 1):
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        section = ""
        for index, line in enumerate(lines):
            if re.search(r"(?i)consolidated.*income|income statement|statement of operations|balance sheet|cash flow statement|notes|risk", line):
                section = line
            for metric, pattern in METRIC_PATTERNS.items():
                if not re.search(rf"(?i)\b(?:{pattern})\b", line):
                    continue
                candidates = list(VALUE_RE.finditer(line))
                if not candidates and index + 1 < len(lines):
                    candidates = list(VALUE_RE.finditer(lines[index + 1]))
                for match in candidates:
                    parsed = _normalize_value(match.group("value"))
                    if parsed and 1900 <= parsed["numeric_value"] <= 2100 and not parsed["unit"] and not parsed["currency"]:
                        continue
                    if parsed:
                        years = [int(match.group(0).replace("FY", "").strip()) for match in YEAR_RE.finditer(line)]
                        occurrences.append({
                            "metric": metric,
                            "value": parsed,
                            "page": page_number,
                            "section": section or "Unknown",
                            "line": line,
                            "report_year": years[-1] if years else None,
                        })
                        break
    return occurrences


def _authority_score(occurrence: Dict[str, Any]) -> int:
    section = str(occurrence.get("section", "")).lower()
    if re.search(r"consolidated.*income|income statement|statement of operations", section):
        return 100
    if re.search(r"consolidated.*balance|balance sheet", section):
        return 100
    if re.search(r"cash flow statement|statement of cash flows", section):
        return 100
    if re.search(r"segment|business", section):
        return 70
    if re.search(r"note|accounting", section):
        return 40
    if re.search(r"risk", section):
        return 20
    return 10


def select_expected_values(occurrences: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    selected: Dict[str, Dict[str, Any]] = {}
    for occurrence in occurrences:
        current = selected.get(occurrence["metric"])
        candidate_key = (_authority_score(occurrence), occurrence.get("report_year") is not None, -occurrence["page"])
        current_key = (_authority_score(current), current.get("report_year") is not None, -current["page"]) if current else None
        if current is None or candidate_key > current_key:
            selected[occurrence["metric"]] = occurrence
    return selected


def _metric_records(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    records = payload.get("metrics")
    if not isinstance(records, list):
        raise ValueError("Extraction response field 'metrics' must be a list")
    result = {}
    for record in records:
        if isinstance(record, dict) and record.get("metric"):
            result[str(record["metric"])] = record
    return result


def compare_results(expected: Dict[str, Dict[str, Any]], payload: Dict[str, Any]) -> Dict[str, Any]:
    actual = _metric_records(payload)
    discrepancies: List[Dict[str, Any]] = []
    checked = []
    for metric, occurrence in expected.items():
        actual_record = actual.get(metric)
        expected_value = occurrence["value"]
        actual_value = _normalize_value((actual_record or {}).get("value"))
        value_match = bool(actual_value and actual_value["numeric_value"] == expected_value["numeric_value"] and actual_value["unit"] == expected_value["unit"])
        checked.append(metric)
        if actual_record is None:
            discrepancies.append({"metric": metric, "type": "missing_metric", "expected": expected_value["raw"]})
            continue
        if not value_match:
            discrepancies.append({"metric": metric, "type": "value_mismatch", "expected": expected_value["raw"], "actual": actual_record.get("value")})
        provenance = actual_record.get("provenance") if isinstance(actual_record.get("provenance"), dict) else {}
        for field in ("source_file", "page", "chunk_id", "section"):
            if provenance.get(field) in (None, ""):
                discrepancies.append({"metric": metric, "type": "missing_provenance", "field": field})
    return {"checked_metrics": checked, "discrepancies": discrepancies, "passed": not discrepancies}


def run_validation(args: argparse.Namespace) -> Dict[str, Any]:
    pdf_path = Path(args.pdf).expanduser()
    pages = extract_pdf_pages(pdf_path)
    occurrences = extract_expected_occurrences(pages)
    expected = select_expected_values(occurrences)
    headers = {args.api_key_header: f"{args.api_key_prefix}{args.api_key}"}
    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    started = datetime.now(timezone.utc).isoformat()
    try:
        with pdf_path.open("rb") as handle:
            response = session.post(
                f"{base_url}/analysis/upload",
                files={"file": (pdf_path.name, handle, "application/pdf")},
                data={"company_name": args.company_name, "report_year": args.report_year, "question": "What financial metrics were extracted?"},
                headers=headers,
                timeout=args.timeout,
            )
        response.raise_for_status()
        upload = response.json()
        analysis_id = upload.get("analysis_id")
        if not analysis_id:
            raise ValueError("Upload response does not contain analysis_id")
        extraction_response = session.get(
            f"{base_url}/analysis/{analysis_id}/extraction",
            headers=headers,
            timeout=args.timeout,
        )
        extraction_response.raise_for_status()
        extraction = extraction_response.json()
        comparison = compare_results(expected, extraction)
        return {
            "started_at": started,
            "pdf": str(pdf_path),
            "page_count": len(pages),
            "analysis_id": analysis_id,
            "expected_occurrences": occurrences,
            "expected_selected": expected,
            "api_status": extraction_response.status_code,
            "comparison": comparison,
        }
    except requests.Timeout as exc:
        raise RuntimeError(f"API request timed out after {args.timeout}s: {exc}") from exc
    except requests.RequestException as exc:
        status = getattr(exc.response, "status_code", None)
        raise RuntimeError(f"API request failed{f' with HTTP {status}' if status else ''}: {exc}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"API schema or JSON validation failed: {exc}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", default=os.getenv("PDF_PATH", DEFAULT_PDF))
    parser.add_argument("--base-url", default=os.getenv("BASE_URL"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY"))
    parser.add_argument("--api-key-header", default=os.getenv("API_KEY_HEADER", "Authorization"))
    parser.add_argument("--api-key-prefix", default=os.getenv("API_KEY_PREFIX", "Bearer "))
    parser.add_argument("--company-name", default=os.getenv("COMPANY_NAME", "Unknown Company"))
    parser.add_argument("--report-year", default=os.getenv("REPORT_YEAR", ""))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("API_TIMEOUT_SECONDS", DEFAULT_TIMEOUT)))
    parser.add_argument("--report", default=os.getenv("VALIDATION_REPORT", "extraction_validation_report.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.base_url or not args.api_key:
        print("BASE_URL and API_KEY must be provided via environment variables or arguments.", file=sys.stderr)
        return 2
    try:
        report = run_validation(args)
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
        print(json.dumps({"passed": report["comparison"]["passed"], "checked_metrics": len(report["comparison"]["checked_metrics"]), "discrepancies": len(report["comparison"]["discrepancies"]), "report": args.report}, indent=2))
        return 0 if report["comparison"]["passed"] else 1
    except (FileNotFoundError, RuntimeError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
