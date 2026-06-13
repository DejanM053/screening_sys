from app.diff_engine import DiffEngine
from app.models import CanonicalSanctionsEntity, SanctionsEntityType, SanctionsList


def _entity(source_id: str, primary_name: str, **kwargs) -> CanonicalSanctionsEntity:
    return CanonicalSanctionsEntity(
        source_list=SanctionsList.OFAC_SDN,
        source_id=source_id,
        entity_type=SanctionsEntityType.INDIVIDUAL,
        primary_name=primary_name,
        **kwargs,
    )


def test_detects_added_and_removed():
    previous = [_entity("1", "Alice"), _entity("2", "Bob")]
    current = [_entity("1", "Alice"), _entity("3", "Carol")]

    diff = DiffEngine.diff(SanctionsList.OFAC_SDN, previous, current)

    assert [e.source_id for e in diff.added] == ["3"]
    assert diff.removed_keys == ["OFAC_SDN:2"]
    assert diff.modified == []
    assert diff.total_changes == 2


def test_detects_modified_via_content_hash():
    previous = [_entity("1", "Alice", aliases=["Ally"])]
    current = [_entity("1", "Alice", aliases=["Ally", "A. Smith"])]

    diff = DiffEngine.diff(SanctionsList.OFAC_SDN, previous, current)

    assert diff.added == []
    assert diff.removed_keys == []
    assert [e.source_id for e in diff.modified] == ["1"]


def test_no_changes_when_identical():
    entities = [_entity("1", "Alice"), _entity("2", "Bob")]
    diff = DiffEngine.diff(SanctionsList.OFAC_SDN, entities, entities)
    assert diff.total_changes == 0


def test_new_crypto_addresses_collected_from_added_and_modified():
    from app.models import CryptoAddress

    previous = [_entity("1", "Alice")]
    current = [
        _entity("1", "Alice", crypto_addresses=[CryptoAddress(chain="tron", address="TXalice")]),
        _entity("2", "Bob", crypto_addresses=[CryptoAddress(chain="bitcoin", address="1Bob")]),
    ]

    diff = DiffEngine.diff(SanctionsList.OFAC_SDN, previous, current)

    addresses = {c.address for c in diff.new_crypto_addresses}
    assert addresses == {"TXalice", "1Bob"}
