# Place at: domains/screening-api/app/challenge_xml.py
"""XML serialisation / deserialisation for AMLCaseXML.

Root element: <AMLCase>
Uses standard library xml.etree.ElementTree only.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from app.challenge_models import AMLCaseXML, CountryGeopoliticalContext, Party, TradeContext


# ─── Private helpers ──────────────────────────────────────────────────────────

def _sub(parent: ET.Element, tag: str, value: object = None) -> ET.Element:
    el = ET.SubElement(parent, tag)
    if value is not None:
        el.text = str(value)
    return el


def _sub_list(parent: ET.Element, wrapper: str, item_tag: str, values: list) -> ET.Element:
    w = ET.SubElement(parent, wrapper)
    for v in values:
        i = ET.SubElement(w, item_tag)
        i.text = str(v)
    return w


def _party_to_xml(parent: ET.Element, tag: str, party: Party) -> None:
    el = ET.SubElement(parent, tag)
    _sub(el, "entity_name", party.entity_name)
    _sub(el, "entity_type", party.entity_type)
    _sub(el, "country_of_incorporation", party.country_of_incorporation)
    _sub(el, "account_country", party.account_country)
    _sub(el, "registration_age_days", party.registration_age_days)
    _sub(el, "is_pep", str(party.is_pep).lower())
    _sub(el, "ownership_opacity_score", party.ownership_opacity_score)


def _party_from_xml(el: ET.Element) -> Party:
    return Party(
        entity_name=el.findtext("entity_name") or "",
        entity_type=el.findtext("entity_type") or "company",  # type: ignore[arg-type]
        country_of_incorporation=el.findtext("country_of_incorporation") or "",
        account_country=el.findtext("account_country") or "",
        registration_age_days=int(el.findtext("registration_age_days") or "0"),
        is_pep=(el.findtext("is_pep") or "").lower() == "true",
        ownership_opacity_score=float(el.findtext("ownership_opacity_score") or "0"),
    )


# ─── Public API ───────────────────────────────────────────────────────────────

def case_to_xml(case: AMLCaseXML) -> str:
    """Serialise an AMLCaseXML instance to a pretty-printed XML string."""
    root = ET.Element("AMLCase")

    # Transaction core
    txn = ET.SubElement(root, "TransactionCore")
    _sub(txn, "transaction_id", case.transaction_id)
    _sub(txn, "amount", case.amount)
    _sub(txn, "currency", case.currency)
    _sub(txn, "value_date", case.value_date)
    _sub(txn, "product_type", case.product_type)
    _sub(txn, "direction", case.direction)

    # Parties
    parties = ET.SubElement(root, "Parties")
    _party_to_xml(parties, "Originator", case.originator)
    _party_to_xml(parties, "Beneficiary", case.beneficiary)

    # Trade context
    tc_el = ET.SubElement(root, "TradeContext")
    if case.trade_context:
        tc_el.set("present", "true")
        _sub(tc_el, "goods_description", case.trade_context.goods_description)
        _sub(tc_el, "hs_code", case.trade_context.hs_code)
        _sub(tc_el, "dual_use_flag", str(case.trade_context.dual_use_flag).lower())
        _sub(tc_el, "invoice_amount", case.trade_context.invoice_amount)
        _sub(tc_el, "shipment_country", case.trade_context.shipment_country)
    else:
        tc_el.set("present", "false")

    # Relationship context
    rel = ET.SubElement(root, "RelationshipContext")
    _sub(rel, "relationship_tenure_days", case.relationship_tenure_days)
    _sub(rel, "first_transaction_to_counterparty", str(case.first_transaction_to_counterparty).lower())
    _sub(rel, "referral_origin", case.referral_origin)

    # Analyst assessment
    aa = ET.SubElement(root, "AnalystAssessment")
    _sub_list(aa, "TypologyTags", "tag", case.typology_tags)
    rs_el = ET.SubElement(aa, "RiskScores")
    for k, v in case.risk_scores.items():
        s = ET.SubElement(rs_el, "score")
        s.set("key", k)
        s.text = str(v)
    _sub(aa, "reviewer_verdict", case.reviewer_verdict)
    rationale_el = ET.SubElement(aa, "reviewer_rationale")
    rationale_el.text = case.reviewer_rationale

    # Geopolitical snapshot
    geo = ET.SubElement(root, "GeopoliticalSnapshot")
    for country_code, ctx in case.geopolitical_snapshot.items():
        cc_el = ET.SubElement(geo, "CountryContext")
        cc_el.set("country", country_code)
        _sub(cc_el, "FATF_status", ctx.FATF_status)
        _sub(cc_el, "basel_aml_index_score", ctx.basel_aml_index_score)
        _sub_list(cc_el, "ActiveSanctionsPrograms", "program", ctx.active_sanctions_programs)
        _sub_list(cc_el, "ExportControlAlerts", "alert", ctx.export_control_alerts)

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def xml_to_case(xml_string: str) -> AMLCaseXML:
    """Deserialise an XML string produced by case_to_xml back to AMLCaseXML."""
    root = ET.fromstring(xml_string)

    txn = root.find("TransactionCore")
    if txn is None:
        raise ValueError("Missing <TransactionCore>")

    parties = root.find("Parties")
    if parties is None:
        raise ValueError("Missing <Parties>")
    orig_el = parties.find("Originator")
    ben_el = parties.find("Beneficiary")
    if orig_el is None or ben_el is None:
        raise ValueError("Missing <Originator> or <Beneficiary>")

    # Trade context
    tc_el = root.find("TradeContext")
    trade_context: TradeContext | None = None
    if tc_el is not None and tc_el.get("present") == "true":
        inv_raw = tc_el.findtext("invoice_amount")
        trade_context = TradeContext(
            goods_description=tc_el.findtext("goods_description"),
            hs_code=tc_el.findtext("hs_code"),
            dual_use_flag=(tc_el.findtext("dual_use_flag") or "").lower() == "true",
            invoice_amount=float(inv_raw) if inv_raw else None,
            shipment_country=tc_el.findtext("shipment_country"),
        )

    rel = root.find("RelationshipContext")
    if rel is None:
        raise ValueError("Missing <RelationshipContext>")

    aa = root.find("AnalystAssessment")
    if aa is None:
        raise ValueError("Missing <AnalystAssessment>")

    tags_el = aa.find("TypologyTags")
    typology_tags = [t.text or "" for t in tags_el.findall("tag")] if tags_el is not None else []

    rs_el = aa.find("RiskScores")
    risk_scores: dict[str, float] = {}
    if rs_el is not None:
        for s in rs_el.findall("score"):
            k = s.get("key")
            if k:
                risk_scores[k] = float(s.text or "0")

    geo_el = root.find("GeopoliticalSnapshot")
    geopolitical_snapshot: dict[str, CountryGeopoliticalContext] = {}
    if geo_el is not None:
        for cc_el in geo_el.findall("CountryContext"):
            country = cc_el.get("country", "")
            progs_el = cc_el.find("ActiveSanctionsPrograms")
            programs = [p.text or "" for p in progs_el.findall("program")] if progs_el is not None else []
            alerts_el = cc_el.find("ExportControlAlerts")
            alerts = [a.text or "" for a in alerts_el.findall("alert")] if alerts_el is not None else []
            geopolitical_snapshot[country] = CountryGeopoliticalContext(
                FATF_status=cc_el.findtext("FATF_status") or "compliant",  # type: ignore[arg-type]
                basel_aml_index_score=float(cc_el.findtext("basel_aml_index_score") or "0"),
                active_sanctions_programs=programs,
                export_control_alerts=alerts,
            )

    return AMLCaseXML(
        transaction_id=txn.findtext("transaction_id") or "",
        amount=float(txn.findtext("amount") or "0"),
        currency=txn.findtext("currency") or "",
        value_date=txn.findtext("value_date") or "",
        product_type=txn.findtext("product_type") or "wire_transfer",  # type: ignore[arg-type]
        direction=txn.findtext("direction") or "outbound",  # type: ignore[arg-type]
        originator=_party_from_xml(orig_el),
        beneficiary=_party_from_xml(ben_el),
        trade_context=trade_context,
        relationship_tenure_days=int(rel.findtext("relationship_tenure_days") or "0"),
        first_transaction_to_counterparty=(rel.findtext("first_transaction_to_counterparty") or "").lower() == "true",
        referral_origin=rel.findtext("referral_origin") or "unknown",  # type: ignore[arg-type]
        typology_tags=typology_tags,
        risk_scores=risk_scores,
        reviewer_verdict=aa.findtext("reviewer_verdict") or "approved",  # type: ignore[arg-type]
        reviewer_rationale=aa.findtext("reviewer_rationale") or "",
        geopolitical_snapshot=geopolitical_snapshot,
    )
