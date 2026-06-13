"""Tests for audit-trail (write-once, wallet-indexed audit log, Section 11.4)."""
from fastapi.testclient import TestClient

from app.main import app


def _verdict(**overrides) -> dict:
    base = {
        "verdict": "REVIEW",
        "track": "B:risk",
        "cause": "elevated composite score",
        "composite_score": 0.62,
        "priority": 0.62,
        "ubo_resolution_status": "FULL",
        "policy_flags": {"mica_compliance_risk": False, "tron_eu_corridor_review": False, "pep_flag": False},
        "list_version_ofac": "2026-06-12",
        "list_version_ofsi": "2026-06-11",
        "algorithm_version": "v1.2",
        "screened_at": "2026-06-13T10:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_health() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "audit-trail"


def test_log_fiat_payment_with_no_wallets_creates_one_record() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/log",
            json={
                "payment_id": "PAY-001",
                "verdict": _verdict(),
                "payment": {"originator_country": "GB", "beneficiary_country": "AE"},
            },
        )
        assert resp.status_code == 200
        records = resp.json()["records"]
        assert len(records) == 1
        assert records[0]["wallet_address"] is None
        assert records[0]["verdict"] == "REVIEW"
        assert records[0]["retention_until"] is not None


def test_log_crypto_payment_creates_record_per_wallet() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/log",
            json={
                "payment_id": "PAY-002",
                "verdict": _verdict(verdict="MATCH"),
                "payment": {
                    "originator_country": "US",
                    "beneficiary_country": "DE",
                    "originator_wallet": "TAAA111",
                    "beneficiary_wallet": "TBBB222",
                },
            },
        )
        assert resp.status_code == 200
        records = resp.json()["records"]
        wallets = {r["wallet_address"] for r in records}
        assert wallets == {"TAAA111", "TBBB222"}
        assert all(r["verdict"] == "MATCH" for r in records)


def test_log_with_explicit_wallet_address_from_crypto_screener() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/log",
            json={
                "payment_id": "PAY-003",
                "wallet_address": "TCCC333",
                "entity_id": "ENT-001",
                "verdict": _verdict(verdict="NO_MATCH"),
            },
        )
        assert resp.status_code == 200
        records = resp.json()["records"]
        assert len(records) == 1
        assert records[0]["wallet_address"] == "TCCC333"
        assert records[0]["entity_id"] == "ENT-001"


def test_export_payment_returns_all_records() -> None:
    with TestClient(app) as client:
        client.post(
            "/log",
            json={
                "payment_id": "PAY-EXPORT",
                "verdict": _verdict(),
                "payment": {
                    "originator_country": "US",
                    "beneficiary_country": "DE",
                    "originator_wallet": "TEXPORT1",
                    "beneficiary_wallet": "TEXPORT2",
                },
            },
        )
        resp = client.get("/export/PAY-EXPORT")
        assert resp.status_code == 200
        body = resp.json()
        assert body["payment_id"] == "PAY-EXPORT"
        assert len(body["records"]) == 2


def test_export_unknown_payment_returns_404() -> None:
    with TestClient(app) as client:
        resp = client.get("/export/UNKNOWN")
        assert resp.status_code == 404


def test_wallet_history_endpoint() -> None:
    with TestClient(app) as client:
        client.post(
            "/log",
            json={
                "payment_id": "PAY-WALLET",
                "verdict": _verdict(),
                "payment": {
                    "originator_country": "US",
                    "beneficiary_country": "DE",
                    "originator_wallet": "TWALLET1",
                },
            },
        )
        resp = client.get("/wallet/TWALLET1")
        assert resp.status_code == 200
        records = resp.json()["records"]
        assert len(records) == 1
        assert records[0]["wallet_address"] == "TWALLET1"


def test_eu_high_risk_payment_gets_ten_year_retention() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/log",
            json={
                "payment_id": "PAY-EU-HIGHRISK",
                "verdict": _verdict(
                    policy_flags={"mica_compliance_risk": True, "tron_eu_corridor_review": False, "pep_flag": False}
                ),
                "payment": {"originator_country": "DE", "beneficiary_country": "AE"},
            },
        )
        record = resp.json()["records"][0]
        screened = record["screening_timestamp"]
        retain_until = record["retention_until"]
        assert screened[:4] == "2026"
        assert retain_until[:4] == "2036"  # 10-year retention
