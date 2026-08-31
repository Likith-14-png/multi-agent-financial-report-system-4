"""Reproduction harness for the Extraction Agent regression (Capgemini PDF).

Runs the CURRENT extraction agent against the real PDF text and dumps the
result to JSON so we can inspect the invalid observations described in the task.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extraction-agent"))

from extraction_agent import extract_report_metrics  # noqa: E402

PDF = ROOT / "tmp_uploads" / "Capgemini 2025 Synthetic Financial Report.pdf"


def load_pages():
    doc = pymupdf.open(str(PDF))
    pages = []
    for i, page in enumerate(doc):
        pages.append({"page_number": i + 1, "text": page.get_text()})
    return pages


def build_chunk_records(pages):
    """Mimic the document agent: ~800 char chunks carrying page + section metadata."""
    records = []
    cid = 0
    for p in pages:
        text = p["text"]
        # crude section title = first non-empty line
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        section = next((l for l in lines if re.search(r"Page \d+ —|Statement|Balance|Cash Flow|Segment|Summary", l)), lines[0] if lines else "Unknown")
        # chunk into ~800 chars
        start = 0
        while start < len(text):
            piece = text[start:start + 800]
            records.append({
                "chunk_id": f"chunk-{cid}",
                "chunk_index": cid,
                "page_start": p["page_number"],
                "page_end": p["page_number"],
                "section_title": section,
                "text": piece,
                "metadata": {
                    "chunk_id": f"chunk-{cid}",
                    "chunk_index": cid,
                    "page_start": p["page_number"],
                    "section_title": section,
                    "company_name": "Extracted from source",  # the polluted value seen in prod
                    "report_year": "2025",
                    "source": PDF.name,
                },
            })
            cid += 1
            start += 800
    return records


def main():
    pages = load_pages()
    combined_text = "\n\n".join(p["text"] for p in pages)
    chunk_records = build_chunk_records(pages)
    # metadata as stored by the document agent (company_name polluted)
    meta = {
        "company_name": "Extracted from source",
        "report_year": "2025",
        "source": PDF.name,
        "document_id": "capgemini-doc",
        "analysis_id": "capgemini-analysis",
    }
    result = extract_report_metrics(combined_text, metadata=meta, chunk_records=chunk_records)

    out = ROOT / "scratch" / "before_result.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # --- Focused invalid-pattern report ---
    lines = []
    lines.append("=== TOP-LEVEL CANONICAL FIELDS ===")
    for k in ["company_name", "report_year", "revenue", "operating_income", "net_income",
              "eps", "basic_eps", "diluted_eps", "total_assets", "total_liabilities",
              "total_equity", "cash_flow", "operating_cash_flow", "free_cash_flow", "capex"]:
        lines.append(f"  {k} = {result.get(k)!r}")

    lines.append("\n=== yearly_metrics ===")
    for name, series in (result.get("yearly_metrics") or {}).items():
        lines.append(f"  {name}:")
        for item in series:
            lines.append(f"    {item.get('year')} -> {item.get('value')!r}")

    lines.append("\n=== OBSERVATIONS (metric = raw_value  [unit] @ evidence) ===")
    for obs in (result.get("observations") or []):
        ev = str(obs.get("exact_evidence", ""))[:70].replace("\n", " ")
        lines.append(f"  {obs.get('metric_name')} = {obs.get('raw_value')!r} "
                     f"[unit={obs.get('unit')} cur={obs.get('currency')} yr={obs.get('report_year')} "
                     f"score={obs.get('grounding_score')}] ev={ev!r}")

    lines.append("\n=== ANTI-PATTERN SCAN ===")
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for pat in ["€2022 billion", "€2023 billion", "€2024 billion", "€2025 billion",
                "€9.46 billion", "€1,949 billion", "2025 billion", "420,000",
                "€534 billion", "€11,700 billion", "€2 billion", "€16 billion"]:
        n = blob.count(pat)
        if n:
            lines.append(f"  FOUND {n}x: {pat!r}")

    report = "\n".join(lines)
    (ROOT / "scratch" / "before_report.txt").write_text(report, encoding="utf-8")
    print("wrote scratch/before_result.json and scratch/before_report.txt")


if __name__ == "__main__":
    main()
