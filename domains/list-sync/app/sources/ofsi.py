"""UK OFSI Consolidated List CSV parser (ConList.csv).

The OFSI feed groups multiple rows under a shared "Group ID" — one row per
name/alias variant. Rows are aggregated per group into a single
CanonicalSanctionsEntity, with the "Primary name" row supplying the
primary_name and remaining rows contributing aliases.
"""
from __future__ import annotations

import csv
import io

from app.models import Address, CanonicalSanctionsEntity, Identification, SanctionsEntityType, SanctionsList

_ENTITY_TYPE_MAP = {
    "individual": SanctionsEntityType.INDIVIDUAL,
    "entity": SanctionsEntityType.ENTITY,
    "ship": SanctionsEntityType.VESSEL,
    "vessel": SanctionsEntityType.VESSEL,
    "aircraft": SanctionsEntityType.AIRCRAFT,
}

_NAME_FIELDS = ["Name 6", "Name 1", "Name 2", "Name 3", "Name 4", "Name 5"]


def _row_get(row: dict, *keys: str) -> str | None:
    for key in keys:
        for actual_key, value in row.items():
            if actual_key and actual_key.strip().lower() == key.lower():
                value = (value or "").strip()
                if value:
                    return value
    return None


def _build_name(row: dict) -> str | None:
    parts = [_row_get(row, name_field) for name_field in _NAME_FIELDS]
    parts = [p for p in parts if p]
    return " ".join(parts) if parts else None


def parse_ofsi(csv_text: str) -> list[CanonicalSanctionsEntity]:
    reader = csv.DictReader(io.StringIO(csv_text))

    groups: dict[str, dict] = {}
    order: list[str] = []

    for row in reader:
        group_id = _row_get(row, "Group ID", "Group Id", "GroupID")
        if group_id is None:
            continue

        name = _build_name(row)
        if name is None:
            continue

        if group_id not in groups:
            group_type = (_row_get(row, "Group Type") or "entity").lower()
            groups[group_id] = {
                "group_id": group_id,
                "entity_type": _ENTITY_TYPE_MAP.get(group_type, SanctionsEntityType.ENTITY),
                "primary_name": None,
                "aliases": [],
                "country": _row_get(row, "Country"),
                "programs": [],
                "identification": [],
                "addresses": [],
            }
            order.append(group_id)

        group = groups[group_id]

        name_type = (_row_get(row, "Alias Type", "Name Type") or "").lower()
        if group["primary_name"] is None and ("primary" in name_type or name_type == ""):
            group["primary_name"] = name
        else:
            group["aliases"].append(name)

        regime = _row_get(row, "Regime")
        if regime and regime not in group["programs"]:
            group["programs"].append(regime)

        country = _row_get(row, "Country")
        if country:
            address_text = _row_get(row, "Address Line 1", "Town", "County")
            if address_text or country:
                addr = Address(country=country, full_address=address_text)
                if addr not in group["addresses"]:
                    group["addresses"].append(addr)

        nin = _row_get(row, "Non-UK NIN", "National Identification Number")
        if nin:
            group["identification"].append(Identification(id_type="national_id", id_number=nin, country=country))

    entities: list[CanonicalSanctionsEntity] = []
    for group_id in order:
        group = groups[group_id]
        primary_name = group["primary_name"] or (group["aliases"].pop(0) if group["aliases"] else None)
        if primary_name is None:
            continue

        entities.append(
            CanonicalSanctionsEntity(
                source_list=SanctionsList.OFSI_CONSOLIDATED,
                source_id=group_id,
                entity_type=group["entity_type"],
                primary_name=primary_name,
                aliases=group["aliases"],
                addresses=group["addresses"],
                identification=group["identification"],
                programs=group["programs"],
                country=group["country"],
            )
        )

    return entities
