"""OpenSanctions PEP dataset parser (JSON Lines).

Each line is `{id, schema, caption, properties: {name, alias, country, topics, ...}}`.
Only records whose `properties.topics` includes a PEP-related topic
(e.g. "role.pep") are kept; PEPs are stored separately from sanctions lists
since they carry different risk weighting (Section 10 of CLAUDE.md).
"""
from __future__ import annotations

import json

from app.models import CanonicalSanctionsEntity, SanctionsEntityType, SanctionsList

_SCHEMA_TYPE_MAP = {
    "Person": SanctionsEntityType.INDIVIDUAL,
    "Organization": SanctionsEntityType.ENTITY,
    "Company": SanctionsEntityType.ENTITY,
    "LegalEntity": SanctionsEntityType.ENTITY,
}


def _first(values: list) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_pep_list(jsonl_text: str) -> list[CanonicalSanctionsEntity]:
    entities: list[CanonicalSanctionsEntity] = []

    for line in jsonl_text.splitlines():
        line = line.strip()
        if not line:
            continue

        record = json.loads(line)
        properties = record.get("properties", {}) or {}

        topics = properties.get("topics", []) or []
        if not any(str(topic).startswith("role.pep") for topic in topics):
            continue

        source_id = record.get("id")
        if not source_id:
            continue

        primary_name = _first(properties.get("name", [])) or record.get("caption")
        if not primary_name:
            continue

        aliases = [name for name in properties.get("alias", []) if isinstance(name, str)]
        country = _first(properties.get("country", []))

        entity_type = _SCHEMA_TYPE_MAP.get(record.get("schema"), SanctionsEntityType.INDIVIDUAL)

        entities.append(
            CanonicalSanctionsEntity(
                source_list=SanctionsList.PEP,
                source_id=source_id,
                entity_type=entity_type,
                primary_name=primary_name,
                aliases=aliases,
                programs=["PEP"],
                country=country,
                raw={"topics": topics},
            )
        )

    return entities
