"""Integration tests for regulatory-engine /get-requirements (CC-04)."""
from fastapi.testclient import TestClient

from app.main import app
from app.models import PolicyFlag

client = TestClient(app)


def _get_requirements(**overrides) -> dict:
    payload = {
        "originator_country": "GB",
        "beneficiary_country": "AE",
        "amount_usd": 50000,
        "entity_type": "business",
        "asset_type": "fiat",
        "chain": None,
        "token": None,
    }
    payload.update(overrides)
    resp = client.post("/get-requirements", json=payload)
    assert resp.status_code == 200
    return resp.json()


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "regulatory-engine"


def test_uk_to_iran_always_auto_blocks_regardless_of_score() -> None:
    result = _get_requirements(originator_country="GB", beneficiary_country="IR")
    assert result["auto_block"] is True
    assert result["country_risk_tiers"]["beneficiary"]["tier"] == "BLACK"
    assert result["country_sanctions_program"] is not None


def test_eu_tron_usdt_always_carries_mica_compliance_risk() -> None:
    result = _get_requirements(
        originator_country="DE",
        beneficiary_country="AE",
        asset_type="stablecoin",
        chain="tron",
        token="USDT",
    )
    assert PolicyFlag.MICA_COMPLIANCE_RISK.value in result["policy_flags"]
    assert result["mica_compliance_risk"] is True


def test_uk_tron_usdt_always_carries_tron_eu_corridor_review() -> None:
    result = _get_requirements(
        originator_country="GB",
        beneficiary_country="AE",
        asset_type="stablecoin",
        chain="tron",
        token="USDT",
    )
    assert PolicyFlag.TRON_EU_CORRIDOR_REVIEW.value in result["policy_flags"]
    assert result["tron_eu_corridor_review"] is True


def test_usdc_on_eu_corridor_carries_neither_flag() -> None:
    result = _get_requirements(
        originator_country="DE",
        beneficiary_country="AE",
        asset_type="stablecoin",
        chain="ethereum",
        token="USDC",
    )
    assert PolicyFlag.MICA_COMPLIANCE_RISK.value not in result["policy_flags"]
    assert PolicyFlag.TRON_EU_CORRIDOR_REVIEW.value not in result["policy_flags"]
    assert result["mica_compliance_risk"] is False
    assert result["tron_eu_corridor_review"] is False


def test_ofac_applies_for_us_corridor_with_required_lists() -> None:
    result = _get_requirements(originator_country="US", beneficiary_country="DE")
    assert "OFAC_SDN" in result["required_lists"]
    assert "OFACRule" in result["applicable_rules"]
    # OFAC near-zero tolerance -> strictest thresholds win
    assert result["thresholds"]["review"] <= 0.30


def test_union_of_rules_for_multi_jurisdiction_corridor() -> None:
    result = _get_requirements(originator_country="GB", beneficiary_country="AE")
    assert "FCARule" in result["applicable_rules"]
    assert "DFSARule" in result["applicable_rules"]
    assert "UK_SANCTIONS_LIST" in result["required_lists"]
    assert "UAE_LOCAL_TERRORIST_LIST" in result["required_lists"]


def test_fatf_fallback_when_no_specific_rule_matches() -> None:
    result = _get_requirements(originator_country="JP", beneficiary_country="BR")
    assert result["applicable_rules"] == ["FATFBaseRule"]
    assert "UN_CONSOLIDATED" in result["required_lists"]


def test_travel_rule_required_for_eu_stablecoin_regardless_of_amount() -> None:
    result = _get_requirements(
        originator_country="DE",
        beneficiary_country="FR",
        asset_type="stablecoin",
        amount_usd=1.0,
        chain="ethereum",
        token="USDC",
    )
    assert result["travel_rule_required"] is True
