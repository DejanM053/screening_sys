#!/usr/bin/env python3
"""
Seed the challenge-system database with 8 realistic AML cases.

Usage:
    python scripts/seed_demo_cases.py [--api http://localhost:8001]

The script is idempotent: it skips any case whose transaction_id already
exists (the /submit endpoint does ON CONFLICT DO UPDATE, so re-running
overwrites with fresh data rather than erroring).

Cases include one deliberate contradiction pair:
  DEMO-TXN-001 (approved)  vs
  DEMO-TXN-002 (blocked)
Both are CZ→AE trade_finance corridor — the similarity engine should
surface this tension when either case is queried for similar cases.
"""

import argparse
import asyncio
import math
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

import httpx

# ── Helpers ───────────────────────────────────────────────────────────────────

def _xml(data: dict) -> str:
    """Build the AMLCase XML string from a structured dict."""

    def esc(v: object) -> str:
        return str(v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def party_el(tag: str, p: dict) -> ET.Element:
        el = ET.Element(tag)
        for key in ("entity_name", "entity_type", "country_of_incorporation",
                    "account_country", "registration_age_days", "is_pep",
                    "ownership_opacity_score"):
            sub = ET.SubElement(el, key)
            sub.text = esc(p.get(key, ""))
        return el

    root = ET.Element("AMLCase")

    # TransactionCore
    tc = ET.SubElement(root, "TransactionCore")
    for key in ("transaction_id", "amount", "currency", "value_date",
                "product_type", "direction"):
        sub = ET.SubElement(tc, key)
        sub.text = esc(data.get(key, ""))

    # Parties
    parties = ET.SubElement(root, "Parties")
    parties.append(party_el("Originator", data["originator"]))
    parties.append(party_el("Beneficiary", data["beneficiary"]))

    # TradeContext
    trade = data.get("trade_context") or {}
    if trade:
        tce = ET.SubElement(root, "TradeContext")
        tce.set("present", "true")
        for key in ("goods_description", "hs_code", "dual_use_flag",
                    "invoice_amount", "shipment_country"):
            sub = ET.SubElement(tce, key)
            sub.text = esc(trade.get(key, ""))
    else:
        tce = ET.SubElement(root, "TradeContext")
        tce.set("present", "false")

    # RelationshipContext
    rc = ET.SubElement(root, "RelationshipContext")
    for key in ("relationship_tenure_days", "first_transaction_to_counterparty",
                "referral_origin"):
        sub = ET.SubElement(rc, key)
        sub.text = esc(data.get(key, ""))

    # AnalystAssessment
    aa = ET.SubElement(root, "AnalystAssessment")
    tags_el = ET.SubElement(aa, "TypologyTags")
    for t in (data.get("typology_tags") or []):
        tag_el = ET.SubElement(tags_el, "tag")
        tag_el.text = esc(t)
    scores_el = ET.SubElement(aa, "RiskScores")
    for k, v in (data.get("risk_scores") or {}).items():
        score_el = ET.SubElement(scores_el, "score")
        score_el.set("key", k)
        score_el.text = esc(v)
    verdict_el = ET.SubElement(aa, "reviewer_verdict")
    verdict_el.text = esc(data.get("reviewer_verdict", ""))
    rationale_el = ET.SubElement(aa, "reviewer_rationale")
    rationale_el.text = esc(data.get("reviewer_rationale", ""))

    # GeopoliticalSnapshot
    geo = ET.SubElement(root, "GeopoliticalSnapshot")
    for cc, ctx in (data.get("geopolitical_snapshot") or {}).items():
        cce = ET.SubElement(geo, "CountryContext")
        cce.set("country", esc(cc))
        for key in ("FATF_status", "basel_aml_index_score"):
            sub = ET.SubElement(cce, key)
            sub.text = esc(ctx.get(key, ""))
        prog = ET.SubElement(cce, "ActiveSanctionsPrograms")
        for p in (ctx.get("active_sanctions_programs") or []):
            pe = ET.SubElement(prog, "program")
            pe.text = esc(p)
        alerts = ET.SubElement(cce, "ExportControlAlerts")
        for a in (ctx.get("export_control_alerts") or []):
            ae_el = ET.SubElement(alerts, "alert")
            ae_el.text = esc(a)

    raw = ET.tostring(root, encoding="unicode")
    reparsed = minidom.parseString(raw)
    return reparsed.toprettyxml(indent="  ")


# ── Case definitions ──────────────────────────────────────────────────────────

CASES = [
    # ── DEMO-TXN-001  ── APPROVED ── CZ→AE trade_finance (contradiction seed)
    {
        "transaction_id": "DEMO-TXN-001",
        "amount": "3800000",
        "currency": "EUR",
        "value_date": "2025-11-14",
        "product_type": "trade_finance",
        "direction": "outbound",
        "originator": {
            "entity_name": "Brno Industrial Supplies s.r.o.",
            "entity_type": "company",
            "country_of_incorporation": "CZ",
            "account_country": "CZ",
            "registration_age_days": 4380,
            "is_pep": "false",
            "ownership_opacity_score": "0.15",
        },
        "beneficiary": {
            "entity_name": "Khaleeji Mechanical Parts LLC",
            "entity_type": "company",
            "country_of_incorporation": "AE",
            "account_country": "AE",
            "registration_age_days": 1095,
            "is_pep": "false",
            "ownership_opacity_score": "0.35",
        },
        "trade_context": {
            "goods_description": "industrial pump assemblies and hydraulic fittings",
            "hs_code": "8413.60",
            "dual_use_flag": "false",
            "invoice_amount": "3750000",
            "shipment_country": "AE",
        },
        "relationship_tenure_days": "730",
        "first_transaction_to_counterparty": "false",
        "referral_origin": "existing_relationship",
        "typology_tags": ["trade_based_ml"],
        "risk_scores": {
            "source_of_wealth": "4.0",
            "document_consistency": "8.5",
            "counterparty_opacity": "4.5",
            "relationship_novelty": "2.0",
        },
        "reviewer_verdict": "approved",
        "reviewer_rationale": (
            "Established 2-year relationship. Full trade documentation provided including "
            "bill of lading, commercial invoice and certificate of origin. Pump assemblies "
            "are dual-use grey area but specific HS code 8413.60 is not on Wassenaar Annex I. "
            "Physical inspection report attached. AE counterparty has EU-registered parent. Approved."
        ),
        "geopolitical_snapshot": {
            "CZ": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 3.1,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
            "AE": {
                "FATF_status": "monitored",
                "basel_aml_index_score": 6.1,
                "active_sanctions_programs": ["OFAC-GLOMAG"],
                "export_control_alerts": ["BIS-MEP-2024-07: aluminum component diversion alert"],
            },
        },
    },

    # ── DEMO-TXN-002  ── BLOCKED ── CZ→AE trade_finance (contradiction trigger)
    {
        "transaction_id": "DEMO-TXN-002",
        "amount": "4100000",
        "currency": "EUR",
        "value_date": "2025-12-03",
        "product_type": "trade_finance",
        "direction": "outbound",
        "originator": {
            "entity_name": "Ostrava Precision Components a.s.",
            "entity_type": "company",
            "country_of_incorporation": "CZ",
            "account_country": "CZ",
            "registration_age_days": 2190,
            "is_pep": "false",
            "ownership_opacity_score": "0.20",
        },
        "beneficiary": {
            "entity_name": "Gulf Apex General Trading LLC",
            "entity_type": "company",
            "country_of_incorporation": "AE",
            "account_country": "AE",
            "registration_age_days": 180,
            "is_pep": "false",
            "ownership_opacity_score": "0.72",
        },
        "trade_context": {
            "goods_description": "precision-machined aluminum components and pressure valve assemblies",
            "hs_code": "8481.80",
            "dual_use_flag": "true",
            "invoice_amount": "3950000",
            "shipment_country": "AE",
        },
        "relationship_tenure_days": "45",
        "first_transaction_to_counterparty": "true",
        "referral_origin": "cold_contact",
        "typology_tags": ["trade_based_ml", "sanctions_adjacent"],
        "risk_scores": {
            "source_of_wealth": "4.0",
            "document_consistency": "5.5",
            "counterparty_opacity": "8.0",
            "relationship_novelty": "9.5",
        },
        "reviewer_verdict": "blocked",
        "reviewer_rationale": (
            "First transaction with 6-month-old AE counterparty with high opacity score. "
            "Dual-use flag on pressure valve components (HS 8481.80 appears on Wassenaar Annex I "
            "Category 2B). No end-user certificate provided. AE re-export risk to sanctioned "
            "jurisdictions given BIS MEP-2024-07 alert. Blocked pending dual-use export licence "
            "and enhanced due diligence on beneficial ownership of Gulf Apex General Trading."
        ),
        "geopolitical_snapshot": {
            "CZ": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 3.1,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
            "AE": {
                "FATF_status": "monitored",
                "basel_aml_index_score": 6.1,
                "active_sanctions_programs": ["OFAC-GLOMAG"],
                "export_control_alerts": ["BIS-MEP-2024-07: aluminum component diversion alert"],
            },
        },
    },

    # ── DEMO-TXN-003  ── APPROVED ── SG→DE crypto OTC
    {
        "transaction_id": "DEMO-TXN-003",
        "amount": "890000",
        "currency": "USDT",
        "value_date": "2025-10-22",
        "product_type": "crypto",
        "direction": "outbound",
        "originator": {
            "entity_name": "Nexus Digital Asset OTC Pte Ltd",
            "entity_type": "financial_institution",
            "country_of_incorporation": "SG",
            "account_country": "SG",
            "registration_age_days": 1460,
            "is_pep": "false",
            "ownership_opacity_score": "0.18",
        },
        "beneficiary": {
            "entity_name": "Hartmann Capital GmbH",
            "entity_type": "financial_institution",
            "country_of_incorporation": "DE",
            "account_country": "DE",
            "registration_age_days": 3650,
            "is_pep": "false",
            "ownership_opacity_score": "0.10",
        },
        "relationship_tenure_days": "365",
        "first_transaction_to_counterparty": "false",
        "referral_origin": "existing_relationship",
        "typology_tags": ["crypto_layering"],
        "risk_scores": {
            "source_of_wealth": "6.5",
            "document_consistency": "8.0",
            "counterparty_opacity": "2.0",
            "relationship_novelty": "3.0",
        },
        "reviewer_verdict": "approved",
        "reviewer_rationale": (
            "Regulated OTC desk (MAS-licensed) to BaFin-regulated fund. Travel Rule data "
            "exchanged via OpenVASP. Source of USDT traced to 3 on-chain hops from regulated "
            "exchange deposits — no mixing services detected. SG→DE corridor low risk. "
            "crypto_layering tag applied as standard for USDT OTC but no red flags. Approved."
        ),
        "geopolitical_snapshot": {
            "SG": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 3.4,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
            "DE": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 2.9,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
        },
    },

    # ── DEMO-TXN-004  ── ESCALATED ── CY→CH wire, PEP
    {
        "transaction_id": "DEMO-TXN-004",
        "amount": "2200000",
        "currency": "USD",
        "value_date": "2025-11-28",
        "product_type": "wire_transfer",
        "direction": "outbound",
        "originator": {
            "entity_name": "Meridian Consulting Partners Ltd",
            "entity_type": "company",
            "country_of_incorporation": "CY",
            "account_country": "CY",
            "registration_age_days": 730,
            "is_pep": "true",
            "ownership_opacity_score": "0.68",
        },
        "beneficiary": {
            "entity_name": "Albrecht & Söhne AG",
            "entity_type": "company",
            "country_of_incorporation": "CH",
            "account_country": "CH",
            "registration_age_days": 8760,
            "is_pep": "false",
            "ownership_opacity_score": "0.12",
        },
        "relationship_tenure_days": "90",
        "first_transaction_to_counterparty": "false",
        "referral_origin": "platform",
        "typology_tags": ["pep_exposure", "layering"],
        "risk_scores": {
            "source_of_wealth": "7.5",
            "document_consistency": "5.0",
            "counterparty_opacity": "7.5",
            "relationship_novelty": "6.0",
        },
        "reviewer_verdict": "escalated",
        "reviewer_rationale": (
            "UBO of Meridian Consulting Partners is a senior official of a CY state-owned enterprise "
            "(confirmed PEP under 4AMLD Art. 3(9)). CY nominee director structure adds opacity. "
            "Consulting retainer agreement provided but scope is vague. CH beneficiary is a "
            "legitimate commodity trader but PEP-linked funds routing through Cyprus warrants "
            "enhanced due diligence sign-off from MLRO before release. Escalated."
        ),
        "geopolitical_snapshot": {
            "CY": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 5.1,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
            "CH": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 3.6,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
        },
    },

    # ── DEMO-TXN-005  ── BLOCKED ── US→MX wire, structuring
    {
        "transaction_id": "DEMO-TXN-005",
        "amount": "9400",
        "currency": "USD",
        "value_date": "2025-12-01",
        "product_type": "wire_transfer",
        "direction": "outbound",
        "originator": {
            "entity_name": "Castellano Import Export Inc",
            "entity_type": "company",
            "country_of_incorporation": "US",
            "account_country": "US",
            "registration_age_days": 540,
            "is_pep": "false",
            "ownership_opacity_score": "0.40",
        },
        "beneficiary": {
            "entity_name": "Comercializadora del Pacífico S.A. de C.V.",
            "entity_type": "company",
            "country_of_incorporation": "MX",
            "account_country": "MX",
            "registration_age_days": 2555,
            "is_pep": "false",
            "ownership_opacity_score": "0.30",
        },
        "relationship_tenure_days": "180",
        "first_transaction_to_counterparty": "false",
        "referral_origin": "existing_relationship",
        "typology_tags": ["structuring"],
        "risk_scores": {
            "source_of_wealth": "5.5",
            "document_consistency": "6.0",
            "counterparty_opacity": "4.0",
            "relationship_novelty": "7.0",
        },
        "reviewer_verdict": "blocked",
        "reviewer_rationale": (
            "This transaction is the 11th in a sequence over 30 days, all between $9,000 and $9,800 "
            "to the same MX counterparty from two related accounts — classic structuring pattern below "
            "the $10,000 BSA/CTR threshold. Aggregate $104,500 in 30 days. SAR filed (BSA § 5318(g)). "
            "Transaction blocked; account flagged for enhanced monitoring."
        ),
        "geopolitical_snapshot": {
            "US": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 2.8,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
            "MX": {
                "FATF_status": "monitored",
                "basel_aml_index_score": 6.1,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
        },
    },

    # ── DEMO-TXN-006  ── APPROVED ── GB→IT real estate wire
    {
        "transaction_id": "DEMO-TXN-006",
        "amount": "1750000",
        "currency": "EUR",
        "value_date": "2025-10-10",
        "product_type": "wire_transfer",
        "direction": "outbound",
        "originator": {
            "entity_name": "Devereux Property Holdings Ltd",
            "entity_type": "company",
            "country_of_incorporation": "GB",
            "account_country": "GB",
            "registration_age_days": 5840,
            "is_pep": "false",
            "ownership_opacity_score": "0.10",
        },
        "beneficiary": {
            "entity_name": "Adriatico Sviluppo Immobiliare S.p.A.",
            "entity_type": "company",
            "country_of_incorporation": "IT",
            "account_country": "IT",
            "registration_age_days": 7300,
            "is_pep": "false",
            "ownership_opacity_score": "0.12",
        },
        "relationship_tenure_days": "1460",
        "first_transaction_to_counterparty": "false",
        "referral_origin": "existing_relationship",
        "typology_tags": ["real_estate"],
        "risk_scores": {
            "source_of_wealth": "2.0",
            "document_consistency": "9.0",
            "counterparty_opacity": "1.5",
            "relationship_novelty": "1.5",
        },
        "reviewer_verdict": "approved",
        "reviewer_rationale": (
            "Established 4-year property development partnership. Funds are deposit on a commercial "
            "office development in Milan — notarial contract and land registry extracts provided. "
            "Source of funds traced to dividend distribution from UK-listed parent (HMRC clearance "
            "on file). Both entities are FCA/Banca d'Italia regulated. Standard real_estate tag "
            "applied; no red flags. Approved."
        ),
        "geopolitical_snapshot": {
            "GB": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 3.2,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
            "IT": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 3.8,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
        },
    },

    # ── DEMO-TXN-007  ── BLOCKED ── ML→GB correspondent, blacklisted entity
    {
        "transaction_id": "DEMO-TXN-007",
        "amount": "5600000",
        "currency": "USD",
        "value_date": "2025-11-05",
        "product_type": "wire_transfer",
        "direction": "inbound",
        "originator": {
            "entity_name": "Banque Régionale de Commerce",
            "entity_type": "financial_institution",
            "country_of_incorporation": "ML",
            "account_country": "ML",
            "registration_age_days": 9125,
            "is_pep": "false",
            "ownership_opacity_score": "0.55",
        },
        "beneficiary": {
            "entity_name": "Atlantic Gateway Financial Ltd",
            "entity_type": "financial_institution",
            "country_of_incorporation": "GB",
            "account_country": "GB",
            "registration_age_days": 2920,
            "is_pep": "false",
            "ownership_opacity_score": "0.22",
        },
        "relationship_tenure_days": "60",
        "first_transaction_to_counterparty": "false",
        "referral_origin": "platform",
        "typology_tags": ["correspondent_risk", "sanctions_adjacent"],
        "risk_scores": {
            "source_of_wealth": "8.5",
            "document_consistency": "3.5",
            "counterparty_opacity": "7.0",
            "relationship_novelty": "8.5",
        },
        "reviewer_verdict": "blocked",
        "reviewer_rationale": (
            "Originator bank operates in Mali (FATF blacklisted; UN SC 2374 arms embargo). "
            "Banque Régionale de Commerce appears on EU MALI ARMS consolidated list with "
            "asset-freeze designation. Correspondent relationship should not have been established "
            "— de-risking required. Funds frozen pending OFAC OFSI notification. "
            "SAR filed. Compliance escalation raised with Board."
        ),
        "geopolitical_snapshot": {
            "ML": {
                "FATF_status": "blacklisted",
                "basel_aml_index_score": 8.4,
                "active_sanctions_programs": ["EU-MALI-ARMS", "UN-SC-2374"],
                "export_control_alerts": [],
            },
            "GB": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 3.2,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
        },
    },

    # ── DEMO-TXN-008  ── APPROVED ── IE→IE crypto institutional settlement
    {
        "transaction_id": "DEMO-TXN-008",
        "amount": "3200000",
        "currency": "BTC_USD",
        "value_date": "2025-12-11",
        "product_type": "crypto",
        "direction": "outbound",
        "originator": {
            "entity_name": "Vantage Institutional Prime Ltd",
            "entity_type": "financial_institution",
            "country_of_incorporation": "IE",
            "account_country": "IE",
            "registration_age_days": 2190,
            "is_pep": "false",
            "ownership_opacity_score": "0.08",
        },
        "beneficiary": {
            "entity_name": "Kraken Financial Ireland DAC",
            "entity_type": "financial_institution",
            "country_of_incorporation": "IE",
            "account_country": "IE",
            "registration_age_days": 1825,
            "is_pep": "false",
            "ownership_opacity_score": "0.05",
        },
        "relationship_tenure_days": "540",
        "first_transaction_to_counterparty": "false",
        "referral_origin": "existing_relationship",
        "typology_tags": ["crypto_layering"],
        "risk_scores": {
            "source_of_wealth": "1.5",
            "document_consistency": "9.5",
            "counterparty_opacity": "1.0",
            "relationship_novelty": "2.0",
        },
        "reviewer_verdict": "approved",
        "reviewer_rationale": (
            "Intra-jurisdiction institutional prime brokerage settlement (IE→IE). Both entities "
            "are CBI-registered VASPs under EU MiCA transitional provisions. Travel Rule data "
            "exchanged in full. Chain analysis confirms source wallets are exchange-attributed "
            "with no mixing service hops. crypto_layering tag is applied as a matter of policy "
            "for all crypto transactions; no indicators of actual layering. Approved."
        ),
        "geopolitical_snapshot": {
            "IE": {
                "FATF_status": "compliant",
                "basel_aml_index_score": 2.7,
                "active_sanctions_programs": [],
                "export_control_alerts": [],
            },
        },
    },
]


# ── Embed with BOW fallback ───────────────────────────────────────────────────

async def _embed(client: httpx.AsyncClient, ollama_url: str, text: str) -> list[float]:
    try:
        r = await client.post(
            f"{ollama_url}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()["embedding"]
    except Exception:
        # BOW fallback: hash-based random indexing to 768-dim unit-normalised vector
        dim = 768
        vec = [0.0] * dim
        for token in text.lower().split():
            vec[abs(hash(token)) % dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm > 1e-9 else vec


# ── Main ─────────────────────────────────────────────────────────────────────

async def seed(api_url: str) -> None:
    submit_url = f"{api_url}/api/cases/submit"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Detect Ollama
        ollama_url = "http://localhost:11434"
        try:
            r = await client.get(f"{ollama_url}/api/tags", timeout=3.0)
            ollama_ok = r.status_code == 200
        except Exception:
            ollama_ok = False
        print(f"Ollama: {'available' if ollama_ok else 'unavailable (BOW fallback)'}")

        ok = err = 0
        for case in CASES:
            txn_id = case["transaction_id"]
            # Build embed text
            embed_text = " ".join([
                case["originator"]["entity_name"],
                case["beneficiary"]["entity_name"],
                " ".join(case.get("typology_tags") or []),
                case.get("reviewer_rationale", ""),
                (case.get("trade_context") or {}).get("goods_description", ""),
            ])
            _ = await _embed(client, ollama_url, embed_text)  # pre-warm; route stores its own

            xml_str = _xml(case)
            try:
                r = await client.post(
                    submit_url,
                    json={"transaction_id": txn_id, "case_xml": xml_str},
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    print(f"  OK  {txn_id} → case_id={data.get('case_id')}")
                    ok += 1
                else:
                    print(f"  ERR {txn_id} → HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
                    err += 1
            except Exception as exc:
                print(f"  ERR {txn_id} → {exc}", file=sys.stderr)
                err += 1

    print(f"\nDone: {ok} submitted, {err} errors.")
    if err:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed AML challenge-system demo cases")
    parser.add_argument("--api", default="http://localhost:8001", help="screening-api base URL")
    args = parser.parse_args()

    asyncio.run(seed(args.api))


if __name__ == "__main__":
    main()
