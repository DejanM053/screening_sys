from app.config import settings
from app.es_sync import ESSyncManager, staging_index_name
from app.models import SanctionsList


def test_validate_accepts_growth_and_minor_shrink_within_ratio():
    # previous=100, min_entry_count_ratio=0.95 -> threshold 95
    assert ESSyncManager.validate(new_count=120, previous_count=100) is True
    assert ESSyncManager.validate(new_count=95, previous_count=100) is True


def test_validate_rejects_drop_below_ratio():
    assert ESSyncManager.validate(new_count=94, previous_count=100) is False
    assert ESSyncManager.validate(new_count=0, previous_count=100) is False


def test_validate_accepts_first_ever_nonempty_sync():
    assert ESSyncManager.validate(new_count=10, previous_count=0) is True
    assert ESSyncManager.validate(new_count=0, previous_count=0) is False


def test_staging_index_name_is_namespaced_per_list_and_generation():
    name_a = staging_index_name(SanctionsList.OFAC_SDN, 1)
    name_b = staging_index_name(SanctionsList.OFAC_SDN, 2)
    name_c = staging_index_name(SanctionsList.EU_CONSOLIDATED, 1)

    assert name_a.startswith(settings.sanctions_index_alias)
    assert "ofac_sdn" in name_a
    assert name_a != name_b
    assert "eu_consolidated" in name_c


class _FakeIndicesClient:
    def __init__(self):
        self.aliases: dict[str, set[str]] = {}
        self.created: set[str] = set()
        self.deleted: set[str] = set()
        self.docs: dict[str, dict] = {}

    def exists_alias(self, name):
        return name in self.aliases and bool(self.aliases[name])

    def get_alias(self, name):
        return {index: {} for index in self.aliases.get(name, set())}

    def create(self, index, ignore=None):
        self.created.add(index)

    def refresh(self, index):
        pass

    def update_aliases(self, actions):
        for action in actions:
            if "add" in action:
                alias = action["add"]["alias"]
                index = action["add"]["index"]
                self.aliases.setdefault(alias, set()).add(index)
            elif "remove" in action:
                alias = action["remove"]["alias"]
                index = action["remove"]["index"]
                self.aliases.setdefault(alias, set()).discard(index)

    def delete(self, index, ignore=None):
        self.deleted.add(index)


class _FakeESClient:
    def __init__(self):
        self.indices = _FakeIndicesClient()
        self._docs: dict[str, list[dict]] = {}

    def index(self, index, id, document):
        self._docs.setdefault(index, []).append(document)

    def count(self, index, query):
        return {"count": len(self._docs.get(index, []))}


def test_swap_alias_repoints_and_removes_stale_index():
    client = _FakeESClient()
    manager = ESSyncManager(client)

    old_index = staging_index_name(SanctionsList.OFAC_SDN, 1)
    client.indices.create(index=old_index)
    client.indices.update_aliases(actions=[{"add": {"index": old_index, "alias": settings.sanctions_index_alias}}])

    new_index = staging_index_name(SanctionsList.OFAC_SDN, 2)
    client.indices.create(index=new_index)
    manager.swap_alias(SanctionsList.OFAC_SDN, new_index)

    alias_indices = set(client.indices.get_alias(name=settings.sanctions_index_alias))
    assert alias_indices == {new_index}
    assert old_index in client.indices.deleted


def test_index_entities_writes_docs_and_returns_index_name():
    from app.models import CanonicalSanctionsEntity, SanctionsEntityType

    client = _FakeESClient()
    manager = ESSyncManager(client)

    entities = [
        CanonicalSanctionsEntity(
            source_list=SanctionsList.OFAC_SDN,
            source_id="1",
            entity_type=SanctionsEntityType.INDIVIDUAL,
            primary_name="Alice",
        )
    ]

    index_name = manager.index_entities(SanctionsList.OFAC_SDN, entities, generation=1)
    assert index_name == staging_index_name(SanctionsList.OFAC_SDN, 1)
    assert len(client._docs[index_name]) == 1
    assert client._docs[index_name][0]["_id"] == "OFAC_SDN:1"
