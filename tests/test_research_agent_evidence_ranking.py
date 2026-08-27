from typing import Any, Dict, List

from research_agent import ResearchAgent


class RankingCollection:
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records

    def query(self, query_texts, n_results=4, where=None):
        records = self.records
        if where:
            records = [record for record in records if all(record["metadata"].get(k) == v for k, v in where.items())]
        return {
            "ids": [[record["id"] for record in records[:n_results]]],
            "documents": [[record["document"] for record in records[:n_results]]],
            "metadatas": [[record["metadata"] for record in records[:n_results]]],
            "distances": [[0.1 for _ in records[:n_results]]],
        }

    def get(self, include=None):
        return {"metadatas": [record["metadata"] for record in self.records]}


def _record(chunk_id: str, document: str, section: str) -> Dict[str, Any]:
    return {
        "id": chunk_id,
        "document": document,
        "metadata": {
            "company_name": "Acme Corp",
            "section_title": section,
            "source_file": "acme-report.pdf",
            "chunk_id": chunk_id,
        },
    }


def test_primary_revenue_statement_beats_generic_accounting_note():
    collection = RankingCollection([
        _record("notes", "Accounting policies describe revenue recognition.", "Accounting Notes"),
        _record("income", "Revenue increased from $100 million in FY2024 to $120 million in FY2025.", "Consolidated Income Statement"),
    ])

    answer = ResearchAgent(collection).answer("Why did revenue increase?", company="Acme Corp")

    assert answer.steps[0].citations[0].chunk_id == "income"
    assert "$100 million" in answer.steps[0].citations[0].snippet
    assert "$120 million" in answer.steps[0].citations[0].snippet


def test_mda_driver_beats_generic_risk_factor_and_fx_disclosure():
    collection = RankingCollection([
        _record("risk", "Foreign currency exchange rates are a market risk factor.", "Risk Factors"),
        _record("mda", "Revenue increased 14% primarily due to higher customer demand.", "Management Discussion and Analysis"),
    ])

    answer = ResearchAgent(collection).answer("Why did revenue increase?", company="Acme Corp")

    assert answer.steps[0].citations[0].chunk_id == "mda"
    assert "primarily due to higher customer demand" in answer.steps[0].citations[0].snippet


def test_fx_is_not_ranked_as_revenue_cause_without_explicit_connection():
    collection = RankingCollection([
        _record("fx", "Foreign currency volatility creates exchange-rate risk.", "Risk Indicators"),
        _record("revenue", "Revenue increased from $100 million to $120 million.", "Income Statement"),
    ])

    answer = ResearchAgent(collection).answer("Why did revenue increase?", company="Acme Corp")

    assert answer.steps[0].citations[0].chunk_id == "revenue"


def test_metric_and_driver_chunks_keep_individual_provenance():
    collection = RankingCollection([
        _record("driver", "Management attributed revenue growth to increased demand in Europe.", "Management Discussion and Analysis"),
        _record("metric", "Revenue rose from $100 million in FY2024 to $120 million in FY2025.", "Income Statement"),
    ])

    answer = ResearchAgent(collection).answer("Why did revenue increase?", company="Acme Corp")
    citations = {citation.chunk_id: citation for citation in answer.steps[0].citations}

    assert citations["metric"].source_file == "acme-report.pdf"
    assert citations["driver"].source_file == "acme-report.pdf"
    assert citations["metric"].snippet != citations["driver"].snippet


def test_generic_revenue_mention_is_not_ranked_above_metric_evidence():
    collection = RankingCollection([
        _record("generic", "Revenue is discussed in the accounting note.", "Accounting Notes"),
        _record("metric", "Revenue increased from $100 million to $120 million.", "Statement of Operations"),
    ])

    answer = ResearchAgent(collection).answer("Why did revenue increase?", company="Acme Corp")

    assert answer.steps[0].citations[0].chunk_id == "metric"


def test_metric_movement_without_cause_is_explicitly_reported_as_insufficient():
    collection = RankingCollection([
        _record("metric", "Revenue increased from $100 million to $120 million.", "Income Statement"),
        _record("fx", "Foreign currency balances are disclosed as a market risk.", "Accounting Notes"),
    ])

    answer = ResearchAgent(collection).answer("Why did revenue increase?", company="Acme Corp")

    assert "does not explicitly identify its cause" in answer.final_answer
    assert "operational mix changes" not in answer.final_answer
    assert "foreign currency balances" not in answer.final_answer.lower()


def test_causal_answer_does_not_dump_complete_raw_chunks():
    long_text = "Revenue increased from $100 million to $120 million. " + ("Unrelated disclosure text. " * 80)
    collection = RankingCollection([_record("metric", long_text, "Income Statement")])

    answer = ResearchAgent(collection).answer("Why did revenue increase?", company="Acme Corp")

    assert len(answer.final_answer) < len(long_text)
    assert answer.final_answer.count("Unrelated disclosure text") == 0