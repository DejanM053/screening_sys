from fastapi.testclient import TestClient

from app.main import app
from tests.test_explain import SAMPLE_TREE
from tests.test_sar import PAYMENT


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "llm-service"}


def test_explain_returns_fallback_explanation_when_ollama_unreachable():
    with TestClient(app) as client:
        resp = client.post(
            "/explain",
            json={
                "payment_id": "pay-1",
                "verdict": "REVIEW",
                "composite_score": 0.64,
                "tree": SAMPLE_TREE,
                "network_context": None,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["payment_id"] == "pay-1"
        assert "REVIEW" in body["explanation"]


def test_generate_sar_draft_returns_fallback_when_ollama_unreachable():
    with TestClient(app) as client:
        resp = client.post(
            "/generate-sar-draft",
            json={
                "payment_id": "pay-1",
                "verdict": "REVIEW",
                "composite_score": 0.64,
                "tree": SAMPLE_TREE,
                "payment": PAYMENT,
                "analyst_notes": "Escalated for senior review",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "SUBJECT INFORMATION" in body["draft"]
