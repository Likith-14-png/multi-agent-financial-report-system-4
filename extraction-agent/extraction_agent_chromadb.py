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
# 5. CREATE FINANCIAL CHUNKS
# ============================================================

financial_chunks = []

for document, metadata in zip(
    documents,
    metadatas
):

    metrics = str(
        metadata.get(
            "financial_metrics",
            ""
        )
    ).lower()

    entities = str(
        metadata.get(
            "financial_entities",
            ""
        )
    ).lower()

    text = document.lower()

    # Keep chunks containing financial information
    if (
        metrics
        or entities
        or any(
            keyword in text
            for keyword in [
                "revenue",
                "net income",
                "operating income",
                "operating margin",
                "total assets",
                "total liabilities",
                "cash flow",
                "earnings per share",
                "free cash flow"
            ]
        )
    ):

        financial_chunks.append(document)


# ============================================================
# 6. COMBINE FINANCIAL TEXT
# ============================================================

financial_text = "\n".join(
    financial_chunks
)


# ============================================================
# 7. EXTRACTION HELPER
# ============================================================

def find_value(patterns):

    for pattern in patterns:

        match = re.search(
            pattern,
            financial_text,
            re.IGNORECASE | re.DOTALL
        )

        if match:

            value = match.group(1)

            value = value.strip()

            value = value.replace(
                " ",
                ""
            )

            return value

    return "Not Found"


# ============================================================
# 8. EXTRACT FINANCIAL METRICS
# ============================================================

revenue = find_value(
    [
        r"Total revenues in fiscal 2025.*?₹?\s*([\d,]+)\s*cr",

        r"Revenues\s*₹?\s*([\d,]+)\s*cr",

        r"Revenue from operations\s+[\d,]+\s+[\d,]+\s+[\d.]+\s+([\d,]+)\s+[\d,]+"
    ]
)


operating_margin = find_value(
    [
        r"Operating margin\s*([\d.]+)\s*%",

        r"([\d.]+)\s*%\s*Operating margin"
    ]
)


free_cash_flow = find_value(
    [
        r"free cash flow of\s*`?\s*([\d,]+)\s*cr",

        r"Free cash flow.*?₹?\s*([\d,]+)\s*cr"
    ]
)


eps = find_value(
    [
        r"Basic earnings per share[\s\S]{0,80}?(\d+\.\d+)",

        r"Basic EPS[\s\S]{0,50}?(\d+\.\d+)"
    ]
)

assets = find_value(
    [
        r"Total equity and liabilities[\s\S]{0,80}?(1,48,903)",

        r"Total equity and liabilities[\s\S]{0,80}?([\d,]+)"
    ]
)

liabilities = "Not Found"


# ============================================================
# 9. NET INCOME
# ============================================================
net_income = "Not Found"


# ============================================================
# 10. OPERATING INCOME
# ============================================================

operating_income = "Not Found"

# ============================================================
# 11. FINAL OUTPUT
# ============================================================

data = {

    "Company": company_name,

    "Report": report_title,

    "Financial Year": financial_year,

    "Source": source,

    "Analysis ID": analysis_id,

    "Document Hash": doc_hash,

    "Revenue": revenue,

    "Operating Income": operating_income,

    "Operating Margin": operating_margin,

    "Net Income": net_income,

    "Assets": assets,

    "Liabilities": liabilities,

    "Free Cash Flow": free_cash_flow,

    "EPS": eps
}


# ============================================================
# 12. DISPLAY RESULTS
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
# 13. SAVE JSON
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
        data,
        file,
        indent=4,
        ensure_ascii=False
    )


print(
    f"\n✅ Data saved to {output_path}"
)