"""Tests for crypto-screener — stablecoin/wallet compliance (Section 10, CC-05)."""
from fastapi.testclient import TestClient

from app.main import app


def _kyb_record(ubo_status: str = "FULL", entity_id: str = "ENT-001", onboarding_score: float = 0.1) -> dict:
    return {
        "entity_id": entity_id,
        "ubo_resolution_status": ubo_status,
        "onboarding_score": onboarding_score,
        "kyb_verified_at": "2026-01-01T00:00:00+00:00",
        "historical_flag_rate": 0.0,
    }


def test_health() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "crypto-screener"


def test_external_wallet_no_kyb_record_treated_as_external() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/screen-wallet",
            json={
                "address": "TEXTERNAL1",
                "chain": "tron",
                "stablecoin": "USDT",
                "amount_usd": 500,
                "counterparty_address": "TEXTERNAL2",
                "originator_country": "US",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kyb_verified"] is False
        assert body["is_internal"] is False
        assert body["ubo_status"] == "UNRESOLVED"
        assert body["hop_analysis"]["hop_score"] == 0.0  # no network access -> fails safe


def test_internal_kyb_pair_skips_attribution_and_uses_hop_depth_1() -> None:
    with TestClient(app) as client:
        client.post("/admin/kyb-registry/TINTERNAL1", json=_kyb_record(ubo_status="FULL", entity_id="ENT-A"))
        client.post("/admin/kyb-registry/TINTERNAL2", json=_kyb_record(ubo_status="PARTIAL", entity_id="ENT-B"))

        resp = client.post(
            "/screen-wallet",
            json={
                "address": "TINTERNAL1",
                "chain": "tron",
                "stablecoin": "USDT",
                "amount_usd": 500,
                "counterparty_address": "TINTERNAL2",
                "originator_country": "US",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kyb_verified"] is True
        assert body["is_internal"] is True
        assert body["entity_id"] == "ENT-A"
        assert body["ubo_status"] == "FULL"
        assert body["attribution"] is None


def test_unresolved_ubo_kyb_member_treated_as_external() -> None:
    with TestClient(app) as client:
        client.post("/admin/kyb-registry/TUNRESOLVED1", json=_kyb_record(ubo_status="UNRESOLVED", entity_id="ENT-C"))
        client.post("/admin/kyb-registry/TPARTNER1", json=_kyb_record(ubo_status="FULL", entity_id="ENT-D"))

        resp = client.post(
            "/screen-wallet",
            json={
                "address": "TUNRESOLVED1",
                "chain": "tron",
                "stablecoin": "USDT",
                "amount_usd": 500,
                "counterparty_address": "TPARTNER1",
                "originator_country": "US",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Per Section 10.3 fixed bug: UNRESOLVED UBO downgrades to full external treatment.
        assert body["kyb_verified"] is False
        assert body["is_internal"] is False
        assert body["ubo_status"] == "UNRESOLVED"


def test_ofac_wallet_match_returns_match_recommendation() -> None:
    with TestClient(app) as client:
        client.post("/admin/ofac-wallets", json=["TSANCTIONED1"])

        resp = client.post(
            "/screen-wallet",
            json={
                "address": "TSANCTIONED1",
                "chain": "tron",
                "stablecoin": "USDT",
                "amount_usd": 100,
                "originator_country": "US",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ofac_match"] is True
        assert body["ofac_score"] == 1.0
        assert body["recommended_verdict"] == "MATCH"


def test_mica_flag_for_usdt_eu_corridor() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/screen-wallet",
            json={
                "address": "0xEUUSDT1",
                "chain": "ethereum",
                "stablecoin": "USDT",
                "amount_usd": 100,
                "originator_country": "DE",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mica_flag"] is True
        assert body["tron_eu_corridor_flag"] is False


def test_usdc_on_eu_corridor_carries_no_mica_flag() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/screen-wallet",
            json={
                "address": "0xEUUSDC1",
                "chain": "ethereum",
                "stablecoin": "USDC",
                "amount_usd": 100,
                "originator_country": "DE",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mica_flag"] is False


def test_tron_eu_corridor_flag_for_gb_tron_usdt() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/screen-wallet",
            json={
                "address": "TGBUSDT1",
                "chain": "tron",
                "stablecoin": "USDT",
                "amount_usd": 100,
                "originator_country": "GB",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tron_eu_corridor_flag"] is True
        assert body["mica_flag"] is False  # GB not in EU_EEA_COUNTRIES; only the TRON policy flag applies


def test_travel_rule_required_for_eu_corridor_regardless_of_amount() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/screen-wallet",
            json={
                "address": "0xEUSMALL1",
                "chain": "ethereum",
                "stablecoin": "USDT",
                "amount_usd": 1,
                "originator_country": "DE",
                "beneficiary_country": "US",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["travel_rule"]["required"] is True
        assert body["travel_rule"]["threshold_usd"] == 0.0


def test_travel_rule_below_us_threshold_not_required() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/screen-wallet",
            json={
                "address": "0xUSSMALL1",
                "chain": "ethereum",
                "stablecoin": "USDT",
                "amount_usd": 100,
                "originator_country": "US",
                "beneficiary_country": "DE",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["travel_rule"]["required"] is False
        assert body["travel_rule"]["threshold_usd"] == 3000.0
