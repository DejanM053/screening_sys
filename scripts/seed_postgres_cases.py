#!/usr/bin/env python3
"""
Seed the PostgreSQL challenge database with historical AML case precedents.

Run this AFTER the screening-api is up:
    python scripts/seed_postgres_cases.py [--api http://localhost:8001]

Idempotent: ON CONFLICT DO UPDATE in the API, so safe to re-run.
The key design goal: include CONTRADICTING verdicts for the same typology tags
so the challenge review panel can surface meaningful disagreements.
"""

import argparse
import asyncio
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

import httpx

# ─── XML builder (mirrors challenge_xml.py server-side logic) ─────────────────

def _sub(parent, tag, value=None):
    el = ET.SubElement(parent, tag)
    if value is not None:
        el.text = str(value)
    return el


def _build_xml(case: dict) -> str:
    root = ET.Element("AMLCase")

    txn = ET.SubElement(root, "TransactionCore")
    _sub(txn, "transaction_id", case["transaction_id"])
    _sub(txn, "amount", case["amount"])
    _sub(txn, "currency", case.get("currency", "USD"))
    _sub(txn, "value_date", case.get("value_date", "2025-06-10"))
    _sub(txn, "product_type", case.get("product_type", "wire_transfer"))
    _sub(txn, "direction", case.get("direction", "outbound"))

    parties = ET.SubElement(root, "Parties")
    for role in ("Originator", "Beneficiary"):
        key = role.lower()
        p = case[key]
        pel = ET.SubElement(parties, role)
        _sub(pel, "entity_name", p["entity_name"])
        _sub(pel, "entity_type", p.get("entity_type", "company"))
        _sub(pel, "country_of_incorporation", p["country"])
        _sub(pel, "account_country", p["country"])
        _sub(pel, "registration_age_days", p.get("reg_age", 365))
        _sub(pel, "is_pep", str(p.get("is_pep", False)).lower())
        _sub(pel, "ownership_opacity_score", p.get("opacity", 0.3))

    tc_el = ET.SubElement(root, "TradeContext")
    trade = case.get("trade_context")
    if trade:
        tc_el.set("present", "true")
        _sub(tc_el, "goods_description", trade.get("goods_description", ""))
        _sub(tc_el, "hs_code", trade.get("hs_code", ""))
        _sub(tc_el, "dual_use_flag", str(trade.get("dual_use_flag", False)).lower())
        _sub(tc_el, "invoice_amount", trade.get("invoice_amount", 0))
        _sub(tc_el, "shipment_country", trade.get("shipment_country", ""))
    else:
        tc_el.set("present", "false")

    rel = ET.SubElement(root, "RelationshipContext")
    _sub(rel, "relationship_tenure_days", case.get("tenure_days", 180))
    _sub(rel, "first_transaction_to_counterparty",
         str(case.get("first_txn", False)).lower())
    _sub(rel, "referral_origin", case.get("referral_origin", "existing_relationship"))

    aa = ET.SubElement(root, "AnalystAssessment")
    tags_el = ET.SubElement(aa, "TypologyTags")
    for t in case.get("typology_tags", ["unknown"]):
        ET.SubElement(tags_el, "tag").text = t
    rs_el = ET.SubElement(aa, "RiskScores")
    for k, v in case.get("risk_scores", {}).items():
        s = ET.SubElement(rs_el, "score")
        s.set("key", k)
        s.text = str(v)
    _sub(aa, "reviewer_verdict", case["verdict"])
    _sub(aa, "reviewer_rationale", case.get("rationale", ""))

    geo = ET.SubElement(root, "GeopoliticalSnapshot")
    for cc, ctx in case.get("geopolitical_snapshot", {}).items():
        cc_el = ET.SubElement(geo, "CountryContext")
        cc_el.set("country", cc)
        _sub(cc_el, "FATF_status", ctx.get("FATF_status", "compliant"))
        _sub(cc_el, "basel_aml_index_score", ctx.get("basel_aml_index_score", 3.0))
        progs = ET.SubElement(cc_el, "ActiveSanctionsPrograms")
        for p in ctx.get("active_sanctions_programs", []):
            ET.SubElement(progs, "program").text = p
        alerts = ET.SubElement(cc_el, "ExportControlAlerts")
        for a in ctx.get("export_control_alerts", []):
            ET.SubElement(alerts, "alert").text = a

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


