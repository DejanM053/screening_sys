"""OFAC SDN XML parser (ofac.treasury.gov/ofac/downloads/sdn.xml).

Extracts SDN_ENTRY records, AKA aliases, addresses, identification numbers,
and crypto addresses published via FEATURE elements (Section 10.4).
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from app.models import Address, CanonicalSanctionsEntity, CryptoAddress, Identification, SanctionsEntityType, SanctionsList
from app.sources.xml_utils import child_text, direct_children_local, local_tag

# OFAC "Digital Currency Address - XXX" feature type suffixes -> canonical chain names
_CRYPTO_FEATURE_CHAINS = {
    "XBT": "bitcoin",
    "ETH": "ethereum",
    "LTC": "litecoin",
    "XMR": "monero",
    "BCH": "bitcoin-cash",
    "TRX": "tron",
    "USDT": "tron",
    "ZEC": "zcash",
    "DASH": "dash",
}

_ENTITY_TYPE_MAP = {
    "individual": SanctionsEntityType.INDIVIDUAL,
    "vessel": SanctionsEntityType.VESSEL,
    "aircraft": SanctionsEntityType.AIRCRAFT,
}


def parse_ofac_sdn(xml_bytes: bytes) -> list[CanonicalSanctionsEntity]:
    root = ET.fromstring(xml_bytes)
    entities: list[CanonicalSanctionsEntity] = []

    for sdn_entry in [el for el in root.iter() if local_tag(el) == "sdnEntry"]:
        uid = child_text(sdn_entry, "uid")
        if uid is None:
            continue

        first_name = child_text(sdn_entry, "firstName") or ""
        last_name = child_text(sdn_entry, "lastName") or ""
        primary_name = " ".join(part for part in (first_name, last_name) if part).strip() or last_name or first_name

        sdn_type = (child_text(sdn_entry, "sdnType") or "entity").strip().lower()
        entity_type = _ENTITY_TYPE_MAP.get(sdn_type, SanctionsEntityType.ENTITY)

        programs = [
            (program.text or "").strip()
            for program_list in direct_children_local(sdn_entry, "programList")
            for program in direct_children_local(program_list, "program")
        ]
        programs = [p for p in programs if p]

        aliases: list[str] = []
        for aka_list in direct_children_local(sdn_entry, "akaList"):
            for aka in direct_children_local(aka_list, "aka"):
                aka_first = child_text(aka, "firstName") or ""
                aka_last = child_text(aka, "lastName") or ""
                aka_name = " ".join(part for part in (aka_first, aka_last) if part).strip()
                if aka_name:
                    aliases.append(aka_name)

        addresses: list[Address] = []
        for address_list in direct_children_local(sdn_entry, "addressList"):
            for address in direct_children_local(address_list, "address"):
                country = child_text(address, "country")
                parts = [child_text(address, tag) for tag in ("address1", "address2", "address3", "city", "stateOrProvince", "postalCode")]
                full_address = ", ".join(p for p in parts if p) or None
                if country or full_address:
                    addresses.append(Address(country=country, full_address=full_address))

        identification: list[Identification] = []
        for id_list in direct_children_local(sdn_entry, "idList"):
            for id_el in direct_children_local(id_list, "id"):
                identification.append(
                    Identification(
                        id_type=child_text(id_el, "idType"),
                        id_number=child_text(id_el, "idNumber"),
                        country=child_text(id_el, "idCountry"),
                    )
                )

        crypto_addresses: list[CryptoAddress] = []
        for feature_list in direct_children_local(sdn_entry, "featureList"):
            for feature in direct_children_local(feature_list, "feature"):
                feature_type = child_text(feature, "type") or ""
                if "Digital Currency Address" not in feature_type:
                    continue
                code = feature_type.split("-")[-1].strip().upper()
                chain = _CRYPTO_FEATURE_CHAINS.get(code, code.lower())
                for version in direct_children_local(feature, "version"):
                    value = child_text(version, "value")
                    if value:
                        crypto_addresses.append(CryptoAddress(chain=chain, address=value))

        entities.append(
            CanonicalSanctionsEntity(
                source_list=SanctionsList.OFAC_SDN,
                source_id=uid,
                entity_type=entity_type,
                primary_name=primary_name,
                aliases=aliases,
                addresses=addresses,
                identification=identification,
                crypto_addresses=crypto_addresses,
                programs=programs,
                country=addresses[0].country if addresses else None,
            )
        )

    return entities
