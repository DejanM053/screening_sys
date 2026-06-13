"""API tests for GET /explanation/{payment_id} and POST /generate-sar-draft (CC-06)."""
from fastapi.testclient import TestClient

from app.main import app
from app.models.explanation import ExplanationRecord, ScoreNode


def _record(payment_id: str = "pay-1") -> ExplanationRecord:
    tree = ScoreNode(
        id="root",
        label="Composite Risk Score",
        score=0.6,
        children=[
            ScoreNode(id="identity_match", label="Identity Match Signal", score=0.4, weight=0.25),
        ],
    )
    return ExplanationRecord(
        payment_id=payment_id,
        verdict="REVIEW",
        track="B:risk",
        composite_score=0.6,
        tree=tree,
        network_context=None,
        payment={"payment_id": payment_id, "amount_usd": 1000.0},
        screened_at="2026-06-13T00:00:00",
    )


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "screening-api"


async def test_get_explanation_not_found():
    with TestClient(app) as client:
        resp = client.get("/explanation/does-not-exist")
        assert resp.status_code == 404


async def test_get_explanation_returns_stored_record():
    with TestClient(app) as client:
        await app.state.explanation_store.put("pay-1", _record("pay-1"))

        resp = client.get("/explanation/pay-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["payment_id"] == "pay-1"
        assert body["verdict"] == "REVIEW"
        assert body["tree"]["id"] == "root"
        assert body["tree"]["children"][0]["id"] == "identity_match"


async def test_generate_sar_draft_not_found():
    with TestClient(app) as client:
        resp = client.post("/generate-sar-draft", json={"payment_id": "does-not-exist"})
        assert resp.status_code == 404


async def test_generate_sar_draft_llm_unavailable_returns_502():
    with TestClient(app) as client:
        await app.state.explanation_store.put("pay-2", _record("pay-2"))

        resp = client.post("/generate-sar-draft", json={"payment_id": "pay-2", "analyst_notes": "looks fine"})
        assert resp.status_code == 502
