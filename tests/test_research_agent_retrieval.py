from __future__ import annotations

from typing import Any, Dict, List

from research_agent import ResearchAgent


class FakeQueryCollection:
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records

    def query(self, query_texts: List[str], n_results: int = 4, where: Dict[str, Any] | None = None):
        if where is not None:
            filtered = [
                record for record in self.records
                if all(record.get(k) == v for k, v in where.items())
            ]
            if not filtered:
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            return {
                "ids": [[record["id"] for record in filtered[:n_results]]],
                "documents": [[record["document"] for record in filtered[:n_results]]],
                "metadatas": [[record["metadata"] for record in filtered[:n_results]]],
                "distances": [[0.1 for _ in filtered[:n_results]]],
            }
        return {
            "ids": [[record["id"] for record in self.records[:n_results]]],
            "documents": [[record["document"] for record in self.records[:n_results]]],
            "metadatas": [[record["metadata"] for record in self.records[:n_results]]],
            "distances": [[0.1 for _ in self.records[:n_results]]],
        }

    def get(self, include=None):
        return {"metadatas": [record["metadata"] for record in self.records]}


def test_research_agent_uses_company_name_metadata_when_present():
    collection = FakeQueryCollection([
        {
            "id": "1",
            "document": "Nova Tech Systems Ltd. reported revenue growth and elevated debt risk.",
            "metadata": {"company_name": "Nova Tech Systems Ltd.", "section": "MD&A", "source": "mock_financial_report_2024_2025.pdf", "chunk_id": "abc-1"},
        }
    ])
    agent = ResearchAgent(collection)
    answer = agent.answer("What are the financial trends and risks?", top_k=4, company="Nova Tech Systems Ltd.")

    assert answer.steps[0].citations
    assert answer.steps[0].citations[0].company == "Nova Tech Systems Ltd."
    assert answer.steps[0].citations[0].source_file == "mock_financial_report_2024_2025.pdf"
    assert answer.steps[0].citations[0].chunk_id == "abc-1"


def test_research_agent_supports_legacy_company_metadata():
    collection = FakeQueryCollection([
        {
            "id": "2",
            "document": "Legacy company metadata is still supported.",
            "metadata": {"company": "Nova Tech Systems Ltd.", "doc_type": "Annual Report", "section": "Balance Sheet", "source_file": "legacy.pdf", "chunk_id": "legacy-1"},
        }
    ])
    agent = ResearchAgent(collection)
    answer = agent.answer("Tell me about the company risk profile.", top_k=4, company=" Nova Tech Systems Ltd. ")

    assert answer.steps[0].citations
    assert answer.steps[0].citations[0].company == "Nova Tech Systems Ltd."
    assert answer.steps[0].citations[0].source_file == "legacy.pdf"
    assert answer.steps[0].citations[0].chunk_id == "legacy-1"


def test_research_agent_normalizes_company_name_whitespace_and_case():
    collection = FakeQueryCollection([
        {
            "id": "3",
            "document": "Whitespace and case should normalize to the same company.",
            "metadata": {"company_name": " nova tech systems ltd. ", "section": "Risk Factors", "source": "norm.pdf", "chunk_id": "norm-1"},
        }
    ])
    agent = ResearchAgent(collection)
    answer = agent.answer("What are the risks?", top_k=4, company="Nova Tech Systems Ltd.")

    assert answer.steps[0].citations
    assert answer.steps[0].citations[0].company == " nova tech systems ltd. "


def test_research_agent_falls_back_after_zero_filtered_query_results():
    collection = FakeQueryCollection([
        {
            "id": "4",
            "document": "Fallback after zero filtered match.",
            "metadata": {"company_name": "Nova Tech Systems Ltd.", "section": "Risk Factors", "source": "fallback.pdf", "chunk_id": "fallback-1"},
        }
    ])

    class ZeroFirstCollection(FakeQueryCollection):
        def query(self, query_texts, n_results=4, where=None):
            if where is not None:
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            return super().query(query_texts, n_results=n_results, where=where)

    agent = ResearchAgent(ZeroFirstCollection(collection.records))
    answer = agent.answer("What are the main risks?", top_k=4, company="Nova Tech Systems Ltd.")

    assert answer.steps[0].citations
    assert answer.steps[0].citations[0].source_file == "fallback.pdf"


