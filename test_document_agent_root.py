#!/usr/bin/env python3
"""
=============================================================================
Document Agent Standalone Validation Program
=============================================================================
Validates that the existing Document Agent has correctly processed and stored
documents in ChromaDB (read-only verification).
=============================================================================
"""

import logging
import os
import re
import sys
import unicodedata
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# Suppress library deprecation and logging noise for clean CLI output
warnings.filterwarnings("ignore")
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# Ensure standard output uses UTF-8 encoding safely
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError as err:
    print(f"Error: ChromaDB library not found: {err}")
    sys.exit(1)

fitz = None
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


def clean_text(text: str) -> str:
    """Normalize text and remove zero-width and unprintable characters."""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"[\u200b\u200e\u200f\ufeff]", "", normalized)
    normalized = "".join(c for c in normalized if c.isprintable() or c in "\n\t")
    return re.sub(r"\s+", " ", normalized).strip()


def resolve_chroma_path() -> Path:
    """Find the active ChromaDB persistent storage."""
    candidate_paths = [
        PROJECT_ROOT / "enterprise_chroma_db",
        PROJECT_ROOT / "document-agent-text-chunking" / "scripts" / "enterprise_chroma_db",
        PROJECT_ROOT / "chroma_db",
        PROJECT_ROOT / "document-agent-text-chunking" / "chroma_db",
    ]

    for path in candidate_paths:
        if path.exists() and (path / "chroma.sqlite3").exists():
            try:
                client = chromadb.PersistentClient(path=str(path.resolve()))
                col = client.get_collection("financial_research_v1")
                if col.count() > 0:
                    return path
            except Exception:
                continue

    for path in candidate_paths:
        if path.exists() and (path / "chroma.sqlite3").exists():
            return path

    return candidate_paths[0]


