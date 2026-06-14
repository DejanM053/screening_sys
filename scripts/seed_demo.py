#!/usr/bin/env python3
"""
Seed the day-1 demo with 3 realistic screening scenarios.

Usage:
    python scripts/seed_demo.py [--api http://localhost:8001]
                                [--queue http://localhost:8009]
                                [--graph http://localhost:8005]
                                [--crypto http://localhost:8004]

What this does:
  1. Seeds the graph-engine with demo relationships so ENT-DEMO-001 shows
     network risk (connected to SDN-OFAC-001 + ENT-DEMO-002).
  2. Seeds 5 KYB wallets into the crypto-screener registry.
  3. Screens 3 demo entities via /fiat/screen — each becomes a REVIEW queue item.
  4. Screens 1 demo wallet via /crypto/screen.
"""

import argparse
import asyncio
import sys

import httpx

DEMO_PAYMENTS = [
    {
        "payment": {
            "payment_id": "DEMO-001",
            "originator_name": "Al-Qadir Trading LLC",
            "originator_country": "AE",
            "beneficiary_name": "Thames Export Ltd",
            "beneficiary_country": "GB",
            "amount_usd": 185_000.0,
            "asset_type": "fiat",
            "entity_type": "business",
        }
    },
    {
        "payment": {
            "payment_id": "DEMO-002",
            "originator_name": "Gulf Holdings International",
            "originator_country": "AE",
            "beneficiary_name": "Meridian Finance Group",
            "beneficiary_country": "CY",
            "amount_usd": 520_000.0,
            "asset_type": "fiat",
            "entity_type": "business",
        }
    },
    {
        "payment": {
            "payment_id": "DEMO-003",
            "originator_name": "North Korean Trade Bureau",
            "originator_country": "KP",
            "beneficiary_name": "Shell Holdings BVI",
            "beneficiary_country": "VG",
            "amount_usd": 1_200_000.0,
            "asset_type": "fiat",
            "entity_type": "business",
        }
    },
]

DEMO_WALLETS = [
    # KYB-verified platform members
    {"address": "TXxxKYB001AEGulfHoldings", "entity_id": "ENT-KYB-001", "ubo_resolution_status": "FULL"},
    {"address": "TXxxKYB002UKThames", "entity_id": "ENT-KYB-002", "ubo_resolution_status": "PARTIAL"},
    {"address": "TXxxKYB003AEAlQadir", "entity_id": "ENT-KYB-003", "ubo_resolution_status": "FULL"},
    {"address": "TXxxKYB004SGTradeCenter", "entity_id": "ENT-KYB-004", "ubo_resolution_status": "FULL"},
    {"address": "TXxxKYB005HKMeridian", "entity_id": "ENT-KYB-005", "ubo_resolution_status": "UNRESOLVED"},
]

DEMO_CRYPTO_SCREEN = {
    "payment": {
        "payment_id": "DEMO-CRYPTO-001",
        "originator_name": "External Sender",
        "originator_country": "RU",
        "originator_wallet": "TYyyExternal002RU",
        "beneficiary_name": "Gulf Holdings (KYB verified)",
        "beneficiary_country": "AE",
        "beneficiary_wallet": "TXxxKYB001AEGulfHoldings",
        "amount_usd": 250_000.0,
        "asset_type": "USDT",
        "chain": "tron",
        "entity_type": "business",
    },
    "stablecoin": "USDT",
}

# Demo graph relationships — connect DEMO-001 to SDN-OFAC-001 (1 hop)
# and ENT-DEMO-002 (1 hop) so network risk fires for this entity.
DEMO_GRAPH_RELATIONSHIPS = [
    {"entity_a": "DEMO-001", "entity_b": "SDN-OFAC-001", "attr_type": "registered_address", "weight": 0.7},
    {"entity_a": "DEMO-001", "entity_b": "ENT-DEMO-002", "attr_type": "director", "weight": 0.8},
    {"entity_a": "DEMO-002", "entity_b": "ENT-DEMO-002", "attr_type": "ubo", "weight": 0.9},
]

