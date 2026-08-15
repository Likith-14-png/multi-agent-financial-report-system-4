from app.services.retrieval_service import RetrievalService
from app.services.chroma_service import ChromaService


def test_retrieval_requires_collection_and_company(monkeypatch):
    service = RetrievalService(chroma_service=ChromaService(persist_directory="./tmp_chroma"))
    try:
        service.retrieve("", "Acme")
    except ValueError as exc:
        assert "Collection name is required" in str(exc)

    try:
        service.retrieve("demo", "")
    except ValueError as exc:
        assert "Company name is required" in str(exc)
