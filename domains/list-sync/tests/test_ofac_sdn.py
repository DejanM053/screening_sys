from app.models import SanctionsEntityType, SanctionsList
from app.sources.ofac_sdn import parse_ofac_sdn

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<sdnList xmlns="http://tempuri.org/sdnList.xsd">
  <sdnEntry>
    <uid>12345</uid>
    <firstName>John</firstName>
    <lastName>Doe</lastName>
    <sdnType>Individual</sdnType>
    <programList>
      <program>SDGT</program>
    </programList>
    <akaList>
      <aka>
        <uid>1</uid>
        <type>a.k.a.</type>
        <firstName>Johnny</firstName>
        <lastName>D</lastName>
      </aka>
    </akaList>
    <addressList>
      <address>
        <uid>1</uid>
        <city>Tehran</city>
        <country>Iran</country>
      </address>
    </addressList>
    <idList>
      <id>
        <uid>1</uid>
        <idType>Passport</idType>
        <idNumber>A1234567</idNumber>
        <idCountry>Iran</idCountry>
      </id>
    </idList>
    <featureList>
      <feature>
        <uid>1</uid>
        <type>Digital Currency Address - XBT</type>
        <version>
          <uid>1</uid>
          <value>1A2b3C4d5E6f7G8h9I0j</value>
        </version>
      </feature>
      <feature>
        <uid>2</uid>
        <type>Digital Currency Address - TRX</type>
        <version>
          <uid>1</uid>
          <value>TXxYyZzAaBbCcDdEeFfGgHhIiJjKkLlMm</value>
        </version>
      </feature>
    </featureList>
  </sdnEntry>
  <sdnEntry>
    <uid>67890</uid>
    <lastName>Acme Trading LLC</lastName>
    <sdnType>Entity</sdnType>
    <programList>
      <program>UKRAINE-EO13662</program>
    </programList>
  </sdnEntry>
</sdnList>
"""


def test_parses_individual_with_aliases_addresses_ids_and_crypto():
    entities = parse_ofac_sdn(SAMPLE_XML)
    assert len(entities) == 2

    individual = entities[0]
    assert individual.source_list == SanctionsList.OFAC_SDN
    assert individual.source_id == "12345"
    assert individual.entity_type == SanctionsEntityType.INDIVIDUAL
    assert individual.primary_name == "John Doe"
    assert individual.aliases == ["Johnny D"]
    assert individual.programs == ["SDGT"]
    assert individual.country == "Iran"
    assert individual.addresses[0].country == "Iran"
    assert individual.identification[0].id_number == "A1234567"

    crypto_chains = {c.chain: c.address for c in individual.crypto_addresses}
    assert crypto_chains["bitcoin"] == "1A2b3C4d5E6f7G8h9I0j"
    assert crypto_chains["tron"] == "TXxYyZzAaBbCcDdEeFfGgHhIiJjKkLlMm"


def test_parses_entity_record():
    entities = parse_ofac_sdn(SAMPLE_XML)
    entity = entities[1]
    assert entity.source_id == "67890"
    assert entity.entity_type == SanctionsEntityType.ENTITY
    assert entity.primary_name == "Acme Trading LLC"
    assert entity.programs == ["UKRAINE-EO13662"]
    assert entity.crypto_addresses == []


def test_key_and_content_hash_are_stable():
    entities = parse_ofac_sdn(SAMPLE_XML)
    entity = entities[0]
    assert entity.key == "OFAC_SDN:12345"
    assert entity.content_hash() == entity.content_hash()
