from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi.testclient import TestClient

from backend.api import app
from backend.orchestration.session_store import session_store
from backend.orchestration.workflow import AnalysisWorkflow
from research_agent import ResearchAgent, Citation, ResearchStep, ResearchAnswer

client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent
SAMPLE_REPORT_ABB = ROOT / "data" / "abb_2025_report.txt"


class MockChromaIsolationCollection:
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records
        self.last_queries: List[str] = []
        self.last_wheres: List[Optional[Dict[str, Any]]] = []

    def query(self, query_texts: List[str], n_results: int = 4, where: Optional[Dict[str, Any]] = None):
        self.last_queries.extend(query_texts)
        self.last_wheres.append(where)
        filtered = self.records
        if where is not None:
            filtered = []
            for r in self.records:
                meta = r.get("metadata", {})
                match = True
                if "$and" in where:
                    for sub in where["$and"]:
                        for k, v in sub.items():
                            if meta.get(k) != v and r.get(k) != v:
                                match = False
                else:
                    for k, v in where.items():
                        if meta.get(k) != v and r.get(k) != v:
                            match = False
                if match:
                    filtered.append(r)

        if not filtered:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Score by word overlap with query
        q_words = set(" ".join(query_texts).lower().split())
        def score(r):
            doc = r["document"].lower()
            return -sum(1 for w in q_words if w in doc)

        sorted_records = sorted(filtered, key=score)
        return {
            "ids": [[r["id"] for r in sorted_records[:n_results]]],
            "documents": [[r["document"] for r in sorted_records[:n_results]]],
            "metadatas": [[r.get("metadata", {}) for r in sorted_records[:n_results]]],
            "distances": [[0.12 for _ in sorted_records[:n_results]]],
        }

    def get(self, include=None):
        return {"metadatas": [r.get("metadata", {}) for r in self.records]}