# ─── Case definitions ──────────────────────────────────────────────────────────
# DESIGN: For each typology cluster, we include CONTRADICTING verdicts
# (blocked vs approved vs escalated) so challenge review finds real disagreements.

GEO = {
    "AE": {"FATF_status": "monitored",   "basel_aml_index_score": 6.1,
           "active_sanctions_programs": ["OFAC-GLOMAG"], "export_control_alerts": ["BIS-MEP-2024-07"]},
    "RU": {"FATF_status": "blacklisted", "basel_aml_index_score": 7.8,
           "active_sanctions_programs": ["OFAC-SDN", "EU-CONSOLIDATED"],
           "export_control_alerts": ["BIS-EAR-RU"]},
    "CH": {"FATF_status": "compliant",   "basel_aml_index_score": 3.6,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "CY": {"FATF_status": "compliant",   "basel_aml_index_score": 5.1,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "CN": {"FATF_status": "monitored",   "basel_aml_index_score": 5.9,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "DE": {"FATF_status": "compliant",   "basel_aml_index_score": 2.9,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "GB": {"FATF_status": "compliant",   "basel_aml_index_score": 3.2,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "NG": {"FATF_status": "greylisted",  "basel_aml_index_score": 7.2,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "PK": {"FATF_status": "greylisted",  "basel_aml_index_score": 7.6,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "PA": {"FATF_status": "greylisted",  "basel_aml_index_score": 6.8,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "SG": {"FATF_status": "compliant",   "basel_aml_index_score": 3.4,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "ML": {"FATF_status": "blacklisted", "basel_aml_index_score": 8.4,
           "active_sanctions_programs": ["EU-MALI-ARMS", "UN-SC-2374"], "export_control_alerts": []},
    "TR": {"FATF_status": "greylisted",  "basel_aml_index_score": 7.0,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "UA": {"FATF_status": "monitored",   "basel_aml_index_score": 6.4,
           "active_sanctions_programs": [], "export_control_alerts": []},
    "VG": {"FATF_status": "monitored",   "basel_aml_index_score": 5.3,
           "active_sanctions_programs": [], "export_control_alerts": []},
}

CASES = [
    # ── Cluster 1: layering + sanctions_adjacent — BLOCKED precedents ──────────
    {
        "transaction_id": "HIST-AE-BLK-001",
        "amount": 1250000, "currency": "USD",
        "value_date": "2025-03-14", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Gulf Star Holdings Ltd",  "country": "AE", "opacity": 0.72, "is_pep": True},
        "beneficiary": {"entity_name": "Meridian Capital BVI",    "country": "VG", "opacity": 0.85},
        "tenure_days": 12, "first_txn": True, "referral_origin": "cold_contact",
        "typology_tags": ["layering", "sanctions_adjacent", "pep_exposure"],
        "risk_scores": {"source_of_wealth": 8.5, "document_consistency": 3.2,
                        "counterparty_opacity": 9.0, "relationship_novelty": 9.5},
        "verdict": "blocked",
        "rationale": "PEP-linked entity with freshly incorporated offshore beneficiary. No credible source of wealth. Layering pattern confirmed across 3 intermediate entities.",
        "geopolitical_snapshot": {"AE": GEO["AE"], "VG": GEO["VG"]},
    },
    {
        "transaction_id": "HIST-AE-BLK-002",
        "amount": 890000, "currency": "USD",
        "value_date": "2025-04-02", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Emirates Bridge Finance",  "country": "AE", "opacity": 0.61},
        "beneficiary": {"entity_name": "Pinnacle Trust AG",        "country": "CH", "opacity": 0.55},
        "tenure_days": 45, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["layering", "structuring"],
        "risk_scores": {"source_of_wealth": 7.0, "document_consistency": 4.5,
                        "counterparty_opacity": 7.5, "relationship_novelty": 6.0},
        "verdict": "blocked",
        "rationale": "Round-amount structuring across 4 wires below EUR 250k threshold. Beneficiary is nominee-directed Swiss trust with no discernible commercial purpose.",
        "geopolitical_snapshot": {"AE": GEO["AE"], "CH": GEO["CH"]},
    },
    # ── Cluster 1 CONTRADICTION: similar profile, APPROVED after full UBO clearance ─
    {
        "transaction_id": "HIST-AE-APR-001",
        "amount": 980000, "currency": "USD",
        "value_date": "2025-01-18", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Al Noor Commercial LLC",   "country": "AE", "opacity": 0.28},
        "beneficiary": {"entity_name": "Frankfurt Machinery GmbH", "country": "DE", "opacity": 0.12},
        "tenure_days": 720, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["layering", "sanctions_adjacent"],
        "risk_scores": {"source_of_wealth": 3.5, "document_consistency": 8.5,
                        "counterparty_opacity": 2.5, "relationship_novelty": 2.0},
        "verdict": "approved",
        "rationale": "Apparent layering signal resolved on UBO review: full beneficial ownership chain disclosed, audited financials provided. Long-standing trade relationship with documented invoices. Cleared.",
        "geopolitical_snapshot": {"AE": GEO["AE"], "DE": GEO["DE"]},
    },
    {
        "transaction_id": "HIST-CH-APR-001",
        "amount": 3400000, "currency": "CHF",
        "value_date": "2025-02-05", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Helvetica Asset Management SA", "country": "CH", "opacity": 0.22},
        "beneficiary": {"entity_name": "Singapore Quantum Partners",    "country": "SG", "opacity": 0.31},
        "tenure_days": 1100, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["layering", "structuring", "sanctions_adjacent"],
        "risk_scores": {"source_of_wealth": 2.0, "document_consistency": 9.0,
                        "counterparty_opacity": 3.0, "relationship_novelty": 1.5},
        "verdict": "approved",
        "rationale": "Complex multi-leg structure cleared after FINMA correspondent review. Full KYB package verified. Underlying transaction is a regulated fund repatriation.",
        "geopolitical_snapshot": {"CH": GEO["CH"], "SG": GEO["SG"]},
    },
    # ── Cluster 1 ESCALATED ─────────────────────────────────────────────────────
    {
        "transaction_id": "HIST-RU-ESC-001",
        "amount": 5100000, "currency": "USD",
        "value_date": "2025-03-29", "product_type": "wire_transfer", "direction": "inbound",
        "originator":  {"entity_name": "Volga Trade Group",        "country": "RU", "opacity": 0.79, "is_pep": True},
        "beneficiary": {"entity_name": "Cyprus Holding Co. Ltd",   "country": "CY", "opacity": 0.65},
        "tenure_days": 90, "first_txn": False, "referral_origin": "platform",
        "typology_tags": ["layering", "sanctions_adjacent", "pep_exposure"],
        "risk_scores": {"source_of_wealth": 9.0, "document_consistency": 3.0,
                        "counterparty_opacity": 8.5, "relationship_novelty": 7.0},
        "verdict": "escalated",
        "rationale": "Senior Russian official in originator UBO chain. Transaction volume exceeds 6-month average by 800%. Escalated to senior compliance officer pending geopolitical assessment.",
        "geopolitical_snapshot": {"RU": GEO["RU"], "CY": GEO["CY"]},
    },
    # ── Cluster 2: trade_based_ml — BLOCKED ────────────────────────────────────
    {
        "transaction_id": "HIST-CN-TRAD-BLK-001",
        "amount": 620000, "currency": "USD",
        "value_date": "2025-04-15", "product_type": "trade_finance", "direction": "outbound",
        "originator":  {"entity_name": "Shenzhen Tech Exports Ltd",  "country": "CN", "opacity": 0.44},
        "beneficiary": {"entity_name": "AE Receiving Corp.",          "country": "AE", "opacity": 0.68},
        "tenure_days": 22, "first_txn": True, "referral_origin": "cold_contact",
        "typology_tags": ["trade_based_ml", "sanctions_adjacent"],
        "risk_scores": {"source_of_wealth": 6.5, "document_consistency": 3.8,
                        "counterparty_opacity": 7.2, "relationship_novelty": 8.5},
        "verdict": "blocked",
        "rationale": "Invoice amount exceeds comparable market value by 3.2x. Goods description inconsistent with declared HS code. Classic over-invoicing trade-based ML pattern.",
        "trade_context": {
            "goods_description": "Electronic components — capacitors and resistors (industrial grade)",
            "hs_code": "8532.10",
            "dual_use_flag": False,
            "invoice_amount": 620000,
            "shipment_country": "AE",
        },
        "geopolitical_snapshot": {"CN": GEO["CN"], "AE": GEO["AE"]},
    },
    {
        "transaction_id": "HIST-PK-TRAD-BLK-001",
        "amount": 310000, "currency": "USD",
        "value_date": "2025-05-01", "product_type": "trade_finance", "direction": "outbound",
        "originator":  {"entity_name": "Karachi Export House Ltd",   "country": "PK", "opacity": 0.55},
        "beneficiary": {"entity_name": "Gulf Distribution FZCO",     "country": "AE", "opacity": 0.62},
        "tenure_days": 8, "first_txn": True, "referral_origin": "cold_contact",
        "typology_tags": ["trade_based_ml", "structuring"],
        "risk_scores": {"source_of_wealth": 7.0, "document_consistency": 4.2,
                        "counterparty_opacity": 6.8, "relationship_novelty": 9.0},
        "verdict": "blocked",
        "rationale": "Under-invoiced textile shipment to free zone entity. Volume in first week of relationship inconsistent with trade onboarding. Structuring across 5 sub-250k tranches detected.",
        "trade_context": {
            "goods_description": "Cotton garments — mixed lot",
            "hs_code": "6201.20",
            "dual_use_flag": False,
            "invoice_amount": 310000,
            "shipment_country": "AE",
        },
        "geopolitical_snapshot": {"PK": GEO["PK"], "AE": GEO["AE"]},
    },
    # ── Cluster 2 CONTRADICTION: trade_based_ml APPROVED ───────────────────────
    {
        "transaction_id": "HIST-CN-TRAD-APR-001",
        "amount": 780000, "currency": "USD",
        "value_date": "2025-02-20", "product_type": "trade_finance", "direction": "outbound",
        "originator":  {"entity_name": "Guangdong Precision Parts",  "country": "CN", "opacity": 0.29},
        "beneficiary": {"entity_name": "Munich Industrial GmbH",      "country": "DE", "opacity": 0.15},
        "tenure_days": 880, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["trade_based_ml", "sanctions_adjacent"],
        "risk_scores": {"source_of_wealth": 2.5, "document_consistency": 8.8,
                        "counterparty_opacity": 2.0, "relationship_novelty": 1.5},
        "verdict": "approved",
        "rationale": "Trade-based ML flag triggered by corridor risk. Third-party pricing review confirms invoice within 5% of market benchmark. Full bill of lading and letter of credit verified. Long-standing approved relationship.",
        "trade_context": {
            "goods_description": "CNC machined aluminium parts — automotive supply chain",
            "hs_code": "8708.99",
            "dual_use_flag": False,
            "invoice_amount": 780000,
            "shipment_country": "DE",
        },
        "geopolitical_snapshot": {"CN": GEO["CN"], "DE": GEO["DE"]},
    },
    {
        "transaction_id": "HIST-NG-TRAD-APR-001",
        "amount": 195000, "currency": "USD",
        "value_date": "2025-01-30", "product_type": "trade_finance", "direction": "inbound",
        "originator":  {"entity_name": "Lagos Agricultural Export Co.", "country": "NG", "opacity": 0.38},
        "beneficiary": {"entity_name": "London Commodities Ltd",        "country": "GB", "opacity": 0.21},
        "tenure_days": 540, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["trade_based_ml"],
        "risk_scores": {"source_of_wealth": 3.0, "document_consistency": 7.5,
                        "counterparty_opacity": 3.5, "relationship_novelty": 2.0},
        "verdict": "approved",
        "rationale": "Nigerian corridor flag cleared after commodity pricing review. Cocoa export valued within ICCO benchmark. Full export documentation matches declared volume. Approved.",
        "trade_context": {
            "goods_description": "Raw cocoa beans — certified origin",
            "hs_code": "1801.00",
            "dual_use_flag": False,
            "invoice_amount": 195000,
            "shipment_country": "GB",
        },
        "geopolitical_snapshot": {"NG": GEO["NG"], "GB": GEO["GB"]},
    },
    # ── Cluster 3: pep_exposure ─────────────────────────────────────────────────
    {
        "transaction_id": "HIST-ML-PEP-BLK-001",
        "amount": 430000, "currency": "EUR",
        "value_date": "2025-04-08", "product_type": "wire_transfer", "direction": "inbound",
        "originator":  {"entity_name": "Bamako Regional Finance SA",  "country": "ML", "opacity": 0.81, "is_pep": True},
        "beneficiary": {"entity_name": "Nicosia Real Estate Trust",   "country": "CY", "opacity": 0.70},
        "tenure_days": 5, "first_txn": True, "referral_origin": "cold_contact",
        "typology_tags": ["pep_exposure", "real_estate"],
        "risk_scores": {"source_of_wealth": 9.2, "document_consistency": 2.1,
                        "counterparty_opacity": 8.8, "relationship_novelty": 9.8},
        "verdict": "blocked",
        "rationale": "Mali cabinet minister in originator UBO. Real estate acquisition via Cypriot nominee trust. No legitimate income source documented. FATF blacklist jurisdiction of origin.",
        "geopolitical_snapshot": {"ML": GEO["ML"], "CY": GEO["CY"]},
    },
    {
        "transaction_id": "HIST-AE-PEP-APR-001",
        "amount": 600000, "currency": "USD",
        "value_date": "2025-03-03", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Abu Dhabi Sovereign Capital",  "country": "AE", "opacity": 0.15, "is_pep": True},
        "beneficiary": {"entity_name": "Zurich Private Equity AG",     "country": "CH", "opacity": 0.18},
        "tenure_days": 1460, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["pep_exposure"],
        "risk_scores": {"source_of_wealth": 1.5, "document_consistency": 9.2,
                        "counterparty_opacity": 1.8, "relationship_novelty": 1.0},
        "verdict": "approved",
        "rationale": "PEP flag triggered by government-affiliated beneficial owner. Enhanced due diligence completed: source of wealth is UAE sovereign investment mandate. Fully documented. 4-year established relationship with no adverse history.",
        "geopolitical_snapshot": {"AE": GEO["AE"], "CH": GEO["CH"]},
    },
    # ── Cluster 4: crypto_layering ──────────────────────────────────────────────
    {
        "transaction_id": "HIST-CRYPTO-BLK-001",
        "amount": 75000, "currency": "USDT",
        "value_date": "2025-05-10", "product_type": "crypto", "direction": "outbound",
        "originator":  {"entity_name": "Anonymous Wallet Cluster A",  "country": "RU", "opacity": 0.92},
        "beneficiary": {"entity_name": "AE Exchange Desk FZCO",       "country": "AE", "opacity": 0.75},
        "tenure_days": 1, "first_txn": True, "referral_origin": "unknown",
        "typology_tags": ["crypto_layering", "sanctions_adjacent"],
        "risk_scores": {"source_of_wealth": 9.5, "document_consistency": 1.0,
                        "counterparty_opacity": 9.8, "relationship_novelty": 9.9},
        "verdict": "blocked",
        "rationale": "TRON USDT chain-hop through 4 intermediate wallets. Source address 2 hops from OFAC SDN wallet. UAE unregulated exchange as exit ramp. Classic crypto peel-chain pattern.",
        "geopolitical_snapshot": {"RU": GEO["RU"], "AE": GEO["AE"]},
    },
    {
        "transaction_id": "HIST-CRYPTO-APR-001",
        "amount": 52000, "currency": "USDT",
        "value_date": "2025-01-25", "product_type": "crypto", "direction": "inbound",
        "originator":  {"entity_name": "Coinbase Institutional",      "country": "US", "opacity": 0.05},
        "beneficiary": {"entity_name": "DeFi Yield Fund Ltd",         "country": "GB", "opacity": 0.28},
        "tenure_days": 200, "first_txn": False, "referral_origin": "platform",
        "typology_tags": ["crypto_layering"],
        "risk_scores": {"source_of_wealth": 2.0, "document_consistency": 8.0,
                        "counterparty_opacity": 3.5, "relationship_novelty": 3.0},
        "verdict": "approved",
        "rationale": "Crypto layering signal triggered by multi-hop chain. Source verified as regulated US exchange with full KYC. On-chain analytics clear. MiCA compliance check passed. Approved.",
        "geopolitical_snapshot": {"US": {"FATF_status": "compliant", "basel_aml_index_score": 2.8,
                                         "active_sanctions_programs": [], "export_control_alerts": []},
                                   "GB": GEO["GB"]},
    },
    # ── Cluster 5: correspondent_risk ──────────────────────────────────────────
    {
        "transaction_id": "HIST-ML-CORR-BLK-001",
        "amount": 2800000, "currency": "USD",
        "value_date": "2025-04-20", "product_type": "wire_transfer", "direction": "inbound",
        "originator":  {"entity_name": "Banque Régionale du Sahel",   "country": "ML", "opacity": 0.77},
        "beneficiary": {"entity_name": "London Correspondent Bank",   "country": "GB", "opacity": 0.20},
        "tenure_days": 120, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["correspondent_risk", "sanctions_adjacent"],
        "risk_scores": {"source_of_wealth": 8.2, "document_consistency": 3.5,
                        "counterparty_opacity": 7.8, "relationship_novelty": 5.0},
        "verdict": "blocked",
        "rationale": "Correspondent banking relationship with Mali institution. FATF blacklisted jurisdiction. Volume spike 400% above baseline. Nostro reconciliation gap flagged. Blocked pending CBN notification.",
        "geopolitical_snapshot": {"ML": GEO["ML"], "GB": GEO["GB"]},
    },
    {
        "transaction_id": "HIST-NG-CORR-ESC-001",
        "amount": 1500000, "currency": "USD",
        "value_date": "2025-02-28", "product_type": "wire_transfer", "direction": "inbound",
        "originator":  {"entity_name": "First Bank of Nigeria PLC",   "country": "NG", "opacity": 0.35},
        "beneficiary": {"entity_name": "Standard Correspondent Bank", "country": "GB", "opacity": 0.15},
        "tenure_days": 730, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["correspondent_risk"],
        "risk_scores": {"source_of_wealth": 4.5, "document_consistency": 6.5,
                        "counterparty_opacity": 4.0, "relationship_novelty": 2.5},
        "verdict": "escalated",
        "rationale": "Nigerian FATF greylisted correspondent. Volume within historical range but single transaction size triggers EDD. Escalated for senior sign-off per correspondent banking policy.",
        "geopolitical_snapshot": {"NG": GEO["NG"], "GB": GEO["GB"]},
    },
    # ── Cluster 6: real_estate ──────────────────────────────────────────────────
    {
        "transaction_id": "HIST-CY-RE-BLK-001",
        "amount": 4200000, "currency": "EUR",
        "value_date": "2025-03-18", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Paphos Nominee Holdings Ltd", "country": "CY", "opacity": 0.88},
        "beneficiary": {"entity_name": "Valletta Property Trust",     "country": "MT",
                        "opacity": 0.82, "reg_age": 30},
        "tenure_days": 3, "first_txn": True, "referral_origin": "cold_contact",
        "typology_tags": ["real_estate", "layering"],
        "risk_scores": {"source_of_wealth": 9.0, "document_consistency": 2.5,
                        "counterparty_opacity": 9.5, "relationship_novelty": 9.8},
        "verdict": "blocked",
        "rationale": "Cross-border real estate acquisition through freshly incorporated nominee entities in two EU jurisdictions. No UBO identified. Price 35% above market value — classic RE over-valuation ML typology.",
        "geopolitical_snapshot": {"CY": GEO["CY"],
                                   "MT": {"FATF_status": "compliant", "basel_aml_index_score": 4.2,
                                          "active_sanctions_programs": [], "export_control_alerts": []}},
    },
    # ── Cluster 7: unknown / low-risk — APPROVED (for NO_MATCH cases to find) ──
    {
        "transaction_id": "HIST-DE-CLEAN-001",
        "amount": 85000, "currency": "EUR",
        "value_date": "2025-04-30", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Berlin Software GmbH",        "country": "DE", "opacity": 0.08},
        "beneficiary": {"entity_name": "Amsterdam Tech BV",           "country": "NL", "opacity": 0.10},
        "tenure_days": 900, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["unknown"],
        "risk_scores": {"source_of_wealth": 1.5, "document_consistency": 9.5,
                        "counterparty_opacity": 1.2, "relationship_novelty": 1.0},
        "verdict": "approved",
        "rationale": "Routine B2B payment between established EU entities. Full KYB on file. No adverse signals. Approved per standard STP criteria.",
        "geopolitical_snapshot": {"DE": GEO["DE"],
                                   "NL": {"FATF_status": "compliant", "basel_aml_index_score": 3.1,
                                          "active_sanctions_programs": [], "export_control_alerts": []}},
    },
    {
        "transaction_id": "HIST-GB-CLEAN-001",
        "amount": 220000, "currency": "GBP",
        "value_date": "2025-05-05", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Edinburgh Asset Management",  "country": "GB", "opacity": 0.12},
        "beneficiary": {"entity_name": "Dublin Fund Services Ltd",    "country": "IE", "opacity": 0.15},
        "tenure_days": 1200, "first_txn": False, "referral_origin": "existing_relationship",
        "typology_tags": ["unknown"],
        "risk_scores": {"source_of_wealth": 1.8, "document_consistency": 9.0,
                        "counterparty_opacity": 1.5, "relationship_novelty": 1.0},
        "verdict": "approved",
        "rationale": "FCA-regulated fund-to-fund transfer. Both entities are authorised and verified. Full documentation on file. Standard STP approval.",
        "geopolitical_snapshot": {"GB": GEO["GB"],
                                   "IE": {"FATF_status": "compliant", "basel_aml_index_score": 2.7,
                                          "active_sanctions_programs": [], "export_control_alerts": []}},
    },
    # ── Cluster 8: structuring — focused cases ──────────────────────────────────
    {
        "transaction_id": "HIST-PA-STRUCT-BLK-001",
        "amount": 199500, "currency": "USD",
        "value_date": "2025-03-25", "product_type": "wire_transfer", "direction": "outbound",
        "originator":  {"entity_name": "Panama City Holdings Corp.",  "country": "PA", "opacity": 0.79},
        "beneficiary": {"entity_name": "Belize Nominee Trust Ltd",    "country": "BZ", "opacity": 0.90, "reg_age": 14},
        "tenure_days": 7, "first_txn": True, "referral_origin": "cold_contact",
        "typology_tags": ["structuring", "layering"],
        "risk_scores": {"source_of_wealth": 8.8, "document_consistency": 2.8,
                        "counterparty_opacity": 9.2, "relationship_novelty": 9.7},
        "verdict": "blocked",
        "rationale": "Amount deliberately set $500 below USD 200k Fincen CTR threshold. Series of 6 identical tranches in 72 hours. Classic smurfing structuring pattern. Offshore shell beneficiary with no business purpose.",
        "geopolitical_snapshot": {"PA": GEO["PA"],
                                   "BZ": {"FATF_status": "monitored", "basel_aml_index_score": 5.8,
                                          "active_sanctions_programs": [], "export_control_alerts": []}},
    },
    {
        "transaction_id": "HIST-TR-STRUCT-ESC-001",
        "amount": 175000, "currency": "USD",
        "value_date": "2025-04-12", "product_type": "wire_transfer", "direction": "inbound",
        "originator":  {"entity_name": "Istanbul Trade Finance AS",   "country": "TR", "opacity": 0.52},
        "beneficiary": {"entity_name": "Vienna Clearing Bank AG",     "country": "AT", "opacity": 0.25},
        "tenure_days": 65, "first_txn": False, "referral_origin": "platform",
        "typology_tags": ["structuring", "sanctions_adjacent"],
        "risk_scores": {"source_of_wealth": 6.5, "document_consistency": 5.5,
                        "counterparty_opacity": 6.0, "relationship_novelty": 5.5},
        "verdict": "escalated",
        "rationale": "FATF-greylisted Turkish originator. Amount below EUR 200k reporting threshold but part of a series. Escalated for enhanced monitoring pending MASAK assessment.",
        "geopolitical_snapshot": {"TR": GEO["TR"],
                                   "AT": {"FATF_status": "compliant", "basel_aml_index_score": 3.3,
                                          "active_sanctions_programs": [], "export_control_alerts": []}},
    },
]


async def seed(api_url: str) -> None:
    submit_url = f"{api_url}/api/cases/submit"
    ok = err = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for case in CASES:
            tid = case["transaction_id"]
            try:
                xml_str = _build_xml(case)
                r = await client.post(submit_url, json={"transaction_id": tid, "case_xml": xml_str})
                if r.status_code in (200, 201):
                    resp = r.json()
                    print(f"  OK   {tid}  ({case['verdict']})  tags={case['typology_tags']}  → id={resp.get('case_id','?')[:8]}…")
                    ok += 1
                else:
                    print(f"  ERR  {tid} → HTTP {r.status_code}: {r.text[:150]}", file=sys.stderr)
                    err += 1
            except Exception as exc:
                print(f"  EXC  {tid} → {exc}", file=sys.stderr)
                err += 1

    print(f"\nDone: {ok} seeded, {err} errors.")
    if err:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Postgres challenge DB with historical AML precedents")
    parser.add_argument("--api", default="http://localhost:8001", help="Screening API base URL")
    args = parser.parse_args()
    asyncio.run(seed(args.api))


if __name__ == "__main__":
    main()
