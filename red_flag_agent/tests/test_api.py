from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_invalid_request_payload_rejected():
    response = client.post("/redflag/analyze", json={"company": "", "collection": ""})
    assert response.status_code == 422
