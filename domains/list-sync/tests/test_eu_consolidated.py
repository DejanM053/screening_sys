from app.models import SanctionsEntityType, SanctionsList
from app.sources.eu_consolidated import parse_eu_consolidated

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<export>
  <sanctionEntity logicalId="EU-1001" euReferenceNumber="EU.1001">
    <subjectType code="P"/>
    <nameAlias firstName="Ivan" lastName="Petrov" wholeName="Ivan Petrov" lang="eng" strong="true"/>
    <nameAlias wholeName="Иван Петров" lang="rus" strong="false"/>
    <citizenship countryIso2Code="RU"/>
    <address city="Moscow" countryIso2Code="RU" street="Tverskaya 1" zipCode="125009"/>
    <identification identificationTypeCode="passport" number="A1234567" countryIso2Code="RU"/>
    <regulation programme="RUSSIA"/>
    <remark>Designated for involvement in sanctioned activity.</remark>
  </sanctionEntity>
  <sanctionEntity logicalId="EU-2002" euReferenceNumber="EU.2002">
    <subjectType code="E"/>
    <nameAlias wholeName="Aldgate Finance Services" lang="eng" strong="true"/>
    <address city="Nicosia" countryIso2Code="CY"/>
    <regulation programme="SYRIA"/>
  </sanctionEntity>
</export>
""".encode("utf-8")


def test_parses_individual_with_multilingual_aliases():
    entities = parse_eu_consolidated(SAMPLE_XML)
    assert len(entities) == 2

    individual = entities[0]
    assert individual.source_list == SanctionsList.EU_CONSOLIDATED
    assert individual.source_id == "EU-1001"
    assert individual.entity_type == SanctionsEntityType.INDIVIDUAL
    assert individual.primary_name == "Ivan Petrov"
    assert individual.aliases == ["Иван Петров"]
    assert individual.country == "RU"
    assert individual.identification[0].id_number == "A1234567"
    assert individual.programs == ["RUSSIA"]
    assert "sanctioned activity" in individual.narrative


def test_parses_entity_record():
    entities = parse_eu_consolidated(SAMPLE_XML)
    entity = entities[1]
    assert entity.source_id == "EU-2002"
    assert entity.entity_type == SanctionsEntityType.ENTITY
    assert entity.primary_name == "Aldgate Finance Services"
    assert entity.country == "CY"
    assert entity.programs == ["SYRIA"]
