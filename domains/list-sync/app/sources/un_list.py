"""UN Security Council Consolidated List XML parser.

The feed has two top-level sections: `INDIVIDUALS/INDIVIDUAL` and
`ENTITIES/ENTITY`. Aliases come from `INDIVIDUAL_ALIAS`/`ENTITY_ALIAS`
children's `ALIAS_NAME`. `COMMENTS1` is preserved as narrative text for
downstream LLM processing.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from app.models import Address, CanonicalSanctionsEntity, SanctionsEntityType, SanctionsList
from app.sources.xml_utils import child_text, direct_children_local, local_tag


def _individual_name(record: ET.Element) -> str:
    parts = [
        child_text(record, tag)
        for tag in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")
    ]
    return " ".join(p for p in parts if p)


def _aliases(record: ET.Element, alias_tag: str) -> list[str]:
    aliases: list[str] = []
    for alias_el in direct_children_local(record, alias_tag):
        name = child_text(alias_el, "ALIAS_NAME")
        if name:
            aliases.append(name)
    return aliases


def _addresses_and_country(record: ET.Element, address_tag: str) -> tuple[list[Address], str | None]:
    addresses: list[Address] = []
    country: str | None = None
    for address_el in direct_children_local(record, address_tag):
        addr_country = child_text(address_el, "COUNTRY")
        parts = [child_text(address_el, tag) for tag in ("STREET", "CITY", "STATE_PROVINCE")]
        full_address = ", ".join(p for p in parts if p) or None
        if addr_country or full_address:
            addresses.append(Address(country=addr_country, full_address=full_address))
        if addr_country and country is None:
            country = addr_country
    return addresses, country


def parse_un_consolidated(xml_bytes: bytes) -> list[CanonicalSanctionsEntity]:
    root = ET.fromstring(xml_bytes)
    entities: list[CanonicalSanctionsEntity] = []

    for individuals_el in [el for el in root.iter() if local_tag(el) == "INDIVIDUALS"]:
        for record in direct_children_local(individuals_el, "INDIVIDUAL"):
            data_id = child_text(record, "DATAID")
            if data_id is None:
                continue

            primary_name = _individual_name(record)
            if not primary_name:
                continue

            addresses, country = _addresses_and_country(record, "INDIVIDUAL_ADDRESS")
            if country is None:
                for nationality_el in direct_children_local(record, "NATIONALITY"):
                    value = child_text(nationality_el, "VALUE")
                    if value:
                        country = value
                        break

            entities.append(
                CanonicalSanctionsEntity(
                    source_list=SanctionsList.UN_CONSOLIDATED,
                    source_id=data_id,
                    entity_type=SanctionsEntityType.INDIVIDUAL,
                    primary_name=primary_name,
                    aliases=_aliases(record, "INDIVIDUAL_ALIAS"),
                    addresses=addresses,
                    narrative=child_text(record, "COMMENTS1"),
                    country=country,
                )
            )

    for entities_el in [el for el in root.iter() if local_tag(el) == "ENTITIES"]:
        for record in direct_children_local(entities_el, "ENTITY"):
            data_id = child_text(record, "DATAID")
            if data_id is None:
                continue

            primary_name = child_text(record, "FIRST_NAME")
            if not primary_name:
                continue

            addresses, country = _addresses_and_country(record, "ENTITY_ADDRESS")

            entities.append(
                CanonicalSanctionsEntity(
                    source_list=SanctionsList.UN_CONSOLIDATED,
                    source_id=data_id,
                    entity_type=SanctionsEntityType.ENTITY,
                    primary_name=primary_name,
                    aliases=_aliases(record, "ENTITY_ALIAS"),
                    addresses=addresses,
                    narrative=child_text(record, "COMMENTS1"),
                    country=country,
                )
            )

    return entities
