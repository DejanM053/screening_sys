"""OpenSanctions API fallback for entity matching (no Elasticsearch required)."""
from __future__ import annotations

import logging
import os
from typing import List

import httpx

from app.fuzzy.matcher import FuzzyMatcher

_BASE_URL = os.getenv("OPENSANCTIONS_URL", "https://api.opensanctions.org")
_DATASET = "default"
_logger = logging.getLogger("entity-resolution.opensanctions")
_fuzzy = FuzzyMatcher()


def _auth_headers() -> dict:
    key = os.getenv("OPENSANCTIONS_API_KEY", "")
    h = {"Accept": "application/json"}
    if key:
        h["Authorization"] = f"ApiKey {key}"
    return h


async def match_opensanctions(
    name: str, country: str, entity_type: str = "business", cutoff: float = 0.40
) -> List[dict]:
    """Call the OpenSanctions Match API (logic-v2 algorithm).

    Returns candidates in the same format as the Elasticsearch path:
    {matched_name, score, list_source, list_entry_id, match_methods_used}.
    Falls back to empty list on any network or API error.
    """
    schema = "LegalEntity" if entity_type == "business" else "Person"
    properties: dict = {"name": [name]}
    if country:
        properties["country"] = [country.lower()]

    payload = {
        "queries": {"q1": {"schema": schema, "properties": properties}},
        "algorithm": "logic-v2",
        "cutoff": cutoff,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_BASE_URL}/match/{_DATASET}",
                json=payload,
                headers=_auth_headers(),
            )
            if resp.status_code == 402:
                _logger.warning("OpenSanctions: payment required — check API key / quota")
                return []
            if resp.status_code != 200:
                _logger.warning("OpenSanctions API returned %s: %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()
            results = data.get("responses", {}).get("q1", {}).get("results", [])

            candidates = []
            for r in results:
                entity = r.get("entity", {})
                props = entity.get("properties", {})
                names = props.get("name", [])
                matched_name = names[0] if names else name

                api_score = float(r.get("score", 0.0))
                fuzzy_score = _fuzzy.score(name.lower(), matched_name.lower())
                blended = round(0.6 * fuzzy_score + 0.4 * api_score, 4)

                datasets = props.get("datasets", entity.get("datasets", []))
                list_source = datasets[0] if datasets else "opensanctions"

                candidates.append({
                    "matched_name": matched_name,
                    "score": blended,
                    "list_source": list_source,
                    "list_entry_id": entity.get("id", ""),
                    "match_methods_used": ["opensanctions-logic-v2", "fuzzy"],
                })

            candidates.sort(key=lambda x: x["score"], reverse=True)
            return candidates

    except Exception as exc:
        _logger.warning("OpenSanctions API call failed: %s", exc)
        return []
