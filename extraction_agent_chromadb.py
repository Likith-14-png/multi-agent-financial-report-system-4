# Production Extraction Agent
# Reads processed document chunks from ChromaDB
# Used in the Multi-Agent Financial Research System
import chromadb
import json
import re

# Connect to ChromaDB
client = chromadb.PersistentClient(path="enterprise_chroma_db")

# Open collection
collection = client.get_collection("financial_research_v1")

# Read all documents
results = collection.get(include=["documents", "metadatas"])

# Combine all chunks into one report
report = "\n".join(results["documents"])


# Function to extract values
def extract_from_chunk(metric, pattern):
    for doc, meta in zip(results["documents"], results["metadatas"]):
        metrics = meta.get("financial_metrics", "")

        if metric.lower() in metrics.lower():
            match = re.search(pattern, doc, re.IGNORECASE)
            if match:
                return match.group(1).strip()

    return "Not Found"

# Extract financial metrics
data = {
    "Company": "Microsoft",
    "Report": "2024 Annual Report",

    "Revenue": extract_from_chunk(
        "Revenue",
        r"\$([\d.,]+)\s*billion.*?revenue"
    ),

    "Operating Income": extract_from_chunk(
        "Operating Income",
        r"\$([\d.,]+)\s*billion.*?operating income"
    ),

    "Net Income": extract_from_chunk(
        "Net Income",
        r"net income.*?\$([\d.,]+)"
    ),

    "Assets": extract_from_chunk(
        "Assets",
        r"total assets.*?\$([\d.,]+)"
    ),

    "Liabilities": extract_from_chunk(
        "Liabilities",
        r"total liabilities.*?\$([\d.,]+)"
    ),

    "Cash Flow": extract_from_chunk(
        "Cash Flow",
        r"cash flow.*?\$([\d.,]+)"
    ),

    "EPS": extract_from_chunk(
        "EPS",
        r"earnings per share.*?([\d.]+)"
    )
}

# Display results
print("\n===== Extracted Financial Metrics =====\n")
print(json.dumps(data, indent=4))

# Save JSON
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

print("\n✅ Data saved to output.json")