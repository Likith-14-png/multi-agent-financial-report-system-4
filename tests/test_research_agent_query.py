from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi.testclient import TestClient

from backend.api import app
from backend.orchestration.session_store import session_store
from backend.orchestration.workflow import AnalysisWorkflow
import research_agent as research_agent_module
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


def test_research_agent_uses_shared_question_and_retrieval_components(monkeypatch):
    calls = {}

    class DummyIntent:
        def __init__(self):
            self.target_metrics = ["revenue"]
            self.target_entities = []
            self.target_years = ["2025"]
            self.is_causal = False
            self.requires_ranking = False
            self.requires_calculation = False
            self.target_company = "ABB"
            self.original_question = "Why did ABB revenue increase?"
            self.intent_type = type("T", (), {"value": "financial_metric"})()

    class DummyAnalyzer:
        @staticmethod
        def analyze(question, target_company=None):
            calls["analyze"] = question
            return DummyIntent()

    class DummyRetrievalService:
        def __init__(self, collection):
            self.collection = collection

        def retrieve_for_question(self, question, analysis_id=None, document_id=None, company_name=None, top_k=5):
            calls["retrieval"] = question
            return [type("R", (), {"chunk_id": "r1", "text": "ABB revenue increased 14% to $15.3 billion.", "metadata": {"company_name": "ABB", "section_title": "Management Discussion and Analysis", "source_file": "abb_2025.txt", "chunk_id": "r1"}, "relevance_score": 0.9, "retrieval_method": "semantic"})()]

    monkeypatch.setattr(research_agent_module, "SharedQuestionIntentAnalyzer", DummyAnalyzer)
    monkeypatch.setattr(research_agent_module, "EvidenceRetrievalService", DummyRetrievalService)

    mock_collection = MockChromaIsolationCollection([
        {
            "id": "r1",
            "document": "ABB revenue increased 14% to $15.3 billion.",
            "metadata": {
                "company_name": "ABB",
                "analysis_id": "session-dummy",
                "section_title": "Management Discussion and Analysis",
                "source_file": "abb_2025.txt",
                "chunk_id": "r1",
            },
        }
    ])

    agent = ResearchAgent(mock_collection)
    agent.answer("Why did ABB revenue increase?", company="ABB", analysis_id="session-dummy")

    assert calls.get("analyze") == "Why did ABB revenue increase?"
    assert calls.get("retrieval") == "Why did ABB revenue increase?"


def test_research_agent_keeps_supported_metric_value_and_rejects_unsupported_metric_candidate():
    collection = MockChromaIsolationCollection([
        {
            "id": "chunk-supported",
            "document": "Revenue increased to $500 million.",
            "metadata": {
                "company_name": "Aster Corp",
                "analysis_id": "session-support-1",
                "section_title": "Income Statement",
                "source_file": "aster_2025.txt",
                "chunk_id": "chunk-supported",
            },
        }
    ])

    def mock_llm(prompt: str) -> str:
        return "Revenue was $187 million. Revenue increased to $500 million."

    answer = ResearchAgent(collection, llm_generate=mock_llm).answer("What was revenue?", company="Aster Corp", analysis_id="session-support-1")

    assert "$187 million" not in answer.final_answer.lower()
    assert "$500 million" in answer.final_answer.lower()


def test_research_agent_rejects_unsupported_currency_metric_even_when_supported_euro_value_exists():
    collection = MockChromaIsolationCollection([
        {
            "id": "chunk-euro",
            "document": "Revenue was €500 million.",
            "metadata": {
                "company_name": "Aster Corp",
                "analysis_id": "session-euro-1",
                "section_title": "Income Statement",
                "source_file": "aster_2025.txt",
                "chunk_id": "chunk-euro",
            },
        }
    ])

    def mock_llm(prompt: str) -> str:
        return "Revenue was $187 million. Revenue was €500 million."

    answer = ResearchAgent(collection, llm_generate=mock_llm).answer("What was revenue?", company="Aster Corp", analysis_id="session-euro-1")

    assert "$187 million" not in answer.final_answer.lower()
    assert "€500 million" in answer.final_answer.lower()


