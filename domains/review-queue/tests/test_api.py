from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "review-queue"}


def test_enqueue_list_and_decide_flow():
    with TestClient(app) as client:
        enqueue_response = client.post(
            "/enqueue",
            json={
                "payment_id": "pay-1",
                "entity_id": "ENT-1",
                "entity_name": "Acme Trading LLC",
                "score": 0.64,
                "country": "AE",
                "lists_flagged": ["EU_CONSOLIDATED"],
                "transfer_type": "OUTBOUND",
                "ubo_resolution_status": "PARTIAL",
            },
        )
        assert enqueue_response.status_code == 200
        item = enqueue_response.json()
        assert item["payment_id"] == "pay-1"
        assert item["high_priority"] is False

        queue_response = client.get("/queue")
        assert queue_response.status_code == 200
        items = queue_response.json()
        assert len(items) == 1
        assert items[0]["payment_id"] == "pay-1"

        decide_response = client.post(
            "/decide/pay-1",
            json={"decision": "CLEAR", "analyst_id": "analyst-1", "notes": "Cleared after review"},
        )
        assert decide_response.status_code == 200
        assert decide_response.json()["decision"] == "CLEAR"

        after_decide = client.get("/queue")
        assert after_decide.json() == []


def test_decide_unknown_payment_returns_404():
    with TestClient(app) as client:
        response = client.post("/decide/does-not-exist", json={"decision": "CLEAR", "analyst_id": "analyst-1"})
        assert response.status_code == 404
