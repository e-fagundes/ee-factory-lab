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


def test_settings_exposes_ollama_status():
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert "ollama_enabled" in body
    assert "ollama_model" in body
    assert "ollama_status" in body
    assert "available" in body["ollama_status"]