def test_research_agent_uses_only_numbers_supported_by_selected_evidence():
    collection = MockChromaIsolationCollection([
        {
            "id": "chunk-relevant",
            "document": "Revenue increased to $500 million.",
            "metadata": {
                "company_name": "Aster Corp",
                "analysis_id": "session-supported-multi",
                "section_title": "Income Statement",
                "source_file": "aster_2025.txt",
                "chunk_id": "chunk-relevant",
            },
        },
        {
            "id": "chunk-unrelated",
            "document": "Operating cash flow was $1 million.",
            "metadata": {
                "company_name": "Aster Corp",
                "analysis_id": "session-supported-multi",
                "section_title": "Cash Flow Statement",
                "source_file": "aster_2025.txt",
                "chunk_id": "chunk-unrelated",
            },
        },
    ])

    def mock_llm(prompt: str) -> str:
        return "Revenue was $500 million. Operating cash flow was $1 million."

    answer = ResearchAgent(collection, llm_generate=mock_llm).answer("What was revenue?", company="Aster Corp", analysis_id="session-supported-multi")

    assert "$500 million" in answer.final_answer.lower()
    assert "$1 million" not in answer.final_answer.lower()


def test_research_agent_can_return_narrative_without_inventing_metric_when_no_metric_evidence_is_present():
    collection = MockChromaIsolationCollection([
        {
            "id": "chunk-narrative",
            "document": "The company improved revenue resilience and expanded its market reach.",
            "metadata": {
                "company_name": "Nova Systems",
                "analysis_id": "session-narrative",
                "section_title": "Management Discussion and Analysis",
                "source_file": "nova_2025.txt",
                "chunk_id": "chunk-narrative",
            },
        }
    ])

    def mock_llm(prompt: str) -> str:
        return "Revenue was $187 million. The company improved revenue resilience and expanded its market reach."

    answer = ResearchAgent(collection, llm_generate=mock_llm).answer("What was revenue?", company="Nova Systems", analysis_id="session-narrative")

    assert "$187 million" not in answer.final_answer.lower()
    assert "revenue resilience" in answer.final_answer.lower()


def test_research_agent_rejects_unsupported_metrics_for_arbitrary_company_values():
    collection = MockChromaIsolationCollection([
        {
            "id": "chunk-arbitrary",
            "document": "Revenue was £75.2 million.",
            "metadata": {
                "company_name": "Northwind Ltd.",
                "analysis_id": "session-arbitrary",
                "section_title": "Income Statement",
                "source_file": "northwind_2025.txt",
                "chunk_id": "chunk-arbitrary",
            },
        }
    ])

    def mock_llm(prompt: str) -> str:
        return "Revenue was $12.4 million. Revenue was £75.2 million."

    answer = ResearchAgent(collection, llm_generate=mock_llm).answer("What was revenue?", company="Northwind Ltd.", analysis_id="session-arbitrary")

    assert "$12.4 million" not in answer.final_answer.lower()
    assert "£75.2 million" in answer.final_answer.lower()


def test_research_agent_preserves_provenance_when_supported_metric_is_retained():
    collection = MockChromaIsolationCollection([
        {
            "id": "chunk-provenance",
            "document": "Revenue increased to $500 million.",
            "metadata": {
                "company_name": "Aster Corp",
                "analysis_id": "session-provenance",
                "section_title": "Income Statement",
                "source_file": "aster_2025.txt",
                "page_number": 8,
                "report_year": 2025,
                "chunk_id": "chunk-provenance",
            },
        }
    ])

    def mock_llm(prompt: str) -> str:
        return "Revenue was $500 million."

    answer = ResearchAgent(collection, llm_generate=mock_llm).answer("What was revenue?", company="Aster Corp", analysis_id="session-provenance")

    assert "$500 million" in answer.final_answer.lower()
    assert answer.steps[0].citations[0].source_file == "aster_2025.txt"
    assert answer.steps[0].citations[0].page == 8
    assert answer.steps[0].citations[0].chunk_id == "chunk-provenance"


def test_research_agent_prefers_relevant_financial_development_over_generic_accounting_note():
    collection = MockChromaIsolationCollection([
        {
            "id": "generic-accounting",
            "document": "Accounting policy note and risk indicators describe how revenue is recognized under the company accounting framework.",
            "metadata": {
                "company_name": "Apex Group",
                "analysis_id": "session-rank-dev",
                "section_title": "Accounting Notes and Risk Indicators",
                "source_file": "apex_2025.txt",
                "chunk_id": "generic-accounting",
            },
        },
        {
            "id": "financial-development",
            "document": "Revenue increased 14% to $15.3 billion driven by strong demand, and operating income improved to $2.1 billion.",
            "metadata": {
                "company_name": "Apex Group",
                "analysis_id": "session-rank-dev",
                "section_title": "Management Discussion and Analysis",
                "source_file": "apex_2025.txt",
                "chunk_id": "financial-development",
            },
        },
    ])

    answer = ResearchAgent(collection).answer(
        "What are the major financial developments and risks in this report?",
        company="Apex Group",
        analysis_id="session-rank-dev",
    )

    top_snippet = answer.steps[0].citations[0].snippet
    assert "Revenue increased" in top_snippet
    assert "Accounting policy note" not in top_snippet


