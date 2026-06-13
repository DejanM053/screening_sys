"""Delta detection between two snapshots of a sanctions list (Section CC-07)."""
from __future__ import annotations

from app.models import CanonicalSanctionsEntity, DiffResult, SanctionsList


class DiffEngine:
    @staticmethod
    def diff(
        list_name: SanctionsList,
        previous: list[CanonicalSanctionsEntity],
        current: list[CanonicalSanctionsEntity],
    ) -> DiffResult:
        previous_by_key = {entity.key: entity for entity in previous}
        current_by_key = {entity.key: entity for entity in current}

        added = [entity for key, entity in current_by_key.items() if key not in previous_by_key]
        removed_keys = [key for key in previous_by_key if key not in current_by_key]

        modified = [
            current_by_key[key]
            for key in current_by_key
            if key in previous_by_key and current_by_key[key].content_hash() != previous_by_key[key].content_hash()
        ]

        return DiffResult(list_name=list_name, added=added, removed_keys=removed_keys, modified=modified)
