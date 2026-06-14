"""OFAC SDN crypto-address screening — Redis SET lookup + XML sync."""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from app.store import KeyValueStore

logger = logging.getLogger("crypto-screener.ofac_wallets")

_OFAC_XML_URL = (
    "https://sanctionslistservice.ofac.treas.gov"
    "/api/PublicationPreview/exports/SDN_ADVANCED.XML"
)
_REDIS_SET_KEY = "ofac_wallets_set"
_OFAC_WALLET_KEY_PREFIX = "ofac_wallet:"

# Known crypto address patterns: BTC, ETH/ERC-20, TRON, XMR, LTC, BCH, DOGE, XRP, ZEC
_ADDR_RE = re.compile(
    r"\b("
    r"T[A-Za-z0-9]{33}"              # TRON
    r"|0x[0-9a-fA-F]{40}"            # Ethereum / ERC-20
    r"|[13][a-km-zA-HJ-NP-Z1-9]{25,34}"  # Bitcoin P2PKH/P2SH
    r"|bc1[a-z0-9]{39,59}"           # Bitcoin Bech32
    r"|X[a-km-zA-HJ-NP-Z1-9]{33}"   # Monero / Dash
    r"|r[0-9a-zA-Z]{24,34}"          # XRP
    r")\b"
)


class OFACWalletScreener:
    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def load(self, addresses: list[str]) -> None:
        for address in addresses:
            await self._store.set(_OFAC_WALLET_KEY_PREFIX + address.lower(), "1")

    async def lookup(self, address: str) -> bool:
        return await self._store.exists(_OFAC_WALLET_KEY_PREFIX + address.lower())

    async def sync_from_ofac_xml(self) -> int:
        """Download OFAC SDN_ADVANCED.XML, parse digital currency addresses, load into Redis.

        Returns the number of addresses loaded.
        """
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(_OFAC_XML_URL)
                resp.raise_for_status()
                xml_bytes = resp.content
        except Exception as exc:
            logger.warning("Failed to download OFAC XML: %s", exc)
            return 0

        addresses = _parse_xml(xml_bytes)
        if not addresses:
            logger.warning("OFAC XML parsed but no crypto addresses found")
            return 0

        await self.load(addresses)
        logger.info("Loaded %d OFAC crypto addresses into Redis", len(addresses))
        return len(addresses)


def _parse_xml(xml_bytes: bytes) -> list[str]:
    """Extract digital currency addresses from OFAC SDN_ADVANCED.XML."""
    addresses: list[str] = []
    try:
        root = ET.fromstring(xml_bytes)
        ns = _detect_namespace(root)

        # Strategy 1: look for <feature> elements with digital currency type
        for feature in root.iter(f"{ns}feature"):
            type_el = feature.find(f".//{ns}featureType")
            if type_el is None:
                type_el = feature.find(f".//{ns}versionDetail")
            type_text = (type_el.text or "") if type_el is not None else ""
            if "currency" in type_text.lower() or "crypto" in type_text.lower() or "digital" in type_text.lower():
                for val in feature.iter(f"{ns}value"):
                    if val.text:
                        found = _ADDR_RE.findall(val.text.strip())
                        addresses.extend(found)

        # Strategy 2: scan all text for address patterns (catches schema variants)
        if not addresses:
            full_text = xml_bytes.decode("utf-8", errors="replace")
            addresses = _ADDR_RE.findall(full_text)

    except ET.ParseError as exc:
        logger.warning("OFAC XML parse error: %s", exc)
        # Fallback: regex over raw text
        addresses = _ADDR_RE.findall(xml_bytes.decode("utf-8", errors="replace"))

    return list(set(a.lower() for a in addresses))


def _detect_namespace(root: ET.Element) -> str:
    tag = root.tag
    if tag.startswith("{"):
        return "{" + tag[1:].split("}")[0] + "}"
    return ""
