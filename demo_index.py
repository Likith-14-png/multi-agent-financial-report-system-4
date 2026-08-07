"""
demo_index.py
=============
Builds a REAL ChromaDB collection (persisted locally) from the seed
documents, using sentence-transformers embeddings — matching the actual
tech stack in the project README. This mimics what the Document Agent
(Likith) will do in the full system, so the Research Agent can be tested
end-to-end on its own.

Requires: chromadb, sentence-transformers (see requirements.txt) and a
machine with internet access the first time it runs (to download the
'all-MiniLM-L6-v2' embedding model from Hugging Face — it's cached locally
after that).

Run:
    python3 demo_index.py          # builds ./chroma_db
    python3 -c "
        import chromadb
        from chromadb.utils import embedding_functions
        from research_agent import ResearchAgent

        client = chromadb.PersistentClient(path='./chroma_db')
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name='all-MiniLM-L6-v2')
        collection = client.get_collection('financial_documents', embedding_function=embed_fn)

        agent = ResearchAgent(collection)
        ans = agent.answer('Which company has the highest debt-to-equity ratio?')
        print(ans.final_answer)
    "
"""
import re
import uuid
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

SEED_DIR = Path(__file__).parent / "seed_docs"
CHROMA_PATH = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "financial_documents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

SEED_COMPANIES = [
    ("orion_steelworks.txt", "Orion Steelworks Ltd", "Annual Report", "FY2024"),
    ("vantage_retail.txt", "Vantage Retail Corp", "Annual Report", "FY2024"),
    ("nimbus_cloud.txt", "Nimbus Cloud Technologies Inc", "Annual Report", "FY2024"),
]


def _chunk_text(text: str, target_words: int = 120, overlap: int = 20):
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        piece = words[i:i + target_words]
        if piece:
            chunks.append(" ".join(piece))
        i += target_words - overlap
    return chunks


def _guess_section(chunk_text: str) -> str:
    t = chunk_text.lower()
    if any(k in t for k in ["balance sheet", "total assets", "total liabilities"]):
        return "Balance Sheet"
    if any(k in t for k in ["income statement", "net income", "gross profit", "revenue"]):
        return "Income Statement"
    if any(k in t for k in ["cash flow", "operating activities"]):
        return "Cash Flow Statement"
    if any(k in t for k in ["auditor", "qualified opinion", "going concern", "material weakness"]):
        return "Auditor's Report"
    if any(k in t for k in ["risk factor"]):
        return "Risk Factors"
    if any(k in t for k in ["management discussion", "outlook", "md&a"]):
        return "MD&A"
    return "General"


def main():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=embed_fn)

    for filename, company, doc_type, period in SEED_COMPANIES:
        text = (SEED_DIR / filename).read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"\s+", " ", text).strip()
        doc_id = str(uuid.uuid4())[:8]

        ids, docs, metas = [], [], []
        for idx, chunk in enumerate(_chunk_text(text)):
            ids.append(f"{doc_id}-{idx}")
            docs.append(chunk)
            metas.append({
                "company": company, "doc_type": doc_type,
                "section": _guess_section(chunk), "source_file": filename,
                "period": period,
            })
        collection.add(ids=ids, documents=docs, metadatas=metas)
        print(f"Indexed '{company}' — {len(ids)} chunks")

    print(f"\nDone. Collection '{COLLECTION_NAME}' persisted at {CHROMA_PATH}")


if __name__ == "__main__":
    main()