def test_research_agent_uses_unfiltered_query_when_no_company_filter_matches():
    collection = FakeQueryCollection([
        {
            "id": "5",
            "document": "This is a general company document.",
            "metadata": {"company_name": "Nova Tech Systems Ltd.", "section": "Legal", "source": "unfiltered.pdf", "chunk_id": "unfiltered-1"},
        }
    ])

    class NoMatchCompanyFilterCollection(FakeQueryCollection):
        def query(self, query_texts, n_results=4, where=None):
            if where == {"company_name": "Nova Tech Systems Ltd."}:
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            if where == {"company": "Nova Tech Systems Ltd."}:
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            return super().query(query_texts, n_results=n_results, where=where)

    agent = ResearchAgent(NoMatchCompanyFilterCollection(collection.records))
    answer = agent.answer("What are the trends?", top_k=4, company="Nova Tech Systems Ltd.")

    assert answer.steps[0].citations
    assert answer.steps[0].citations[0].chunk_id == "unfiltered-1"


def test_research_agent_preserves_citation_chunk_and_source_fields():
    collection = FakeQueryCollection([
        {
            "id": "6",
            "document": "Preserve chunk ids and file names.",
            "metadata": {"company_name": "Nova Tech Systems Ltd.", "section_title": "Liquidity", "source": "preserve.pdf", "chunk_id": "chunk-678"},
        }
    ])
    agent = ResearchAgent(collection)
    answer = agent.answer("What is the liquidity risk?", top_k=4, company="Nova Tech Systems Ltd.")

    citation = answer.steps[0].citations[0]
    assert citation.chunk_id == "chunk-678"
    assert citation.source_file == "preserve.pdf"


def test_research_agent_infers_section_from_heading_when_metadata_missing():
    collection = FakeQueryCollection([
        {
            "id": "7",
            "document": "1. Management Discussion and Analysis\nRevenue increased to $18.4 billion.",
            "metadata": {"company_name": "Nova Tech Systems Ltd.", "section": "Unknown", "source": "mdna.pdf", "chunk_id": "chunk-mdna"},
        }
    ])
    agent = ResearchAgent(collection)
    answer = agent.answer("What are the key trends in management discussion and analysis?", top_k=4, company="Nova Tech Systems Ltd.")

    citation = answer.steps[0].citations[0]
    assert citation.section == "Management Discussion and Analysis"


def test_research_agent_skips_note_only_chunks_without_section_heading():
    collection = FakeQueryCollection([
        {
            "id": "8",
            "document": "Note: This is a fictional mock report created for testing the multi-agent financial report system. All company names, figures, and statements are synthetic.",
            "metadata": {"company_name": "Nova Tech Systems Ltd.", "section": "Unknown", "source": "mock.pdf", "chunk_id": "note-chunk"},
        },
        {
            "id": "9",
            "document": "1. Management Discussion and Analysis\nRevenue increased to $18.4 billion.",
            "metadata": {"company_name": "Nova Tech Systems Ltd.", "section": "Unknown", "source": "mock.pdf", "chunk_id": "chunk-mdna"},
        },
    ])
    agent = ResearchAgent(collection)
    answer = agent.answer("What are the key trends in management discussion and analysis?", top_k=4, company="Nova Tech Systems Ltd.")

    assert all(citation.section != "Unknown" for citation in answer.steps[0].citations)
    assert any(citation.chunk_id == "chunk-mdna" for citation in answer.steps[0].citations)


def test_research_agent_handles_empty_collection_without_error():
    collection = FakeQueryCollection([])
    agent = ResearchAgent(collection)
    answer = agent.answer("Any evidence?", top_k=4, company="Nova Tech Systems Ltd.")

    assert answer.steps[0].citations == []
    assert "No indexed documents contain evidence" in answer.steps[0].findings


def test_research_agent_mock_behavior_still_works():
    from fake_chroma_collection import FakeChromaCollection

    collection = FakeChromaCollection()
    collection.add_document("orion_steelworks.txt", company="Orion Steelworks Ltd", doc_type="Annual Report", period="FY2024")
    agent = ResearchAgent(collection)
    answer = agent.answer("Which company has a risk profile?", top_k=4, company="Orion Steelworks Ltd")

    assert answer.steps
    assert any(c.company == "Orion Steelworks Ltd" for c in answer.all_citations())
