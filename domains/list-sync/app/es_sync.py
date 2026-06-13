"""Zero-downtime Elasticsearch index sync via staging-index + alias swap.

Each sync writes the full entity set to a fresh per-list index, validates
the entry count against the previous live index (reject if below
`min_entry_count_ratio` — likely a parsing error, not a real list shrink),
then atomically repoints the shared alias and removes stale indices for
that list.
"""
from __future__ import annotations

from app.config import settings
from app.models import CanonicalSanctionsEntity, SanctionsList


def staging_index_name(list_name: SanctionsList, generation: int) -> str:
    return f"{settings.sanctions_index_alias}_{list_name.value.lower()}_{generation:020d}"


def _entity_doc(entity: CanonicalSanctionsEntity) -> dict:
    return {
        "_id": entity.key,
        **entity.model_dump(mode="json"),
        "content_hash": entity.content_hash(),
    }


class ESSyncManager:
    def __init__(self, es_client):
        self._es = es_client

    def current_entry_count(self, list_name: SanctionsList) -> int:
        alias = settings.sanctions_index_alias
        if not self._es.indices.exists_alias(name=alias):
            return 0

        count = 0
        for index_name in self._es.indices.get_alias(name=alias):
            if index_name.startswith(f"{alias}_{list_name.value.lower()}_"):
                response = self._es.count(index=index_name, query={"match_all": {}})
                count += response["count"]
        return count

    def index_entities(self, list_name: SanctionsList, entities: list[CanonicalSanctionsEntity], generation: int) -> str:
        index_name = staging_index_name(list_name, generation)
        self._es.indices.create(index=index_name, ignore=400)

        for entity in entities:
            self._es.index(index=index_name, id=entity.key, document=_entity_doc(entity))
        self._es.indices.refresh(index=index_name)
        return index_name

    @staticmethod
    def validate(new_count: int, previous_count: int) -> bool:
        if previous_count == 0:
            return new_count > 0
        return new_count >= previous_count * settings.min_entry_count_ratio

    def swap_alias(self, list_name: SanctionsList, new_index: str) -> None:
        alias = settings.sanctions_index_alias
        prefix = f"{alias}_{list_name.value.lower()}_"

        actions = [{"add": {"index": new_index, "alias": alias}}]
        stale_indices: list[str] = []

        if self._es.indices.exists_alias(name=alias):
            for index_name in self._es.indices.get_alias(name=alias):
                if index_name.startswith(prefix) and index_name != new_index:
                    actions.append({"remove": {"index": index_name, "alias": alias}})
                    stale_indices.append(index_name)

        self._es.indices.update_aliases(actions=actions)

        for index_name in stale_indices:
            self._es.indices.delete(index=index_name, ignore=[404])
