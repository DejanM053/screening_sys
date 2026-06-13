import json

from app.models import SanctionsEntityType, SanctionsList
from app.sources.pep_list import parse_pep_list


def _line(record: dict) -> str:
    return json.dumps(record)


SAMPLE_JSONL = "\n".join(
    [
        _line(
            {
                "id": "Q12345",
                "schema": "Person",
                "caption": "Jane Politician",
                "properties": {
                    "name": ["Jane Politician"],
                    "alias": ["J. Politician"],
                    "country": ["gb"],
                    "topics": ["role.pep"],
                },
            }
        ),
        _line(
            {
                "id": "Q99999",
                "schema": "Company",
                "caption": "Not A PEP Ltd",
                "properties": {
                    "name": ["Not A PEP Ltd"],
                    "country": ["gb"],
                    "topics": ["sanction"],
                },
            }
        ),
        "",
    ]
)


def test_filters_to_pep_records_only():
    entities = parse_pep_list(SAMPLE_JSONL)
    assert len(entities) == 1

    pep = entities[0]
    assert pep.source_list == SanctionsList.PEP
    assert pep.source_id == "Q12345"
    assert pep.entity_type == SanctionsEntityType.INDIVIDUAL
    assert pep.primary_name == "Jane Politician"
    assert pep.aliases == ["J. Politician"]
    assert pep.country == "gb"
    assert pep.programs == ["PEP"]
