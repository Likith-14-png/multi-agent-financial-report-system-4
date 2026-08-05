import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from view_chromadb import summarize


class DummyCollection:
    name = "test_collection"

    def get(self, include):
        return {
            "ids": ["1"],
            "documents": ["sample document"],
            "metadatas": [
                {
                    "doc_hash": "abc123",
                    "company_name": "Acme",
                    "report_type": "10-K",
                    "financial_year": 2024,
                }
            ],
            "embeddings": np.array([[0.1, 0.2, 0.3]], dtype=float),
        }


def test_summarize_handles_numpy_embeddings(capsys):
    summarize(DummyCollection())

    captured = capsys.readouterr()
    assert "Collection: test_collection" in captured.out
    assert "Chunks: 1" in captured.out
