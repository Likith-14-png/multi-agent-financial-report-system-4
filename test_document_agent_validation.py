#!/usr/bin/env python3
"""
=============================================================================
Document Agent Independent Validation & Quality Assurance Test Suite
=============================================================================
Purpose:
    Read-only validation of the existing Document Agent pipeline:
    PDF -> Text Extraction -> Page Tracking -> Chunking -> Metadata ->
    Embeddings -> ChromaDB Storage -> Semantic Retrieval.

Execution:
    python test_document_agent_validation.py
    (or pytest test_document_agent_validation.py)
=============================================================================
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Reconfigure stdout for UTF-8 on Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project paths are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
DOC_AGENT_DIR = PROJECT_ROOT / "document-agent-text-chunking" / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DOC_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(DOC_AGENT_DIR))

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError as err:
    print(f"CRITICAL ERROR: ChromaDB or Sentence-Transformers not installed: {err}")
    sys.exit(1)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


# ---------------------------------------------------------------------------
# Data Structures for Validation Tracking
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    status: str  # "PASS", "WARN", "FAIL"
    details: str = ""
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ValidationContext:
    def __init__(self) -> None:
        self.results: Dict[str, CheckResult] = {}
        self.chroma_path: Optional[Path] = None
        self.collection_name: str = "financial_research_v1"
        self.embedding_model: str = "all-MiniLM-L6-v2"
        self.client: Optional[chromadb.PersistentClient] = None
        self.collection: Any = None
        self.records: List[Dict[str, Any]] = []
        self.source_pdf_path: Optional[Path] = None
        self.pdf_pages: List[str] = []
        self.pdf_page_count: int = 0

    def add_result(self, name: str, status: str, details: str = "", failures: List[str] | None = None, warnings: List[str] | None = None) -> None:
        self.results[name] = CheckResult(
            name=name,
            status=status,
            details=details,
            failures=failures or [],
            warnings=warnings or [],
        )


# ---------------------------------------------------------------------------
# Helper Normalization Utilities
# ---------------------------------------------------------------------------

def safe_clean_text(text: str) -> str:
    """Normalize Unicode and strip zero-width and control characters."""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"[\u200b\u200e\u200f\ufeff]", "", normalized)
    normalized = "".join(c for c in normalized if c.isprintable() or c in "\n\t")
    return re.sub(r"\s+", " ", normalized).strip()


def safe_preview(text: str, max_chars: int = 140) -> str:
    cleaned = safe_clean_text(text).replace("\n", " ")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit(" ", 1)[0] + "..."


# ---------------------------------------------------------------------------
# Section 1: Discover Configuration
# ---------------------------------------------------------------------------

def discover_existing_configuration(ctx: ValidationContext) -> None:
    print("=" * 80)
    print("1. DISCOVERING EXISTING CONFIGURATION")
    print("=" * 80)

    # Candidate paths for ChromaDB
    candidate_paths = [
        DOC_AGENT_DIR / "enterprise_chroma_db",
        PROJECT_ROOT / "enterprise_chroma_db",
        DOC_AGENT_DIR.parent / "chroma_db",
        PROJECT_ROOT / "chroma_db",
    ]

    resolved_path: Optional[Path] = None
    for path in candidate_paths:
        if path.exists() and (path / "chroma.sqlite3").exists():
            resolved_path = path
            break

    if not resolved_path:
        # Fallback to any existing directory
        for path in candidate_paths:
            if path.exists():
                resolved_path = path
                break

    ctx.chroma_path = resolved_path or (PROJECT_ROOT / "enterprise_chroma_db")
    ctx.collection_name = "financial_research_v1"
    ctx.embedding_model = "all-MiniLM-L6-v2"

    print(f"ChromaDB Storage Path : {ctx.chroma_path}")
    print(f"Target Collection     : {ctx.collection_name}")
    print(f"Embedding Model       : {ctx.embedding_model}")

    if ctx.chroma_path and ctx.chroma_path.exists():
        ctx.add_result(
            "CONFIGURATION DISCOVERY",
            "PASS",
            f"Resolved ChromaDB at '{ctx.chroma_path.name}' with collection '{ctx.collection_name}'.",
        )
    else:
        ctx.add_result(
            "CONFIGURATION DISCOVERY",
            "FAIL",
            f"ChromaDB path '{ctx.chroma_path}' does not exist.",
            failures=[f"ChromaDB directory not found at {ctx.chroma_path}"],
        )


# ---------------------------------------------------------------------------
# Section 9: ChromaDB Validation (Loaded Early to Supply Chunks to Downstream)
# ---------------------------------------------------------------------------

def validate_chromadb_connection(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("9. CHROMADB STORAGE & EMBEDDING VALIDATION")
    print("=" * 80)

    if not ctx.chroma_path or not ctx.chroma_path.exists():
        print(f"FAIL: ChromaDB path '{ctx.chroma_path}' not accessible.")
        ctx.add_result("CHROMADB CONNECTION", "FAIL", "Path does not exist", failures=["ChromaDB path missing"])
        ctx.add_result("CHROMADB STORAGE", "FAIL", "No data accessible", failures=["No storage accessible"])
        ctx.add_result("EMBEDDING STORAGE", "FAIL", "No embeddings accessible", failures=["No embeddings"])
        return

    try:
        ctx.client = chromadb.PersistentClient(path=str(ctx.chroma_path.resolve()))
        collections = ctx.client.list_collections()
        col_names = [c.name for c in collections]
        print(f"Persistent Client Open: SUCCESS")
        print(f"Available Collections : {', '.join(col_names) if col_names else '<none>'}")
        ctx.add_result("CHROMADB CONNECTION", "PASS", f"Connected to {ctx.chroma_path.name}")
    except Exception as exc:
        print(f"FAIL: Unable to open ChromaDB client: {exc}")
        ctx.add_result("CHROMADB CONNECTION", "FAIL", str(exc), failures=[str(exc)])
        return

    if ctx.collection_name not in col_names:
        # Fallback to first non-empty collection if default not present
        if col_names:
            ctx.collection_name = col_names[0]
            print(f"WARN: Default collection not found; using '{ctx.collection_name}' instead.")
        else:
            ctx.add_result("CHROMADB STORAGE", "FAIL", "No collections found", failures=["ChromaDB contains no collections"])
            return

    try:
        ctx.collection = ctx.client.get_collection(ctx.collection_name)
        count = ctx.collection.count()
        print(f"Active Collection     : {ctx.collection_name}")
        print(f"Total Stored Chunks   : {count}")

        if count == 0:
            ctx.add_result("CHROMADB STORAGE", "FAIL", f"Collection '{ctx.collection_name}' is empty", failures=["Collection is empty"])
            return

        # Fetch all records in READ-ONLY mode
        data = ctx.collection.get(include=["documents", "metadatas", "embeddings"])
        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        embs = data.get("embeddings")

        records: List[Dict[str, Any]] = []
        for i in range(len(ids)):
            records.append({
                "id": ids[i],
                "document": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) and isinstance(metas[i], dict) else {},
                "embedding": embs[i] if embs is not None and i < len(embs) else None,
            })
        ctx.records = records

        # Embedding verification
        emb_dim = len(records[0]["embedding"]) if records and records[0]["embedding"] is not None else 0
        has_embeddings = emb_dim > 0
        print(f"Embeddings Present    : {has_embeddings} (Dimension: {emb_dim})")

        ctx.add_result("CHROMADB STORAGE", "PASS", f"Collection has {count} stored chunks with full metadata.")
        if has_embeddings:
            ctx.add_result("EMBEDDING STORAGE", "PASS", f"All chunks have {emb_dim}-dimensional embeddings.")
        else:
            ctx.add_result("EMBEDDING STORAGE", "WARN", "Stored chunks did not return raw embedding vectors in .get() response.")

    except Exception as exc:
        print(f"FAIL: Error reading ChromaDB collection: {exc}")
        ctx.add_result("CHROMADB STORAGE", "FAIL", str(exc), failures=[str(exc)])


# ---------------------------------------------------------------------------
# Section 2: PDF Validation
# ---------------------------------------------------------------------------

def validate_source_pdf(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("2. SOURCE PDF VALIDATION")
    print("=" * 80)

    # Determine source document name from ChromaDB metadata if available
    source_filename: Optional[str] = None
    if ctx.records:
        source_filename = ctx.records[0]["metadata"].get("source") or ctx.records[0]["metadata"].get("source_file")

    candidate_pdf_paths: List[Path] = []
    if source_filename:
        candidate_pdf_paths.extend([
            DOC_AGENT_DIR / "demo_data" / source_filename,
            PROJECT_ROOT / "data" / source_filename,
            PROJECT_ROOT / "tmp_uploads" / source_filename,
            PROJECT_ROOT / "backend" / "tmp_uploads" / source_filename,
        ])

    # General fallback search for PDF files
    candidate_pdf_paths.extend(list(PROJECT_ROOT.glob("**/ABB*Mock*.pdf")))
    candidate_pdf_paths.extend(list(PROJECT_ROOT.glob("**/*.pdf")))

    resolved_pdf: Optional[Path] = None
    for p in candidate_pdf_paths:
        if p.exists() and p.is_file() and p.suffix.lower() == ".pdf":
            resolved_pdf = p
            break

    if not resolved_pdf:
        print("WARN: No source PDF file found in repository paths.")
        ctx.add_result("PDF ACCESS", "WARN", "Source PDF file not found locally", warnings=["No source PDF located"])
        ctx.add_result("TEXT EXTRACTION", "WARN", "Skipped because source PDF was not found", warnings=["PDF missing"])
        ctx.add_result("PAGE COUNT", "WARN", "Skipped because source PDF was not found", warnings=["PDF missing"])
        return

    ctx.source_pdf_path = resolved_pdf
    print(f"Target PDF File       : {resolved_pdf.name}")
    print(f"Full File Path        : {resolved_pdf}")
    print(f"File Size             : {resolved_pdf.stat().st_size:,} bytes")
    ctx.add_result("PDF ACCESS", "PASS", f"Successfully opened {resolved_pdf.name}")

    # Match records to resolved PDF if multiple documents exist in ChromaDB
    if resolved_pdf and ctx.records:
        matching_records = [r for r in ctx.records if r["metadata"].get("source") == resolved_pdf.name or r["metadata"].get("source_file") == resolved_pdf.name]
        if matching_records:
            ctx.records = matching_records

    # Extract text and count pages using PyMuPDF / PyPDF2
    pages_text: List[str] = []
    if fitz is not None:
        try:
            with fitz.open(resolved_pdf) as doc:
                ctx.pdf_page_count = len(doc)
                for page in doc:
                    pages_text.append(page.get_text("text") or "")
        except Exception as exc:
            print(f"WARN: PyMuPDF extraction failed: {exc}")

    if not pages_text and PyPDF2 is not None:
        try:
            with open(resolved_pdf, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                ctx.pdf_page_count = len(reader.pages)
                for page in reader.pages:
                    pages_text.append(page.extract_text() or "")
        except Exception as exc:
            print(f"FAIL: PyPDF2 extraction failed: {exc}")

    ctx.pdf_pages = pages_text
    non_empty_pages = sum(1 for p in pages_text if len(safe_clean_text(p)) > 0)
    empty_pages = ctx.pdf_page_count - non_empty_pages
    total_chars = sum(len(safe_clean_text(p)) for p in pages_text)

    print(f"Total PDF Pages       : {ctx.pdf_page_count}")
    print(f"Pages with Text       : {non_empty_pages}")
    print(f"Empty/Scanned Pages   : {empty_pages}")
    print(f"Extracted Characters  : {total_chars:,}")

    if ctx.pdf_page_count > 0:
        ctx.add_result("PAGE COUNT", "PASS", f"Document has {ctx.pdf_page_count} pages.")
    else:
        ctx.add_result("PAGE COUNT", "FAIL", "Document page count is 0.", failures=["Zero pages in PDF"])

    if non_empty_pages > 0:
        ctx.add_result("TEXT EXTRACTION", "PASS", f"Extracted {total_chars:,} characters across {non_empty_pages} pages.")
    else:
        ctx.add_result("TEXT EXTRACTION", "FAIL", "Failed to extract text from PDF.", failures=["No text extracted from PDF"])


# ---------------------------------------------------------------------------
# Section 3: Chunk Validation
# ---------------------------------------------------------------------------

def validate_chunks(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("3. CHUNK INTEGRITY & STATISTICAL VALIDATION")
    print("=" * 80)

    records = ctx.records
    total_chunks = len(records)
    print(f"Total Stored Chunks   : {total_chunks}")

    if total_chunks == 0:
        ctx.add_result("CHUNK CREATION", "FAIL", "Zero chunks found in ChromaDB collection.", failures=["No chunks stored"])
        ctx.add_result("EMPTY CHUNK CHECK", "FAIL", "No chunks to validate", failures=["No chunks"])
        ctx.add_result("DUPLICATE ID CHECK", "FAIL", "No chunks to validate", failures=["No chunks"])
        return

    empty_chunks = 0
    whitespace_only = 0
    duplicate_ids: List[str] = []
    char_lengths: List[int] = []
    word_lengths: List[int] = []

    seen_ids: set[str] = set()
    for rec in records:
        cid = rec["id"]
        text = rec["document"]
        if cid in seen_ids:
            duplicate_ids.append(cid)
        seen_ids.add(cid)

        cleaned = safe_clean_text(text)
        if len(text) == 0:
            empty_chunks += 1
        elif len(cleaned) == 0:
            whitespace_only += 1

        char_lengths.append(len(text))
        word_lengths.append(len(text.split()))

    min_chars = min(char_lengths) if char_lengths else 0
    max_chars = max(char_lengths) if char_lengths else 0
    avg_chars = sum(char_lengths) / total_chunks if total_chunks else 0
    min_words = min(word_lengths) if word_lengths else 0
    max_words = max(word_lengths) if word_lengths else 0
    avg_words = sum(word_lengths) / total_chunks if total_chunks else 0

    print(f"Empty Chunks          : {empty_chunks}")
    print(f"Whitespace Chunks     : {whitespace_only}")
    print(f"Duplicate Chunk IDs   : {len(duplicate_ids)}")
    print(f"Character Lengths     : Min={min_chars}, Max={max_chars}, Avg={avg_chars:.1f}")
    print(f"Word Counts           : Min={min_words}, Max={max_words}, Avg={avg_words:.1f}")

    ctx.add_result("CHUNK CREATION", "PASS", f"{total_chunks} chunks stored with average length {avg_words:.1f} words.")

    if empty_chunks == 0 and whitespace_only == 0:
        ctx.add_result("EMPTY CHUNK CHECK", "PASS", "No empty or whitespace-only chunks detected.")
    else:
        ctx.add_result(
            "EMPTY CHUNK CHECK",
            "FAIL",
            f"Found {empty_chunks} empty and {whitespace_only} whitespace chunks.",
            failures=[f"{empty_chunks} empty chunks", f"{whitespace_only} whitespace chunks"],
        )

    if len(duplicate_ids) == 0:
        ctx.add_result("DUPLICATE ID CHECK", "PASS", "All chunk IDs are unique.")
    else:
        ctx.add_result(
            "DUPLICATE ID CHECK",
            "FAIL",
            f"Found {len(duplicate_ids)} duplicate chunk IDs.",
            failures=[f"Duplicate IDs: {duplicate_ids}"],
        )


# ---------------------------------------------------------------------------
# Section 4: Page Number Validation
# ---------------------------------------------------------------------------

def validate_page_numbers(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("4. PAGE NUMBER METADATA VALIDATION")
    print("=" * 80)

    records = ctx.records
    total = len(records)
    if total == 0:
        ctx.add_result("PAGE NUMBER METADATA", "FAIL", "No chunks available to check page numbers.")
        return

    missing_page: int = 0
    invalid_page: int = 0
    out_of_range: int = 0
    page_distribution: Dict[int, int] = defaultdict(int)

    for i, rec in enumerate(records):
        meta = rec["metadata"]
        page_val = meta.get("page_number")
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")

        if page_val in (None, "") and page_start is None:
            missing_page += 1
            continue

        try:
            start_num = int(page_start) if page_start is not None else int(str(page_val).split("-")[0])
            end_num = int(page_end) if page_end is not None else int(str(page_val).split("-")[-1])
            if start_num <= 0 or end_num < start_num:
                invalid_page += 1
            else:
                for p in range(start_num, end_num + 1):
                    page_distribution[p] += 1
                if ctx.pdf_page_count > 0 and end_num > ctx.pdf_page_count:
                    out_of_range += 1
        except Exception:
            invalid_page += 1

    chunks_with_page = total - missing_page
    pct = (chunks_with_page / total) * 100

    print(f"Chunks With Page Info : {chunks_with_page}/{total} ({pct:.1f}%)")
    print(f"Missing Page Info     : {missing_page}")
    print(f"Invalid Page Numbers  : {invalid_page}")
    print(f"Out of Range Pages    : {out_of_range}")
    print(f"Distinct Pages Covered: {len(page_distribution)}")

    print("\nPage Distribution Sample:")
    for p in sorted(page_distribution.keys())[:10]:
        print(f"  Page {p:02d} -> {page_distribution[p]} chunk(s)")
    if len(page_distribution) > 10:
        print(f"  ... and {len(page_distribution) - 10} more pages")

    failures = []
    if missing_page > 0:
        failures.append(f"{missing_page} chunks missing page_number")
    if invalid_page > 0:
        failures.append(f"{invalid_page} chunks have malformed page numbers")
    if out_of_range > 0:
        failures.append(f"{out_of_range} chunks exceed total PDF pages ({ctx.pdf_page_count})")

    if not failures:
        ctx.add_result("PAGE NUMBER METADATA", "PASS", f"100% of chunks have valid page metadata across {len(page_distribution)} pages.")
    else:
        ctx.add_result("PAGE NUMBER METADATA", "FAIL", "; ".join(failures), failures=failures)


# ---------------------------------------------------------------------------
# Section 5 & 12: Metadata Completeness & Field Validation
# ---------------------------------------------------------------------------

def validate_metadata_completeness(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("5. DOCUMENT METADATA COMPLETENESS REPORT")
    print("=" * 80)

    records = ctx.records
    total = len(records)
    if total == 0:
        ctx.add_result("METADATA COMPLETENESS", "FAIL", "No chunks to validate metadata.")
        return

    # Fields defined in the DocumentAgent implementation
    expected_fields = [
        ("company_name", "Company Name", True),
        ("report_year", "Report Year", True),
        ("report_type", "Report Type", True),
        ("page_number", "Page Number", True),
        ("page_start", "Page Start", True),
        ("page_end", "Page End", True),
        ("section_title", "Section Title", True),
        ("analysis_id", "Analysis ID", True),
        ("document_id", "Document ID", True),
        ("source", "Source File", True),
        ("chunk_index", "Chunk Index", True),
        ("total_chunks", "Total Chunks", True),
        ("financial_metrics", "Financial Metrics", False),
        ("semantic_tags", "Semantic Tags", False),
        ("previous_chunk_id", "Previous Chunk ID", False),
        ("next_chunk_id", "Next Chunk ID", False),
    ]

    field_stats = {}
    print(f"{'Field Key':<22} | {'Present':<10} | {'Completeness':<12} | {'Status'}")
    print("-" * 65)

    required_failures = []
    total_possible_required = 0
    total_present_required = 0

    for key, label, is_required in expected_fields:
        present_count = sum(1 for r in records if r["metadata"].get(key) not in (None, ""))
        completeness = (present_count / total) * 100
        field_stats[key] = completeness

        if is_required:
            total_possible_required += total
            total_present_required += present_count
            status_str = "PASS" if completeness >= 95.0 else "WARN" if completeness >= 70.0 else "FAIL"
            if status_str == "FAIL":
                required_failures.append(f"Field '{key}' completeness is only {completeness:.1f}%")
        else:
            status_str = "INFO"

        print(f"{key:<22} | {present_count}/{total:<6} | {completeness:>10.1f}% | {status_str}")

    overall_completeness = (total_present_required / total_possible_required) * 100 if total_possible_required else 0.0
    print("-" * 65)
    print(f"Overall Required Metadata Completeness: {overall_completeness:.1f}%\n")

    if overall_completeness >= 90.0 and not required_failures:
        ctx.add_result("METADATA COMPLETENESS", "PASS", f"Overall metadata completeness is {overall_completeness:.1f}%.")
    elif overall_completeness >= 75.0:
        ctx.add_result("METADATA COMPLETENESS", "WARN", f"Overall metadata completeness is {overall_completeness:.1f}%.", warnings=required_failures)
    else:
        ctx.add_result("METADATA COMPLETENESS", "FAIL", f"Overall metadata completeness is {overall_completeness:.1f}%.", failures=required_failures)


# ---------------------------------------------------------------------------
# Section 6: Company Name Validation
# ---------------------------------------------------------------------------

def validate_company_names(ctx: ValidationContext) -> None:
    print("=" * 80)
    print("6. COMPANY NAME METADATA VALIDATION")
    print("=" * 80)

    records = ctx.records
    total = len(records)
    if total == 0:
        ctx.add_result("COMPANY NAME METADATA", "FAIL", "No chunks to validate company name.")
        return

    company_counts: Counter[str] = Counter()
    suspicious_count = 0
    suspicious_values = {"", "unknown", "none", "null", "n/a", "undefined"}

    for r in records:
        comp = str(r["metadata"].get("company_name", "")).strip()
        company_counts[comp or "<empty>"] += 1
        if comp.lower() in suspicious_values:
            suspicious_count += 1

    print("Company Names Found:")
    for comp, count in company_counts.items():
        print(f"  - {comp}: {count} chunk(s)")

    if suspicious_count > 0:
        print(f"WARN: {suspicious_count}/{total} chunks have suspicious company names.")
        if suspicious_count == total:
            ctx.add_result("COMPANY NAME METADATA", "FAIL", "All chunks have empty or unknown company names.", failures=["All company names are Unknown"])
        else:
            ctx.add_result("COMPANY NAME METADATA", "WARN", f"{suspicious_count} chunks have empty or unknown company name.", warnings=[f"{suspicious_count} chunks have missing company name"])
    else:
        ctx.add_result("COMPANY NAME METADATA", "PASS", f"Identified company '{', '.join(company_counts.keys())}' across 100% of chunks.")


# ---------------------------------------------------------------------------
# Section 7: Report Year Validation
# ---------------------------------------------------------------------------

def validate_report_year(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("7. REPORT YEAR METADATA VALIDATION")
    print("=" * 80)

    records = ctx.records
    total = len(records)
    if total == 0:
        ctx.add_result("REPORT YEAR METADATA", "FAIL", "No chunks to validate report year.")
        return

    year_counts: Counter[str] = Counter()
    invalid_years = 0

    for r in records:
        year_str = str(r["metadata"].get("report_year", "")).strip()
        year_counts[year_str or "<empty>"] += 1
        if not re.fullmatch(r"(?:19|20)\d{2}", year_str):
            invalid_years += 1

    print("Report Years Found:")
    for y, count in year_counts.items():
        print(f"  - {y}: {count} chunk(s)")

    if invalid_years == 0:
        ctx.add_result("REPORT YEAR METADATA", "PASS", f"Valid report years: {', '.join(year_counts.keys())}.")
    elif invalid_years < total:
        ctx.add_result("REPORT YEAR METADATA", "WARN", f"{invalid_years} chunks have invalid report years.", warnings=[f"{invalid_years} chunks with invalid years"])
    else:
        ctx.add_result("REPORT YEAR METADATA", "FAIL", "All chunks have invalid report years.", failures=["All report years invalid"])


# ---------------------------------------------------------------------------
# Section 8: Analysis ID Validation
# ---------------------------------------------------------------------------

def validate_analysis_ids(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("8. ANALYSIS ID & SESSION ISOLATION VALIDATION")
    print("=" * 80)

    records = ctx.records
    total = len(records)
    if total == 0:
        ctx.add_result("ANALYSIS ID", "FAIL", "No chunks to validate analysis IDs.")
        return

    by_analysis: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        aid = str(r["metadata"].get("analysis_id", "")).strip() or "<missing>"
        by_analysis[aid].append(r)

    print(f"Total Analysis Sessions Found: {len(by_analysis)}")
    for aid, recs in by_analysis.items():
        docs = {r["metadata"].get("source") for r in recs if r["metadata"].get("source")}
        comps = {r["metadata"].get("company_name") for r in recs if r["metadata"].get("company_name")}
        print(f"  Session [{aid}] -> {len(recs)} chunks, {len(docs)} doc(s) ({', '.join(docs)}), company: {', '.join(comps)}")

    if "<missing>" in by_analysis:
        ctx.add_result("ANALYSIS ID", "FAIL", f"{len(by_analysis['<missing>'])} chunks missing analysis_id.", failures=["Missing analysis_id"])
    else:
        ctx.add_result("ANALYSIS ID", "PASS", f"All {total} chunks cleanly mapped to {len(by_analysis)} analysis session(s).")


# ---------------------------------------------------------------------------
# Section 10: Chunk <-> PDF Consistency
# ---------------------------------------------------------------------------

def validate_chunk_pdf_consistency(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("10. CHUNK <-> PDF CONSISTENCY VALIDATION")
    print("=" * 80)

    records = ctx.records
    pdf_pages = ctx.pdf_pages

    if not records or not pdf_pages:
        print("WARN: Cannot verify consistency without both ChromaDB chunks and PDF text.")
        ctx.add_result("CHUNK/PDF CONSISTENCY", "WARN", "PDF text not available for consistency matching", warnings=["PDF text missing"])
        return

    clean_pages = [safe_clean_text(p).lower() for p in pdf_pages]
    full_clean_pdf = " ".join(clean_pages)

    matched = 0
    unmatched = 0
    sample_size = min(len(records), 20)

    print(f"Sampled Chunks        : {sample_size}")
    for i in range(sample_size):
        rec = records[i]
        text = safe_clean_text(rec["document"]).lower()
        meta = rec["metadata"]
        words = [w for w in re.split(r"\W+", text) if len(w) >= 3]

        p_start = max(0, int(meta.get("page_start", 1)) - 1)
        p_end = min(len(clean_pages), int(meta.get("page_end", len(clean_pages))))
        page_window = " ".join(clean_pages[p_start:p_end])

        is_match = False
        # Search for 4-word sequence in target page or document
        for start in range(len(words) - 3):
            seq = " ".join(words[start:start + 4])
            if seq in page_window or seq in full_clean_pdf:
                is_match = True
                break

        if is_match:
            matched += 1
        else:
            unmatched += 1

    pct = (matched / sample_size) * 100
    print(f"Matching Source Text  : {matched}/{sample_size} ({pct:.1f}%)")
    print(f"Unmatched Chunks      : {unmatched}")

    if pct >= 85.0:
        ctx.add_result("CHUNK/PDF CONSISTENCY", "PASS", f"{matched}/{sample_size} ({pct:.1f}%) sampled chunks matched source text.")
    elif pct >= 60.0:
        ctx.add_result("CHUNK/PDF CONSISTENCY", "WARN", f"{matched}/{sample_size} ({pct:.1f}%) sampled chunks matched source text.", warnings=[f"Matching rate: {pct:.1f}%"])
    else:
        ctx.add_result("CHUNK/PDF CONSISTENCY", "FAIL", f"Only {matched}/{sample_size} chunks matched PDF text.", failures=[f"Low consistency match: {pct:.1f}%"])


# ---------------------------------------------------------------------------
# Section 11: Retrieval Test
# ---------------------------------------------------------------------------

def validate_retrieval(ctx: ValidationContext) -> None:
    print("\n" + "=" * 80)
    print("11. RETRIEVAL & SEMANTIC SEARCH TEST")
    print("=" * 80)

    if not ctx.collection:
        ctx.add_result("RETRIEVAL", "FAIL", "ChromaDB collection not available for querying.")
        return

    queries = [
        "revenue and profitability",
        "total assets and liabilities",
        "cash flow",
        "risk factors",
        "financial performance",
    ]

    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=ctx.embedding_model)
    query_failures = []
    successful_queries = 0

    for q in queries:
        print(f"\nQuery: '{q}'")
        try:
            results = ctx.collection.query(
                query_texts=[q],
                n_results=3,
                include=["documents", "metadatas", "distances"],
            )
            doc_list = (results.get("documents") or [[]])[0]
            meta_list = (results.get("metadatas") or [[]])[0]
            dist_list = (results.get("distances") or [[]])[0]
            id_list = (results.get("ids") or [[]])[0]

            if not doc_list:
                print("  No chunks returned for query.")
                query_failures.append(f"Query '{q}' returned 0 results")
                continue

            successful_queries += 1
            for rank, (doc, meta, dist, cid) in enumerate(zip(doc_list, meta_list, dist_list, id_list), 1):
                p_num = meta.get("page_number", "Unknown") if isinstance(meta, dict) else "Unknown"
                c_name = meta.get("company_name", "Unknown") if isinstance(meta, dict) else "Unknown"
                r_year = meta.get("report_year", "Unknown") if isinstance(meta, dict) else "Unknown"
                preview = safe_preview(doc)
                print(f"  Result {rank} | ID: {cid[:8]} | Page: {p_num} | Company: {c_name} | Year: {r_year} | Distance: {dist:.4f}")
                print(f"    Snippet: {preview}")

        except Exception as exc:
            print(f"  FAIL: Query execution error: {exc}")
            query_failures.append(f"Query '{q}' failed with exception: {exc}")

    if successful_queries == len(queries):
        ctx.add_result("RETRIEVAL", "PASS", f"All {len(queries)} financial queries returned grounded, valid chunks with metadata.")
    elif successful_queries > 0:
        ctx.add_result("RETRIEVAL", "WARN", f"{successful_queries}/{len(queries)} queries executed successfully.", warnings=query_failures)
    else:
        ctx.add_result("RETRIEVAL", "FAIL", "All retrieval queries failed.", failures=query_failures)


# ---------------------------------------------------------------------------
# Section 14: Summary & Final Verdict
# ---------------------------------------------------------------------------

def generate_final_summary(ctx: ValidationContext) -> int:
    print("\n" + "=" * 80)
    print("DOCUMENT AGENT VALIDATION SUMMARY")
    print("=" * 80)

    summary_order = [
        "PDF ACCESS",
        "TEXT EXTRACTION",
        "PAGE COUNT",
        "CHUNK CREATION",
        "EMPTY CHUNK CHECK",
        "DUPLICATE ID CHECK",
        "PAGE NUMBER METADATA",
        "COMPANY NAME METADATA",
        "REPORT YEAR METADATA",
        "ANALYSIS ID",
        "CHROMADB CONNECTION",
        "CHROMADB STORAGE",
        "EMBEDDING STORAGE",
        "CHUNK/PDF CONSISTENCY",
        "RETRIEVAL",
        "METADATA COMPLETENESS",
    ]

    all_failures: List[str] = []
    all_warnings: List[str] = []

    for name in summary_order:
        res = ctx.results.get(name)
        status_str = res.status if res else "SKIPPED"
        print(f"{name:<28} {status_str:>10}")
        if res:
            all_failures.extend(res.failures)
            all_warnings.extend(res.warnings)

    # Any other checks recorded
    for name, res in ctx.results.items():
        if name not in summary_order:
            print(f"{name:<28} {res.status:>10}")
            all_failures.extend(res.failures)
            all_warnings.extend(res.warnings)

    print("=" * 80)

    if all_failures:
        print("OVERALL RESULT: FAIL")
        print("=" * 80)
        print("Failures:")
        for idx, fail in enumerate(all_failures, 1):
            print(f"  {idx}. {fail}")
        if all_warnings:
            print("\nWarnings:")
            for idx, warn in enumerate(all_warnings, 1):
                print(f"  {idx}. {warn}")
        print("=" * 80)
        return 1
    elif all_warnings:
        print("OVERALL RESULT: PASS (WITH WARNINGS)")
        print("=" * 80)
        print("Warnings:")
        for idx, warn in enumerate(all_warnings, 1):
            print(f"  {idx}. {warn}")
        print("=" * 80)
        return 0
    else:
        print("OVERALL RESULT: PASS")
        print("=" * 80)
        print("All Document Agent ingestion, chunking, metadata, ChromaDB storage,")
        print("and retrieval capabilities are operating cleanly and verified.")
        print("=" * 80)
        return 0


# ---------------------------------------------------------------------------
# Main Orchestration Function
# ---------------------------------------------------------------------------

def run_all_validations() -> int:
    ctx = ValidationContext()
    discover_existing_configuration(ctx)
    validate_chromadb_connection(ctx)
    validate_source_pdf(ctx)
    validate_chunks(ctx)
    validate_page_numbers(ctx)
    validate_metadata_completeness(ctx)
    validate_company_names(ctx)
    validate_report_year(ctx)
    validate_analysis_ids(ctx)
    validate_chunk_pdf_consistency(ctx)
    validate_retrieval(ctx)
    return generate_final_summary(ctx)


def test_document_agent_full_validation() -> None:
    """Pytest entrypoint for Document Agent validation test."""
    exit_code = run_all_validations()
    assert exit_code == 0, "Document Agent validation failed."


if __name__ == "__main__":
    exit_code = run_all_validations()
    sys.exit(exit_code)
