# Production Extraction Agent
# Reads processed document chunks from the shared ChromaDB
# Used in the Multi-Agent Financial Research System

import chromadb
import json
import re
import sys
from pathlib import Path

# ============================================================
# 1. CONNECT TO SHARED CHROMADB
# ============================================================

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent
        / "document-agent-text-chunking"
        / "scripts"
    )
)

from shared_chroma_path import resolve_chroma_db_path


chroma_path = resolve_chroma_db_path(
    script_file=__file__,
    workspace_root=Path(__file__).resolve().parent.parent
)

print(f"Using ChromaDB: {chroma_path}")

client = chromadb.PersistentClient(
    path=str(chroma_path)
)

collection = client.get_collection(
    "financial_research_v1"
)


# ============================================================
# 2. GET ANALYSIS ID AND DOCUMENT HASH
# ============================================================

if len(sys.argv) != 3:

    print("\nUsage:")
    print(
        "python extraction_agent_chromadb.py "
        "<analysis_id> <doc_hash>"
    )

    sys.exit(1)


analysis_id = sys.argv[1]
doc_hash = sys.argv[2]


# ============================================================
# 3. GET DOCUMENT CHUNKS
# ============================================================

results = collection.get(
    where={
        "$and": [
            {
                "analysis_id": analysis_id
            },
            {
                "doc_hash": doc_hash
            }
        ]
    },
    include=[
        "documents",
        "metadatas"
    ]
)


documents = results.get(
    "documents",
    []
)

metadatas = results.get(
    "metadatas",
    []
)


if not documents:

    print("\n❌ No matching document found.")

    print(
        f"Analysis ID: {analysis_id}"
    )

    print(
        f"Document Hash: {doc_hash}"
    )

    sys.exit(1)


print(
    f"\n✅ Retrieved {len(documents)} chunks "
    "for the selected document."
)


# ============================================================
# 4. DOCUMENT INFORMATION
# ============================================================

first_metadata = (
    metadatas[0]
    if metadatas
    else {}
)


company_name = first_metadata.get(
    "company_name",
    "Not Found"
)

report_title = first_metadata.get(
    "report_title",
    first_metadata.get(
        "document_title",
        "Not Found"
    )
)

financial_year = first_metadata.get(
    "financial_year",
    "Not Found"
)

source = first_metadata.get(
    "source",
    "Not Found"
)


# ============================================================
# 5. EXECUTE ENHANCED EXTRACTION
# ============================================================

from extraction_agent import extract_report_metrics

chunk_records = []
for idx, (doc, meta) in enumerate(zip(documents, metadatas)):
    meta_dict = meta if isinstance(meta, dict) else {}
    chunk_records.append({
        "chunk_id": str(meta_dict.get("chunk_id") or f"chunk-{idx}"),
        "chunk_index": int(meta_dict.get("chunk_index", idx)),
        "page_start": int(meta_dict.get("page_start", 1)) if meta_dict.get("page_start") is not None else 1,
        "page_end": int(meta_dict.get("page_end", 1)) if meta_dict.get("page_end") is not None else 1,
        "section_title": meta_dict.get("section_title", "Unknown"),
        "text": doc,
        "metadata": meta_dict,
    })

combined_text = "\n\n".join(documents)
extraction_output = extract_report_metrics(
    combined_text,
    metadata=first_metadata,
    chunk_records=chunk_records,
)

data = {
    "Company": company_name,
    "Report": report_title,
    "Financial Year": financial_year,
    "Source": source,
    "Analysis ID": analysis_id,
    "Document Hash": doc_hash,
    "Revenue": extraction_output.get("revenue") or "Not Found",
    "Operating Income": extraction_output.get("operating_income") or "Not Found",
    "Net Income": extraction_output.get("net_income") or "Not Found",
    "Assets": extraction_output.get("total_assets") or "Not Found",
    "Liabilities": extraction_output.get("total_liabilities") or "Not Found",
    "Equity": extraction_output.get("total_equity") or "Not Found",
    "Free Cash Flow": extraction_output.get("free_cash_flow") or "Not Found",
    "Operating Cash Flow": extraction_output.get("operating_cash_flow") or "Not Found",
    "EPS": extraction_output.get("eps") or "Not Found",
    "R&D": extraction_output.get("rd_expense") or "Not Found",
    "Total Debt": extraction_output.get("total_debt") or "Not Found",
    "Yearly Metrics": extraction_output.get("yearly_metrics") or {},
    "Segment Metrics": extraction_output.get("segment_metrics") or {},
    "Accounting Notes": extraction_output.get("accounting_information") or [],
    "Risk Metrics": extraction_output.get("risk_related_metrics") or [],
}


# ============================================================
# 6. DISPLAY RESULTS
# ============================================================

print(
    "\n===== Extracted Financial Metrics =====\n"
)

print(
    json.dumps(
        data,
        indent=4,
        ensure_ascii=False
    )
)


# ============================================================
# 7. SAVE JSON
# ============================================================

output_path = (
    Path(__file__).parent
    / "output.json"
)


with open(
    output_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        extraction_output,
        file,
        indent=4,
        ensure_ascii=False
    )


print(
    f"\n✅ Data saved to {output_path}"
)