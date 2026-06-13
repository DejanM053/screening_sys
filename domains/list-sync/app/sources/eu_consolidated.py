"""EU Consolidated Financial Sanctions List XML parser (FSF format).

Each `sanctionEntity` carries a `subjectType` (P = person, E = entity/vessel/
aircraft), one or more `nameAlias` elements (multilingual; the "strong"
variant is treated as the primary name), `address`/`identification` children,
and `remark` text used as narrative.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from app.models import Address, CanonicalSanctionsEntity, Identification, SanctionsEntityType, SanctionsList
from app.sources.xml_utils import direct_children_local, local_tag

_SUBJECT_TYPE_MAP = {
    "P": SanctionsEntityType.INDIVIDUAL,
    "E": SanctionsEntityType.ENTITY,
    "V": SanctionsEntityType.VESSEL,
    "A": SanctionsEntityType.AIRCRAFT,
}


def _name_alias_text(alias: ET.Element) -> str | None:
    whole_name = alias.attrib.get("wholeName")
    if whole_name:
        return whole_name.strip() or None
    parts = [alias.attrib.get(part) for part in ("titlePrefix", "firstName", "middleName", "lastName")]
    parts = [p.strip() for p in parts if p and p.strip()]
    return " ".join(parts) if parts else None


def parse_eu_consolidated(xml_bytes: bytes) -> list[CanonicalSanctionsEntity]:
    root = ET.fromstring(xml_bytes)
    entities: list[CanonicalSanctionsEntity] = []

    for entity_el in [el for el in root.iter() if local_tag(el) == "sanctionEntity"]:
        source_id = entity_el.attrib.get("logicalId") or entity_el.attrib.get("euReferenceNumber")
        if source_id is None:
            continue

        subject_type_code = None
        for subject_type_el in direct_children_local(entity_el, "subjectType"):
            subject_type_code = subject_type_el.attrib.get("code")
        entity_type = _SUBJECT_TYPE_MAP.get((subject_type_code or "").upper(), SanctionsEntityType.ENTITY)

        primary_name: str | None = None
        aliases: list[str] = []
        for alias_el in direct_children_local(entity_el, "nameAlias"):
            name = _name_alias_text(alias_el)
            if name is None:
                continue
            if primary_name is None and alias_el.attrib.get("strong", "").lower() == "true":
                primary_name = name
            else:
                aliases.append(name)

        if primary_name is None and aliases:
            primary_name = aliases.pop(0)
        if primary_name is None:
            continue

        addresses: list[Address] = []
        country: str | None = None
        for address_el in direct_children_local(entity_el, "address"):
            addr_country = address_el.attrib.get("countryIso2Code") or address_el.attrib.get("country")
            parts = [address_el.attrib.get(part) for part in ("street", "city", "zipCode")]
            full_address = ", ".join(p for p in parts if p) or None
            if addr_country and country is None:
                country = addr_country
            if addr_country or full_address:
                addresses.append(Address(country=addr_country, full_address=full_address))

        if country is None:
            for citizenship_el in direct_children_local(entity_el, "citizenship"):
                code = citizenship_el.attrib.get("countryIso2Code")
                if code:
                    country = code
                    break

        identification: list[Identification] = []
        for id_el in direct_children_local(entity_el, "identification"):
            identification.append(
                Identification(
                    id_type=id_el.attrib.get("identificationTypeCode") or id_el.attrib.get("type"),
                    id_number=id_el.attrib.get("number"),
                    country=id_el.attrib.get("countryIso2Code"),
                )
            )

        programs: list[str] = []
        for regulation_el in direct_children_local(entity_el, "regulation"):
            programme = regulation_el.attrib.get("programme")
            if programme and programme not in programs:
                programs.append(programme)

        narrative_parts = [
            (remark_el.text or "").strip() for remark_el in direct_children_local(entity_el, "remark")
        ]
        narrative_parts = [p for p in narrative_parts if p]
        narrative = " ".join(narrative_parts) or None

        entities.append(
            CanonicalSanctionsEntity(
                source_list=SanctionsList.EU_CONSOLIDATED,
                source_id=source_id,
                entity_type=entity_type,
                primary_name=primary_name,
                aliases=aliases,
                addresses=addresses,
                identification=identification,
                programs=programs,
                narrative=narrative,
                country=country,
            )
        )

    return entities