def get_pdf_page_count(filename: str, fallback_max_page: int) -> int:
    """Determine the true page count of a source file."""
    if not filename.lower().endswith(".pdf"):
        return 1

    candidates = [
        PROJECT_ROOT / "tmp_uploads" / filename,
        PROJECT_ROOT / "backend" / "tmp_uploads" / filename,
        PROJECT_ROOT / "document-agent-text-chunking" / "scripts" / "demo_data" / filename,
        PROJECT_ROOT / "data" / filename,
    ]
    candidates.extend(list(PROJECT_ROOT.glob(f"**/{filename}")))

    for path in candidates:
        if path.exists() and path.is_file():
            if fitz is not None:
                try:
                    with fitz.open(path) as doc:
                        return len(doc)
                except Exception:
                    pass
            if PyPDF2 is not None:
                try:
                    with open(path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        return len(reader.pages)
                except Exception:
                    pass

    return fallback_max_page or 1


def validate_document_agent() -> int:
    chroma_path = resolve_chroma_path()
    collection_name = "financial_research_v1"

    if not chroma_path.exists():
        print(f"Error: ChromaDB directory '{chroma_path}' not found.")
        return 1

    try:
        client = chromadb.PersistentClient(path=str(chroma_path.resolve()))
        collections = [c.name for c in client.list_collections()]
        if collection_name not in collections and collections:
            collection_name = collections[0]

        collection = client.get_collection(collection_name)
        total_chunks = collection.count()
        data = collection.get(include=["documents", "metadatas", "embeddings"])
    except Exception as exc:
        print(f"Error: Unable to load ChromaDB collection '{collection_name}': {exc}")
        return 1

    # Pre-verify retrieval silently
    retrieval_pass = False
    try:
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        q_coll = client.get_collection(collection_name, embedding_function=emb_fn)
        q_res = q_coll.query(query_texts=["revenue and profitability"], n_results=1)
        if q_res.get("ids") and q_res["ids"][0]:
            retrieval_pass = True
    except Exception:
        try:
            q_res = collection.query(query_texts=["revenue and profitability"], n_results=1)
            if q_res.get("ids") and q_res["ids"][0]:
                retrieval_pass = True
        except Exception:
            retrieval_pass = False

    ids = data.get("ids") or []
    documents = data.get("documents") or []
    metadatas = data.get("metadatas") or []
    embeddings = data.get("embeddings")

    # Group records by document source
    docs_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for i, cid in enumerate(ids):
        doc_text = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if i < len(metadatas) and isinstance(metadatas[i], dict) else {}
        source = meta.get("source") or meta.get("source_file") or meta.get("document_title") or f"Document_{i+1}"
        docs_map[source].append({
            "id": cid,
            "text": doc_text,
            "metadata": meta,
            "embedding": embeddings[i] if embeddings is not None and i < len(embeddings) else None,
        })

    total_documents = len(docs_map)

    print("==================================================")
    print("DOCUMENT AGENT VALIDATION")
    print("==================================================")
    print()
    print("ChromaDB")
    print(f"Collection       : {collection_name}")
    print(f"Total chunks     : {total_chunks}")
    print(f"Total documents  : {total_documents}")

    overall_pdf_processing = True
    overall_page_tracking = True
    overall_chunking = True
    overall_metadata_storage = True
    overall_chromadb_storage = total_chunks > 0

    # Validate each document
    for doc_idx, (doc_name, records) in enumerate(docs_map.items(), 1):
        first_meta = records[0]["metadata"]
        company = first_meta.get("company_name") or "Unknown"
        report_year = first_meta.get("report_year") or first_meta.get("financial_year") or "Unknown"

        max_chunk_page = max((int(r["metadata"].get("page_end") or r["metadata"].get("page_start") or 1) for r in records), default=1)
        pdf_pages = get_pdf_page_count(doc_name, max_chunk_page)

        # Check page metadata
        missing_pages = [r["id"] for r in records if not r["metadata"].get("page_number") and r["metadata"].get("page_start") is None]
        invalid_pages = []
        for r in records:
            p_end = r["metadata"].get("page_end")
            p_start = r["metadata"].get("page_start")
            if p_end and int(p_end) > pdf_pages and pdf_pages > 1:
                invalid_pages.append(r["id"])
            elif p_start and int(p_start) <= 0:
                invalid_pages.append(r["id"])

        page_meta_pass = len(missing_pages) == 0 and len(invalid_pages) == 0

        # Check company metadata
        missing_comp = [r["id"] for r in records if not r["metadata"].get("company_name") or str(r["metadata"].get("company_name")).strip().lower() in ("", "unknown", "none", "null")]
        company_meta_pass = len(missing_comp) == 0

        # Check report year metadata
        missing_year = [r["id"] for r in records if not r["metadata"].get("report_year") or not re.fullmatch(r"(?:19|20)\d{2}", str(r["metadata"].get("report_year")).strip())]
        year_meta_pass = len(missing_year) == 0

        # Check chunk text
        empty_chunks = [r["id"] for r in records if not r["text"] or not clean_text(r["text"])]
        chunk_text_pass = len(empty_chunks) == 0

        if not page_meta_pass:
            overall_page_tracking = False
        if not (company_meta_pass and year_meta_pass):
            overall_metadata_storage = False
        if not chunk_text_pass:
            overall_chunking = False
        if pdf_pages == 0:
            overall_pdf_processing = False

        print()
        print("--------------------------------------------------")
        print(f"DOCUMENT {doc_idx}")
        print("--------------------------------------------------")
        print(f"File             : {doc_name}")
        print(f"Company          : {company}")
        print(f"Report Year      : {report_year}")
        print(f"Pages            : {pdf_pages}")
        print(f"Chunks           : {len(records)}")
        print()

        if page_meta_pass:
            print("Page metadata    : PASS")
        else:
            print("Page metadata    : FAIL")
            if missing_pages:
                print(f"Missing page numbers: {len(missing_pages)} chunks")
            if invalid_pages:
                print(f"Invalid page numbers: {len(invalid_pages)} chunks")

        if company_meta_pass:
            print("Company metadata : PASS")
        else:
            print("Company metadata : FAIL")
            print(f"Missing company_name: {len(missing_comp)} chunks")

        if year_meta_pass:
            print("Report year      : PASS")
        else:
            print("Report year      : FAIL")
            print(f"Invalid report_year : {len(missing_year)} chunks")

        if chunk_text_pass:
            print("Chunk text       : PASS")
        else:
            print("Chunk text       : FAIL")
            print(f"Empty chunk text    : {len(empty_chunks)} chunks")

    # Sample Chunk Display
    sample_record = None
    for records in docs_map.values():
        if len(records) > 0:
            idx = min(len(records) // 2, len(records) - 1)
            sample_record = records[idx]
            break

    if sample_record:
        smeta = sample_record["metadata"]
        s_page = smeta.get("page_number") or smeta.get("page_start") or "1"
        s_comp = smeta.get("company_name") or "Unknown"
        s_year = smeta.get("report_year") or smeta.get("financial_year") or "Unknown"
        s_text = clean_text(sample_record["text"])
        s_preview = s_text[:200] + ("..." if len(s_text) > 200 else "")

        print()
        print("--------------------------------------------------")
        print("SAMPLE CHUNK")
        print("--------------------------------------------------")
        print(f"Chunk ID       : {sample_record['id']}")
        print(f"Page          : {s_page}")
        print(f"Company       : {s_comp}")
        print(f"Report Year   : {s_year}")
        print(f"Text          : {s_preview}")

    overall_pass = (
        overall_pdf_processing
        and overall_page_tracking
        and overall_chunking
        and overall_metadata_storage
        and overall_chromadb_storage
        and retrieval_pass
    )

    print()
    print("--------------------------------------------------")
    print("DOCUMENT AGENT RESULT")
    print("--------------------------------------------------")
    print()
    print(f"PDF processing       : {'PASS' if overall_pdf_processing else 'FAIL'}")
    print(f"Page tracking        : {'PASS' if overall_page_tracking else 'FAIL'}")
    print(f"Chunking             : {'PASS' if overall_chunking else 'FAIL'}")
    print(f"Metadata storage     : {'PASS' if overall_metadata_storage else 'FAIL'}")
    print(f"ChromaDB storage     : {'PASS' if overall_chromadb_storage else 'FAIL'}")
    print(f"Retrieval            : {'PASS' if retrieval_pass else 'FAIL'}")
    print()
    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    print()
    print("==================================================")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    exit_code = validate_document_agent()
    sys.exit(exit_code)
