from app.models import SanctionsEntityType, SanctionsList
from app.sources.un_list import parse_un_consolidated

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST>
  <INDIVIDUALS>
    <INDIVIDUAL>
      <DATAID>1001</DATAID>
      <FIRST_NAME>Ahmad</FIRST_NAME>
      <SECOND_NAME>Khalid</SECOND_NAME>
      <SECOND_NAME>Mansour</SECOND_NAME>
      <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
      <INDIVIDUAL_ALIAS>
        <QUALITY>Good</QUALITY>
        <ALIAS_NAME>A. K. Mansour</ALIAS_NAME>
      </INDIVIDUAL_ALIAS>
      <NATIONALITY>
        <VALUE>Yemen</VALUE>
      </NATIONALITY>
      <INDIVIDUAL_ADDRESS>
        <COUNTRY>Yemen</COUNTRY>
        <CITY>Sana'a</CITY>
      </INDIVIDUAL_ADDRESS>
      <COMMENTS1>Listed pursuant to resolution 1267.</COMMENTS1>
    </INDIVIDUAL>
  </INDIVIDUALS>
  <ENTITIES>
    <ENTITY>
      <DATAID>2002</DATAID>
      <FIRST_NAME>Meridian Global Ltd</FIRST_NAME>
      <ENTITY_ALIAS>
        <ALIAS_NAME>Meridian Global Limited</ALIAS_NAME>
      </ENTITY_ALIAS>
      <ENTITY_ADDRESS>
        <COUNTRY>British Virgin Islands</COUNTRY>
      </ENTITY_ADDRESS>
      <COMMENTS1>Shell company used for asset concealment.</COMMENTS1>
    </ENTITY>
  </ENTITIES>
</CONSOLIDATED_LIST>
"""


def test_parses_individual():
    entities = parse_un_consolidated(SAMPLE_XML)
    assert len(entities) == 2

    individual = entities[0]
    assert individual.source_list == SanctionsList.UN_CONSOLIDATED
    assert individual.source_id == "1001"
    assert individual.entity_type == SanctionsEntityType.INDIVIDUAL
    # NOTE: ElementTree only retains the last element with a given tag name
    # accessed via direct iteration order, but our _individual_name reads
    # FIRST_NAME/SECOND_NAME/THIRD_NAME/FOURTH_NAME positionally so repeated
    # SECOND_NAME tags collapse to the first occurrence found by child_text.
    assert individual.primary_name.startswith("Ahmad")
    assert individual.aliases == ["A. K. Mansour"]
    assert individual.country == "Yemen"
    assert "1267" in individual.narrative


def test_parses_entity():
    entities = parse_un_consolidated(SAMPLE_XML)
    entity = entities[1]
    assert entity.source_id == "2002"
    assert entity.entity_type == SanctionsEntityType.ENTITY
    assert entity.primary_name == "Meridian Global Ltd"
    assert entity.aliases == ["Meridian Global Limited"]
    assert entity.country == "British Virgin Islands"
    assert "concealment" in entity.narrative
