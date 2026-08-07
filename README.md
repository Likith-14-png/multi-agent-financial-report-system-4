RESEARCH AGENT

Part of the **Multi-Agent Financial Research System**
(Infosys Springboard Virtual Internship 7.0, Team 4).

Handles: answering financial questions, multi-step reasoning, retrieval
from ChromaDB, and source citations — per the project README.

## Files
- `research_agent.py` — the agent itself (`ResearchAgent` class). This is
  the only file the rest of the team needs to import.
- `demo_index.py` — builds a real ChromaDB collection (with
  sentence-transformers embeddings) from the seed documents, so you can run
  the Research Agent standalone before the Document Agent is wired up.
- `seed_docs/` — 3 fictional company annual reports (Orion Steelworks Ltd,
  Vantage Retail Corp, Nimbus Cloud Technologies Inc) used for testing.
- `tests/fake_chroma_collection.py` + `tests/test_research_agent_mock.py` —
  an offline test harness that mimics ChromaDB's `.query()`/`.get()` shape,
  so the agent's logic can be verified without installing chromadb /
  sentence-transformers or having network access. **This does not replace
  testing against real ChromaDB** — run `demo_index.py` + the real agent
  once you have chromadb/sentence-transformers installed, to confirm actual
  semantic retrieval quality.

## Install
```
pip install -r requirements.txt
```

## Try it (real ChromaDB)
```
python3 demo_index.py     # builds ./chroma_db from seed_docs/
```
```python
import chromadb
from chromadb.utils import embedding_functions
from research_agent import ResearchAgent

client = chromadb.PersistentClient(path="./chroma_db")
embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
collection = client.get_collection("financial_documents", embedding_function=embed_fn)

agent = ResearchAgent(collection)
answer = agent.answer(
    "Which company has the highest debt-to-equity ratio, and does "
    "Nimbus Cloud Technologies have any going concern risk?"
)
print(answer.final_answer)
for c in answer.all_citations():
    print(c)
```

## Try it offline (no chromadb install needed)
```
python3 tests/test_research_agent_mock.py
```
Runs the full decompose → retrieve → cite → synthesize flow against a mock
collection, so you can sanity-check the logic immediately.

## Integration contract with the rest of the team
`ResearchAgent(collection)` takes **whatever ChromaDB collection the
Document Agent (Likith) already created and populated** — Research Agent
never builds or writes to the collection itself. It expects each chunk's
metadata to look like:

```python
{
    "company":     "Orion Steelworks Ltd",
    "doc_type":    "Annual Report",       # or "10-K", "Earnings Call Transcript", ...
    "section":     "Balance Sheet",       # or "MD&A", "Auditor's Report", ...
    "source_file": "orion_steelworks.pdf",
    "period":      "FY2024",              # optional, "" if unknown
}
```
Share this schema with kusuma (Extraction) and rajan (Red Flag) too, since
their agents will likely also read chunk metadata from the same collection.

Keerthana's Report Agent can call `agent.answer(question)` for the "Research
Q&A" section of the PDF and use `answer.all_citations()` for the source list.

## Multi-step reasoning
A question like *"Which company has the highest debt-to-equity ratio, and
does Nimbus Cloud Technologies have going concern risk?"* is split into
sub-questions, each retrieved and cited independently, then combined into
one step-by-step answer — this is the "multi-step reasoning" behavior named
in the spec. Retrieval is automatically scoped to a company if one is named
in a sub-question (via ChromaDB's `where` filter), so questions about a
specific company don't get diluted by evidence from others.

## Plugging in an LLM (optional)
By default, `ResearchAgent` synthesizes the final answer with a
deterministic template — it can never state a figure that wasn't in a
retrieved chunk. To get more natural prose instead, wire in an LLM call
that only rephrases the already-grounded evidence:

```python
def call_llm(prompt: str) -> str:
    # call your LLM of choice here (Anthropic API, OpenAI, local HF model, ...)
    ...

agent.set_llm_generator(call_llm)
```