def test_research_agent_prefers_risk_evidence_over_unrelated_accounting_note():
    collection = MockChromaIsolationCollection([
        {
            "id": "generic-accounting-risk",
            "document": "Accounting policy note explains the company accounting framework and general disclosure controls.",
            "metadata": {
                "company_name": "Bluebird Ltd.",
                "analysis_id": "session-rank-risk",
                "section_title": "Accounting Notes and Risk Indicators",
                "source_file": "bluebird_2025.txt",
                "chunk_id": "generic-accounting-risk",
            },
        },
        {
            "id": "real-risk",
            "document": "Inflation and supply chain pressures increased margin risk and reduced operating leverage across the group.",
            "metadata": {
                "company_name": "Bluebird Ltd.",
                "analysis_id": "session-rank-risk",
                "section_title": "Risk Factors",
                "source_file": "bluebird_2025.txt",
                "chunk_id": "real-risk",
            },
        },
    ])

    answer = ResearchAgent(collection).answer(
        "What are the major risks?",
        company="Bluebird Ltd.",
        analysis_id="session-rank-risk",
    )

    top_snippet = answer.steps[0].citations[0].snippet
    assert "Inflation and supply chain" in top_snippet
    assert "Accounting policy note" not in top_snippet


def test_research_agent_prefers_question_year_when_ranked_against_older_evidence():
    collection = MockChromaIsolationCollection([
        {
            "id": "older-year",
            "document": "Revenue was $30 million in 2024 and the company improved operating performance.",
            "metadata": {
                "company_name": "Harbor Co",
                "analysis_id": "session-rank-year",
                "section_title": "Results of Operations",
                "source_file": "harbor_2024.txt",
                "page_number": 7,
                "report_year": 2024,
                "chunk_id": "older-year",
            },
        },
        {
            "id": "current-year",
            "document": "Revenue was $42 million in 2025 and operating income improved materially.",
            "metadata": {
                "company_name": "Harbor Co",
                "analysis_id": "session-rank-year",
                "section_title": "Management Discussion and Analysis",
                "source_file": "harbor_2025.txt",
                "page_number": 9,
                "report_year": 2025,
                "chunk_id": "current-year",
            },
        },
    ])

    answer = ResearchAgent(collection).answer(
        "What happened to revenue in 2025?",
        company="Harbor Co",
        analysis_id="session-rank-year",
    )

    assert "2025" in answer.steps[0].citations[0].snippet
    assert "2024" not in answer.steps[0].citations[0].snippet


def test_research_agent_does_not_invent_section_labels_when_metadata_is_missing():
    collection = MockChromaIsolationCollection([
        {
            "id": "no-section",
            "document": "Revenue increased 14% to $15.3 billion and operating income improved materially.",
            "metadata": {
                "company_name": "Northstar Inc.",
                "analysis_id": "session-no-section",
                "source_file": "northstar_2025.txt",
                "chunk_id": "no-section",
            },
        }
    ])

    answer = ResearchAgent(collection).answer(
        "What happened to revenue?",
        company="Northstar Inc.",
        analysis_id="session-no-section",
    )

    section_names = {citation.section for citation in answer.all_citations()}
    assert "Unspecified section" in section_names
    assert "Financial Overview" not in section_names


def test_research_agent_keeps_metric_guard_for_unrelated_numbers_during_ranking():
    collection = MockChromaIsolationCollection([
        {
            "id": "generic-irrelevant-number",
            "document": "Accounting note references a non-operating value of $187 million in a historical footnote.",
            "metadata": {
                "company_name": "Pioneer Works",
                "analysis_id": "session-protect-metric",
                "section_title": "Accounting Notes",
                "source_file": "pioneer_2025.txt",
                "chunk_id": "generic-irrelevant-number",
            },
        },
        {
            "id": "relevant-revenue",
            "document": "Revenue increased to $500 million and the company posted stronger performance in the period.",
            "metadata": {
                "company_name": "Pioneer Works",
                "analysis_id": "session-protect-metric",
                "section_title": "Management Discussion and Analysis",
                "source_file": "pioneer_2025.txt",
                "chunk_id": "relevant-revenue",
            },
        },
    ])

    answer = ResearchAgent(collection).answer(
        "What was revenue?",
        company="Pioneer Works",
        analysis_id="session-protect-metric",
    )

    assert "$500 million" in answer.final_answer.lower()
    assert "$187 million" not in answer.final_answer.lower()
