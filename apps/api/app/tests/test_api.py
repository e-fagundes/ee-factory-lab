from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_domains_load():
    response = client.get("/api/v1/domains")
    assert response.status_code == 200
    assert "windows" in response.json()["domains"]
