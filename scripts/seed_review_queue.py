#!/usr/bin/env python3
"""
Seed the Redis review queue with realistic AML test cases.

Usage:
    python scripts/seed_review_queue.py [--queue http://localhost:8009]

Idempotent: re-running with same payment_id will update in place.
"""

import argparse
import asyncio
import sys
import httpx

CASES = [
    {
        "payment_id": "TXN-AE-001",
        "entity_name": "Al-Qadir Trading LLC",
        "entity_id": "TXN-AE-001",
        "score": 0.81,
        "country": "AE",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "policy_flags": ["pep_exposure", "high_risk_jurisdiction"],
        "network_risk_score": 0.62,
        "network_escalation_applied": True,
        "amount_usd": 847000,
        "track": "B:risk",
        "high_priority": True,
    },
    {
        "payment_id": "TXN-RU-002",
        "entity_name": "Meridian Finance Group",
        "entity_id": "TXN-RU-002",
        "score": 0.74,
        "country": "RU",
        "transfer_type": "INBOUND",
        "ubo_resolution_status": "PARTIAL",
        "policy_flags": ["sanctions_adjacent", "layering"],
        "network_risk_score": 0.55,
        "network_escalation_applied": False,
        "amount_usd": 2100000,
        "track": "B:risk",
        "high_priority": True,
    },
    {
        "payment_id": "TXN-CY-003",
        "entity_name": "Gulf Holdings International",
        "entity_id": "TXN-CY-003",
        "score": 0.69,
        "country": "CY",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "FULL",
        "policy_flags": ["shell_company_indicator"],
        "network_risk_score": 0.41,
        "network_escalation_applied": False,
        "amount_usd": 520000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-NG-004",
        "entity_name": "Lagos Capital Partners Ltd",
        "entity_id": "TXN-NG-004",
        "score": 0.78,
        "country": "NG",
        "transfer_type": "INBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "policy_flags": ["high_risk_jurisdiction", "cash_intensive_business"],
        "network_risk_score": 0.48,
        "network_escalation_applied": False,
        "amount_usd": 315000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-CH-005",
        "entity_name": "Helvetica Private Fund SPC",
        "entity_id": "TXN-CH-005",
        "score": 0.91,
        "country": "CH",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "PARTIAL",
        "lists_flagged": ["EU Consolidated List — partial match 0.87"],
        "policy_flags": ["pep_exposure", "complex_ownership_structure", "layering"],
        "network_risk_score": 0.77,
        "network_escalation_applied": True,
        "amount_usd": 5800000,
        "track": "A:partial",
        "high_priority": True,
    },
    {
        "payment_id": "TXN-PK-006",
        "entity_name": "Karachi Trade Finance Co.",
        "entity_id": "TXN-PK-006",
        "score": 0.72,
        "country": "PK",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "FULL",
        "policy_flags": ["high_risk_jurisdiction", "trade_finance_irregularity"],
        "network_risk_score": 0.38,
        "network_escalation_applied": False,
        "amount_usd": 198000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-ML-007",
        "entity_name": "Banque Régionale de Commerce",
        "entity_id": "TXN-ML-007",
        "score": 0.88,
        "country": "ML",
        "transfer_type": "INBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "policy_flags": ["correspondent_banking_risk", "high_risk_jurisdiction"],
        "network_risk_score": 0.71,
        "network_escalation_applied": True,
        "amount_usd": 760000,
        "track": "B:risk",
        "high_priority": True,
    },
    {
        "payment_id": "TXN-BVI-008",
        "entity_name": "Tortola Ventures Inc.",
        "entity_id": "TXN-BVI-008",
        "score": 0.65,
        "country": "VG",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "PARTIAL",
        "policy_flags": ["offshore_jurisdiction", "shell_company_indicator"],
        "network_risk_score": 0.33,
        "network_escalation_applied": False,
        "amount_usd": 430000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-IR-009",
        "entity_name": "Saman Exchange Bureau",
        "entity_id": "TXN-IR-009",
        "score": 0.97,
        "country": "IR",
        "transfer_type": "INBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "lists_flagged": ["OFAC IRAN sanctions program"],
        "policy_flags": ["sanctioned_jurisdiction", "hawala_typology", "pep_exposure"],
        "network_risk_score": 0.94,
        "network_escalation_applied": True,
        "amount_usd": 92000,
        "track": "A:country-sanctions",
        "high_priority": True,
    },
    {
        "payment_id": "TXN-CN-010",
        "entity_name": "Shenzhen Cross-Border Solutions Ltd",
        "entity_id": "TXN-CN-010",
        "score": 0.58,
        "country": "CN",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "FULL",
        "policy_flags": ["mica_compliance_risk"],
        "network_risk_score": 0.21,
        "network_escalation_applied": False,
        "amount_usd": 1200000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-PA-011",
        "entity_name": "Panama City Holdings Corp.",
        "entity_id": "TXN-PA-011",
        "score": 0.76,
        "country": "PA",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "policy_flags": ["offshore_jurisdiction", "complex_ownership_structure", "cash_intensive_business"],
        "network_risk_score": 0.52,
        "network_escalation_applied": False,
        "amount_usd": 670000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-KE-012",
        "entity_name": "Nairobi Digital Assets Ltd",
        "entity_id": "TXN-KE-012",
        "score": 0.61,
        "country": "KE",
        "transfer_type": "INBOUND",
        "ubo_resolution_status": "PARTIAL",
        "policy_flags": ["crypto_corridor", "mica_compliance_risk"],
        "network_risk_score": 0.29,
        "network_escalation_applied": False,
        "amount_usd": 88000,
        "track": "B:risk",
        "high_priority": False,
    },
    # ── MATCH cases (A:identity — confirmed sanctions hit, needs sign-off) ──
    {
        "payment_id": "TXN-SY-013",
        "entity_name": "Al-Baraka Investment Group",
        "entity_id": "TXN-SY-013",
        "score": 0.96,
        "country": "SY",
        "transfer_type": "INBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "lists_flagged": ["OFAC SDN", "EU Consolidated List"],
        "policy_flags": ["sanctioned_entity", "ofac_sdn_match", "pep_exposure"],
        "network_risk_score": 0.91,
        "network_escalation_applied": True,
        "amount_usd": 245000,
        "track": "A:identity",
        "high_priority": True,
    },
    {
        "payment_id": "TXN-KP-014",
        "entity_name": "Koryo Commercial Bank",
        "entity_id": "TXN-KP-014",
        "score": 0.99,
        "country": "KP",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "lists_flagged": ["OFAC SDN", "UN Consolidated", "DPRK sanctions program"],
        "policy_flags": ["sanctioned_jurisdiction", "ofac_sdn_match", "un_consolidated_match"],
        "network_risk_score": 0.98,
        "network_escalation_applied": True,
        "amount_usd": 1500000,
        "track": "A:identity",
        "high_priority": True,
    },
    # ── NO_MATCH cases (B:risk score < 0.50 — low risk, queued for QA sampling) ──
    {
        "payment_id": "TXN-DE-015",
        "entity_name": "München Logistik GmbH",
        "entity_id": "TXN-DE-015",
        "score": 0.31,
        "country": "DE",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "FULL",
        "policy_flags": [],
        "network_risk_score": 0.08,
        "network_escalation_applied": False,
        "amount_usd": 95000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-NL-016",
        "entity_name": "Amsterdam Trade Finance BV",
        "entity_id": "TXN-NL-016",
        "score": 0.22,
        "country": "NL",
        "transfer_type": "INTERNAL",
        "ubo_resolution_status": "FULL",
        "policy_flags": [],
        "network_risk_score": 0.05,
        "network_escalation_applied": False,
        "amount_usd": 340000,
        "track": "B:risk",
        "high_priority": False,
    },
    # ── Challenge-ready cases (demo: triggers LLM peer-review via Ollama) ───────
    {
        "payment_id": "TXN-CHALLENGE-001",
        "entity_name": "Riyadh Precision Components LLC",
        "entity_id": "TXN-CHALLENGE-001",
        "score": 0.82,
        "country": "AE",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "PARTIAL",
        "policy_flags": ["pep_exposure", "trade_finance_irregularity", "dual_use_goods"],
        "network_risk_score": 0.61,
        "network_escalation_applied": True,
        "amount_usd": 445000,
        "track": "B:risk",
        "high_priority": True,
    },
    {
        "payment_id": "TXN-NOMATCH-001",
        "entity_name": "Vienna Clearing Services AG",
        "entity_id": "TXN-NOMATCH-001",
        "score": 0.19,
        "country": "AT",
        "transfer_type": "INTERNAL",
        "ubo_resolution_status": "FULL",
        "policy_flags": [],
        "network_risk_score": 0.04,
        "network_escalation_applied": False,
        "amount_usd": 125000,
        "track": "B:risk",
        "high_priority": False,
    },
    {
        "payment_id": "TXN-TRADE-002",
        "entity_name": "Shenzhen Industrial Export Co.",
        "entity_id": "TXN-TRADE-002",
        "score": 0.77,
        "country": "CN",
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "PARTIAL",
        "lists_flagged": ["EU Consolidated List — partial match 0.79"],
        "policy_flags": ["trade_finance_irregularity", "sanctions_adjacent", "layering"],
        "network_risk_score": 0.58,
        "network_escalation_applied": True,
        "amount_usd": 690000,
        "track": "A:partial",
        "high_priority": True,
    },
]


async def seed(queue_url: str) -> None:
    enqueue_url = f"{queue_url}/enqueue"
    ok = err = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for case in CASES:
            pid = case["payment_id"]
            try:
                r = await client.post(enqueue_url, json=case)
                if r.status_code in (200, 201):
                    print(f"  OK  {pid}  {case['entity_name']}  score={case['score']}")
                    ok += 1
                else:
                    print(f"  ERR {pid} → HTTP {r.status_code}: {r.text[:120]}", file=sys.stderr)
                    err += 1
            except Exception as exc:
                print(f"  ERR {pid} → {exc}", file=sys.stderr)
                err += 1

    print(f"\nDone: {ok} enqueued, {err} errors.")
    if err:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed review queue with test AML cases")
    parser.add_argument("--queue", default="http://localhost:8009", help="Review queue base URL")
    args = parser.parse_args()
    asyncio.run(seed(args.queue))


if __name__ == "__main__":
    main()