# Direct demo queue entries — realistic scores matching what a live yente + graph engine would produce.
# These supplement the API-screened entries and ensure the queue always has data for the demo.
DEMO_QUEUE_ENTRIES = [
    {
        "payment_id": "DEMO-001",
        "entity_id": "ENT-DEMO-001",
        "entity_name": "Al-Qadir Trading LLC",
        "score": 0.64,
        "country": "AE",
        "lists_flagged": ["Track A:partial — EU Consolidated List 0.71 score"],
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "FULL",
        "policy_flags": [],
        "network_risk_score": 0.116,
        "amount_usd": 185_000.0,
        "track": "B:risk",
    },
    {
        "payment_id": "DEMO-002",
        "entity_id": "ENT-DEMO-002",
        "entity_name": "Gulf Holdings International",
        "score": 0.72,
        "country": "AE",
        "lists_flagged": ["Track A:partial — OFAC SDN 0.78 score"],
        "transfer_type": "OUTBOUND",
        "ubo_resolution_status": "PARTIAL",
        "policy_flags": [],
        "network_risk_score": 0.230,
        "amount_usd": 520_000.0,
        "track": "B:risk",
    },
    {
        "payment_id": "DEMO-CRYPTO-001",
        "entity_id": "DEMO-CRYPTO-001",
        "entity_name": "External Sender (TYyyExternal002RU)",
        "score": 0.55,
        "country": "RU",
        "lists_flagged": ["TRON wallet — 2 hops from OFAC SDN wallet"],
        "transfer_type": "INBOUND",
        "ubo_resolution_status": "UNRESOLVED",
        "policy_flags": ["MiCA_COMPLIANCE_RISK"],
        "network_risk_score": 0.40,
        "amount_usd": 250_000.0,
        "track": "B:risk",
    },
]