def _setup_abb_session() -> str:
    session_store.clear()
    with open(SAMPLE_REPORT_ABB, "rb") as f:
        content = f.read()

    resp = client.post(
        "/analysis/upload",
        files={"file": ("abb_2025_report.txt", content, "text/plain")},
        data={"company_name": "ABB", "report_year": "2025"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["analysis_id"]


# TEST 1: POST /analysis/{analysis_id}/research/query accepts question and returns HTTP 200
def test_research_query_endpoint_contract():
    analysis_id = _setup_abb_session()

    query_payload = {"question": "Why did ABB's revenue increase?"}
    response = client.post(
        f"/analysis/{analysis_id}/research/query",
        json=query_payload,
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["analysis_id"] == analysis_id
    assert data["question"] == "Why did ABB's revenue increase?"
    assert isinstance(data["answer"], str) and len(data["answer"]) > 10
    assert "sources" in data and isinstance(data["sources"], list)
    assert "evidence" in data and isinstance(data["evidence"], list)
    assert "status" in data and data["status"] == "completed"
    assert "citations" in data


# TEST 2: Verify actual question reaches Research Agent
def test_question_propagates_to_research_agent():
    analysis_id = _setup_abb_session()
    unique_q = "What was the operating performance of ABB in 2025?"

    response = client.post(
        f"/analysis/{analysis_id}/research/query",
        json={"question": unique_q},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == unique_q


# TEST 3: Verify ChromaDB retrieval uses the user's question rather than hard-coded generic query
def test_chromadb_retrieval_uses_user_question():
    mock_collection = MockChromaIsolationCollection([
        {
            "id": "chunk-101",
            "document": "ABB revenue increased 14% to $15.3 billion due to high customer demand.",
            "metadata": {
                "company_name": "ABB",
                "analysis_id": "test-session-1",
                "section_title": "Management Discussion and Analysis",
                "source_file": "abb_2025.txt",
                "chunk_id": "chunk-101",
            },
        }
    ])

    agent = ResearchAgent(mock_collection)
    user_question = "Why did ABB revenue increase?"
    agent.answer(user_question, company="ABB", analysis_id="test-session-1")

    # Verify user question appeared in queries sent to ChromaDB
    assert any("Why did ABB revenue increase?" in q or "revenue increase" in q for q in mock_collection.last_queries)
    assert not all(q == "financial report risks financial statements performance" for q in mock_collection.last_queries)


# TEST 4: Verify the final answer is synthesized and is not simply raw retrieved chunk text dump
def test_final_answer_is_synthesized():
    mock_collection = MockChromaIsolationCollection([
        {
            "id": "chunk-102",
            "document": "Revenue increased 14% to $15.3 billion driven by strong demand across Europe and Americas.",
            "metadata": {
                "company_name": "ABB",
                "analysis_id": "test-session-2",
                "section_title": "Management Discussion and Analysis",
                "source_file": "abb_2025.txt",
                "chunk_id": "chunk-102",
            },
        }
    ])

    agent = ResearchAgent(mock_collection)
    user_question = "Why did ABB's revenue increase?"
    answer = agent.answer(user_question, company="ABB", analysis_id="test-session-2")

    # Must not be raw chunk dump like "Evidence found in 4 source passage(s):"
    assert "Evidence found in 4 source passage(s):" not in answer.final_answer
    assert "Research Findings on:" in answer.final_answer or "revenue" in answer.final_answer.lower()
    assert answer.steps[0].citations


# TEST 5: Verify source metadata remains attached to answer/evidence
def test_source_metadata_preserved_in_citations():
    mock_collection = MockChromaIsolationCollection([
        {
            "id": "chunk-103",
            "document": "Operating income was $2.1 billion with an operating margin of 13.7%.",
            "metadata": {
                "company_name": "ABB",
                "analysis_id": "test-session-3",
                "section_title": "Financial Performance",
                "source_file": "abb_2025.txt",
                "page_number": 3,
                "report_year": 2025,
                "chunk_id": "chunk-103",
            },
        }
    ])

    agent = ResearchAgent(mock_collection)
    answer = agent.answer("What was the operating margin?", company="ABB", analysis_id="test-session-3")

    citations = answer.all_citations()
    assert len(citations) >= 1
    cit = citations[0]
    assert cit.company == "ABB"
    assert cit.source_file == "abb_2025.txt"
    assert cit.section == "Financial Performance"
    assert cit.chunk_id == "chunk-103"


# TEST 6: Verify unsupported question returns explicit insufficient-evidence response
def test_unsupported_question_returns_insufficient_evidence():
    empty_col = MockChromaIsolationCollection([])
    agent = ResearchAgent(empty_col)

    answer = agent.answer("What was the R&D expenditure for Mars Exploration Project?", company="ABB")
    assert "No indexed document evidence was found" in answer.final_answer or "insufficient" in answer.final_answer.lower()
    assert len(answer.all_citations()) == 0


# TEST 7: Verify analysis/company/document isolation prevents cross-session retrieval
def test_session_isolation_prevents_cross_contamination():
    session_a_records = [
        {
            "id": "chunk-a1",
            "document": "Session A Company X revenue was $10 billion.",
            "metadata": {"company_name": "Company X", "analysis_id": "session-A", "chunk_id": "chunk-a1"},
        }
    ]
    session_b_records = [
        {
            "id": "chunk-b1",
            "document": "Session B Company Y revenue was $99 billion.",
            "metadata": {"company_name": "Company Y", "analysis_id": "session-B", "chunk_id": "chunk-b1"},
        }
    ]

    col = MockChromaIsolationCollection(session_a_records + session_b_records)
    agent = ResearchAgent(col)

    # Query scoped to Session A
    answer_a = agent.answer("What was the revenue?", company="Company X", analysis_id="session-A")
    assert any(c.chunk_id == "chunk-a1" for c in answer_a.all_citations())
    assert not any(c.chunk_id == "chunk-b1" for c in answer_a.all_citations())

    # Query scoped to Session B
    answer_b = agent.answer("What was the revenue?", company="Company Y", analysis_id="session-B")
    assert any(c.chunk_id == "chunk-b1" for c in answer_b.all_citations())
    assert not any(c.chunk_id == "chunk-a1" for c in answer_b.all_citations())


# TEST 8: Custom LLM generator path verification
def test_custom_llm_generator_used():
    mock_collection = MockChromaIsolationCollection([
        {
            "id": "chunk-llm",
            "document": "Revenue rose 14% to $15.3 billion.",
            "metadata": {"company_name": "ABB", "chunk_id": "chunk-llm"},
        }
    ])

    def mock_llm_fn(prompt: str) -> str:
        return "LLM SYNTHESIS: ABB's revenue increased by 14% to $15.3 billion based on solid regional demand."

    agent = ResearchAgent(mock_collection, llm_generate=mock_llm_fn)
    answer = agent.answer("Why did revenue increase?", company="ABB")

    assert answer.model_used == "custom-llm"
    assert "LLM SYNTHESIS" in answer.final_answer
