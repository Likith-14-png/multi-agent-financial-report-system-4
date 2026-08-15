from app.services.retrieval_service import RetrievalService
from app.services.chroma_service import ChromaService


def test_missing_collection_raises_value_error():
    service = RetrievalService(chroma_service=ChromaService(persist_directory="./tmp_chroma"))
    try:
        service.retrieve("missing_collection", "Acme")
    except ValueError as exc:
        assert "does not exist" in str(exc)
