from app.models import SanctionsEntityType, SanctionsList
from app.sources.ofsi import parse_ofsi

SAMPLE_CSV = (
    "Group ID,Group Type,Name 6,Alias Type,Country,Regime,Address Line 1,Town\r\n"
    "1,Individual,John Smith,Primary name,Russia,RUSSIA,,\r\n"
    "1,Individual,Johnny Smith,AKA,Russia,RUSSIA,,\r\n"
    "2,Entity,Acme Corp,Primary name,Belarus,BELARUS,1 Main St,Minsk\r\n"
)


def test_groups_rows_by_group_id():
    entities = parse_ofsi(SAMPLE_CSV)
    assert len(entities) == 2

    individual = entities[0]
    assert individual.source_list == SanctionsList.OFSI_CONSOLIDATED
    assert individual.source_id == "1"
    assert individual.entity_type == SanctionsEntityType.INDIVIDUAL
    assert individual.primary_name == "John Smith"
    assert individual.aliases == ["Johnny Smith"]
    assert individual.programs == ["RUSSIA"]
    assert individual.country == "Russia"


def test_entity_with_address():
    entities = parse_ofsi(SAMPLE_CSV)
    entity = entities[1]
    assert entity.source_id == "2"
    assert entity.entity_type == SanctionsEntityType.ENTITY
    assert entity.primary_name == "Acme Corp"
    assert entity.country == "Belarus"
    assert entity.addresses
    assert entity.addresses[0].country == "Belarus"
