"""
Offline sanity test for ResearchAgent — runs without chromadb / sentence-
transformers installed, using FakeChromaCollection as a drop-in for a real
ChromaDB Collection. Run: python3 tests/test_research_agent_mock.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from research_agent import ResearchAgent
from tests.fake_chroma_collection import FakeChromaCollection

SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seed_docs")


def main():
    collection = FakeChromaCollection()
    collection.add_document(os.path.join(SEED_DIR, "orion_steelworks.txt"),
                             company="Orion Steelworks Ltd", doc_type="Annual Report", period="FY2024")
    collection.add_document(os.path.join(SEED_DIR, "vantage_retail.txt"),
                             company="Vantage Retail Corp", doc_type="Annual Report", period="FY2024")
    collection.add_document(os.path.join(SEED_DIR, "nimbus_cloud.txt"),
                             company="Nimbus Cloud Technologies Inc", doc_type="Annual Report", period="FY2024")
    print(f"Indexed {len(collection._ids)} chunks across "
          f"{len({m['company'] for m in collection._metas})} companies.\n")

    agent = ResearchAgent(collection)

    question = ("Which company has the highest debt-to-equity ratio, and does "
                "Nimbus Cloud Technologies have any going concern risk?")
    print("=" * 70)
    print("Q:", question)
    print("=" * 70)
    answer = agent.answer(question)
    print(answer.final_answer)

    print("\n" + "=" * 70)
    print("All distinct citations returned:")
    print("=" * 70)
    for c in answer.all_citations():
        print(" -", c)

    # sanity checks
    assert len(answer.steps) == 2, "expected the question to decompose into 2 sub-questions"
    assert all(s.citations for s in answer.steps), "expected every step to retrieve evidence"
    assert any("Nimbus" in c.company for c in answer.all_citations())
    print("\nAll sanity checks passed.")


if __name__ == "__main__":
    main()
