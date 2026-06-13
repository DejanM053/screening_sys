from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SanctionsList(str, Enum):
    OFAC_SDN = "OFAC_SDN"
    OFAC_CONSOLIDATED = "OFAC_CONSOLIDATED"
    UK_SANCTIONS_LIST = "UK_SANCTIONS_LIST"
    OFSI_CONSOLIDATED = "OFSI_CONSOLIDATED"
    EU_CONSOLIDATED = "EU_CONSOLIDATED"
    EU_TERRORISM = "EU_TERRORISM"
    UN_CONSOLIDATED = "UN_CONSOLIDATED"
    PEP = "PEP"


class SanctionsEntityType(str, Enum):
    INDIVIDUAL = "individual"
    ENTITY = "entity"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"


class CryptoAddress(BaseModel):
    chain: str
    address: str


class Address(BaseModel):
    country: Optional[str] = None
    full_address: Optional[str] = None


class Identification(BaseModel):
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    country: Optional[str] = None


class CanonicalSanctionsEntity(BaseModel):
    """Canonical schema all source parsers normalize into.

    `source_list` + `source_id` is the unique key used by the DiffEngine and
    the Elasticsearch document _id.
    """

    source_list: SanctionsList
    source_id: str
    entity_type: SanctionsEntityType
    primary_name: str
    aliases: List[str] = Field(default_factory=list)
    addresses: List[Address] = Field(default_factory=list)
    identification: List[Identification] = Field(default_factory=list)
    crypto_addresses: List[CryptoAddress] = Field(default_factory=list)
    programs: List[str] = Field(default_factory=list)
    narrative: Optional[str] = None
    country: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    @property
    def key(self) -> str:
        return f"{self.source_list.value}:{self.source_id}"

    def content_hash(self) -> str:
        """Hash of fields the DiffEngine considers when detecting modifications."""
        import hashlib
        import json

        payload = {
            "primary_name": self.primary_name,
            "aliases": sorted(self.aliases),
            "addresses": [a.model_dump() for a in self.addresses],
            "identification": [i.model_dump() for i in self.identification],
            "crypto_addresses": sorted(f"{c.chain}:{c.address}" for c in self.crypto_addresses),
            "programs": sorted(self.programs),
            "narrative": self.narrative,
            "country": self.country,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class DiffResult(BaseModel):
    list_name: SanctionsList
    added: List[CanonicalSanctionsEntity] = Field(default_factory=list)
    removed_keys: List[str] = Field(default_factory=list)
    modified: List[CanonicalSanctionsEntity] = Field(default_factory=list)

    @property
    def new_crypto_addresses(self) -> List[CryptoAddress]:
        addresses: List[CryptoAddress] = []
        for entity in self.added + self.modified:
            addresses.extend(entity.crypto_addresses)
        return addresses

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.removed_keys) + len(self.modified)


class SyncResult(BaseModel):
    list_name: SanctionsList
    entry_count: int
    previous_count: int
    diff: DiffResult
    validated: bool
    alias_swapped: bool
    error: Optional[str] = None