async def seed(api: str, queue: str, graph: str, crypto: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:

        # ── 1. Health-check all services ──────────────────────────────────────
        print("Checking services...")
        for name, url in [("screening-api", api), ("review-queue", queue),
                           ("graph-engine", graph), ("crypto-screener", crypto)]:
            try:
                r = await client.get(f"{url}/health")
                print(f"  ✓ {name}: {r.json().get('status', 'ok')}")
            except Exception as exc:
                print(f"  ✗ {name} unreachable: {exc}", file=sys.stderr)

        # ── 2. Seed graph demo entities so SDN-OFAC-001 is present ───────────
        print("\nSeeding graph relationships...")
        for rel in DEMO_GRAPH_RELATIONSHIPS:
            try:
                r = await client.post(f"{graph}/add-relationship", json=rel)
                if r.status_code == 200:
                    print(f"  ✓ {rel['entity_a']} --{rel['attr_type']}--> {rel['entity_b']}")
                elif r.status_code == 404:
                    print(f"  ⚠ Skipped (entity not yet in graph): {rel['entity_a']} or {rel['entity_b']}")
            except Exception as exc:
                print(f"  ✗ relationship error: {exc}", file=sys.stderr)

        # ── 3. Seed KYB wallet registry ───────────────────────────────────────
        print("\nSeeding KYB wallet registry...")
        for wallet in DEMO_WALLETS:
            try:
                r = await client.post(
                    f"{crypto}/admin/kyb-registry/{wallet['address']}",
                    json={
                        "entity_id": wallet["entity_id"],
                        "ubo_resolution_status": wallet["ubo_resolution_status"],
                        "onboarding_score": 0.2,
                        "kyb_verified_at": "2026-06-13T00:00:00Z",
                    },
                )
                status = r.json().get("status", r.status_code)
                print(f"  ✓ {wallet['address'][:20]}... ({wallet['ubo_resolution_status']}) → {status}")
            except Exception as exc:
                print(f"  ✗ wallet seed error: {exc}", file=sys.stderr)

        # ── 4. Screen 3 demo entities (→ REVIEW queue) ───────────────────────
        print("\nScreening 3 demo entities...")
        for payment in DEMO_PAYMENTS:
            pid = payment["payment"]["payment_id"]
            name = payment["payment"]["originator_name"]
            try:
                r = await client.post(f"{api}/fiat/screen", json=payment)
                result = r.json()
                verdict = result.get("verdict", {}).get("verdict", "?")
                score = result.get("verdict", {}).get("composite_score", 0.0)
                track = result.get("verdict", {}).get("track", "?")
                ms = result.get("processing_time_ms", 0)
                print(f"  ✓ {pid} | {name[:30]:<30} → {verdict} (score={score:.3f}, track={track}, {ms:.0f}ms)")
            except Exception as exc:
                print(f"  ✗ {pid} screen error: {exc}", file=sys.stderr)

        # ── 5. Seed graph relationships AFTER entities are ingested ──────────
        print("\nRe-seeding graph relationships (post-ingestion)...")
        for rel in DEMO_GRAPH_RELATIONSHIPS:
            try:
                r = await client.post(f"{graph}/add-relationship", json=rel)
                if r.status_code == 200:
                    print(f"  ✓ {rel['entity_a']} --{rel['attr_type']}--> {rel['entity_b']}")
                elif r.status_code == 404:
                    print(f"  ⚠ Still missing: {rel}")
            except Exception as exc:
                print(f"  ✗ {exc}", file=sys.stderr)

        # ── 6. Screen demo crypto wallet ──────────────────────────────────────
        print("\nScreening demo TRON wallet...")
        try:
            r = await client.post(f"{api}/crypto/screen", json=DEMO_CRYPTO_SCREEN)
            result = r.json()
            verdict = result.get("verdict", {}).get("verdict", "?")
            score = result.get("verdict", {}).get("composite_score", 0.0)
            print(f"  ✓ DEMO-CRYPTO-001 | TYyyExternal002RU → {verdict} (score={score:.3f})")
        except Exception as exc:
            print(f"  ✗ crypto screen error: {exc}", file=sys.stderr)

        # ── 7. Directly enqueue demo cases with realistic scores ─────────────
        print("\nDirect-seeding review queue with demo cases...")
        for entry in DEMO_QUEUE_ENTRIES:
            try:
                r = await client.post(f"{queue}/enqueue", json=entry)
                if r.status_code in (200, 201):
                    print(f"  ✓ {entry['payment_id']} | {entry['entity_name'][:30]:<30} → score={entry['score']:.2f}")
                else:
                    print(f"  ✗ {entry['payment_id']} enqueue failed: {r.status_code} {r.text[:100]}", file=sys.stderr)
            except Exception as exc:
                print(f"  ✗ {entry['payment_id']} enqueue error: {exc}", file=sys.stderr)

        # ── 8. Check queue ────────────────────────────────────────────────────
        print("\nChecking review queue...")
        try:
            r = await client.get(f"{queue}/queue")
            items = r.json()
            print(f"  ✓ {len(items)} item(s) in REVIEW queue:")
            for item in items:
                print(f"     • {item.get('payment_id')} | {item.get('entity_name', '')[:30]:<30} "
                      f"| score={item.get('score', 0):.3f} | {item.get('ubo_resolution_status', '')}")
        except Exception as exc:
            print(f"  ✗ queue check error: {exc}", file=sys.stderr)

    print("\nDone. Open http://localhost:3000 to see the queue dashboard.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the day-1 demo data")
    parser.add_argument("--api", default="http://localhost:8001")
    parser.add_argument("--queue", default="http://localhost:8009")
    parser.add_argument("--graph", default="http://localhost:8005")
    parser.add_argument("--crypto", default="http://localhost:8004")
    args = parser.parse_args()
    asyncio.run(seed(api=args.api, queue=args.queue, graph=args.graph, crypto=args.crypto))


if __name__ == "__main__":
    main()
