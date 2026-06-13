"""Celery tasks: fetch, parse, diff, sync each sanctions list (Section CC-07)."""
from __future__ import annotations

import json
import time

import httpx

from app.config import settings
from app.diff_engine import DiffEngine
from app.es_sync import ESSyncManager
from app.metrics import (
    DIFF_ADDED,
    DIFF_MODIFIED,
    DIFF_REMOVED,
    ENTRY_COUNT,
    LAST_SUCCESSFUL_SYNC_TIMESTAMP,
    NEW_WALLET_ADDRESSES,
    SYNC_DURATION_SECONDS,
    SYNC_ERRORS,
)
from app.models import CanonicalSanctionsEntity, SanctionsList, SyncResult
from app.scheduler import celery_app
from app.sources import parse_eu_consolidated, parse_ofac_sdn, parse_ofsi, parse_pep_list, parse_un_consolidated

_SNAPSHOT_KEY_PREFIX = "list_sync:snapshot:"
_GENERATION_KEY_PREFIX = "list_sync:generation:"
_LAST_SUCCESS_KEY_PREFIX = "list_sync:last_success:"


def _redis_client():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _es_client():
    from elasticsearch import Elasticsearch

    return Elasticsearch(settings.elasticsearch_url)


def _load_snapshot(redis_client, list_name: SanctionsList) -> list[CanonicalSanctionsEntity]:
    raw = redis_client.get(_SNAPSHOT_KEY_PREFIX + list_name.value)
    if not raw:
        return []
    return [CanonicalSanctionsEntity.model_validate(item) for item in json.loads(raw)]


def _save_snapshot(redis_client, list_name: SanctionsList, entities: list[CanonicalSanctionsEntity]) -> None:
    payload = json.dumps([entity.model_dump(mode="json") for entity in entities])
    redis_client.set(_SNAPSHOT_KEY_PREFIX + list_name.value, payload)


def _next_generation(redis_client, list_name: SanctionsList) -> int:
    return redis_client.incr(_GENERATION_KEY_PREFIX + list_name.value)


def _notify(message: str, severity: str = "info") -> None:
    try:
        httpx.post(
            f"{settings.notification_service_url}/notify",
            json={"source": "list-sync", "severity": severity, "message": message},
            timeout=5.0,
        )
    except Exception:
        pass


def _update_wallet_registry(redis_client, list_name: SanctionsList, entities: list[CanonicalSanctionsEntity]) -> None:
    for entity in entities:
        for crypto_address in entity.crypto_addresses:
            key = f"ofac_wallet:{crypto_address.address.lower()}"
            if not redis_client.exists(key):
                redis_client.set(key, "1")
                NEW_WALLET_ADDRESSES.labels(list_name=list_name.value, chain=crypto_address.chain).inc()


def _check_staleness(redis_client, list_name: SanctionsList) -> None:
    last_success_raw = redis_client.get(_LAST_SUCCESS_KEY_PREFIX + list_name.value)
    if last_success_raw is None:
        return
    age_hours = (time.time() - float(last_success_raw)) / 3600.0
    if age_hours > settings.max_staleness_hours:
        _notify(
            f"{list_name.value} data is {age_hours:.1f}h old, exceeding max_staleness_hours="
            f"{settings.max_staleness_hours}. Last successful sync may have failed.",
            severity="warning",
        )


def _run_sync(list_name: SanctionsList, url: str, parse_fn, fetch_kind: str = "bytes") -> SyncResult:
    redis_client = _redis_client()
    start = time.monotonic()

    try:
        response = httpx.get(url, timeout=120.0, follow_redirects=True)
        response.raise_for_status()
        raw = response.content if fetch_kind == "bytes" else response.text
        current = parse_fn(raw)
    except Exception as exc:
        SYNC_ERRORS.labels(list_name=list_name.value).inc()
        _check_staleness(redis_client, list_name)
        previous = _load_snapshot(redis_client, list_name)
        return SyncResult(
            list_name=list_name,
            entry_count=len(previous),
            previous_count=len(previous),
            diff=DiffEngine.diff(list_name, previous, previous),
            validated=False,
            alias_swapped=False,
            error=str(exc),
        )

    previous = _load_snapshot(redis_client, list_name)
    diff = DiffEngine.diff(list_name, previous, current)

    es_manager = ESSyncManager(_es_client())
    previous_count = es_manager.current_entry_count(list_name)
    validated = es_manager.validate(len(current), previous_count)

    alias_swapped = False
    if validated:
        generation = _next_generation(redis_client, list_name)
        new_index = es_manager.index_entities(list_name, current, generation)
        es_manager.swap_alias(list_name, new_index)
        alias_swapped = True

        _save_snapshot(redis_client, list_name, current)
        _update_wallet_registry(redis_client, list_name, diff.added + diff.modified)
        redis_client.set(_LAST_SUCCESS_KEY_PREFIX + list_name.value, str(time.time()))

        if diff.total_changes:
            _notify(
                f"{list_name.value} sync complete: +{len(diff.added)} added, "
                f"-{len(diff.removed_keys)} removed, ~{len(diff.modified)} modified"
            )
    else:
        SYNC_ERRORS.labels(list_name=list_name.value).inc()
        _notify(
            f"{list_name.value} sync rejected: new entry count {len(current)} is below "
            f"{settings.min_entry_count_ratio:.0%} of previous count {previous_count}",
            severity="warning",
        )

    ENTRY_COUNT.labels(list_name=list_name.value).set(len(current))
    DIFF_ADDED.labels(list_name=list_name.value).inc(len(diff.added))
    DIFF_REMOVED.labels(list_name=list_name.value).inc(len(diff.removed_keys))
    DIFF_MODIFIED.labels(list_name=list_name.value).inc(len(diff.modified))
    if alias_swapped:
        LAST_SUCCESSFUL_SYNC_TIMESTAMP.labels(list_name=list_name.value).set(time.time())
    SYNC_DURATION_SECONDS.labels(list_name=list_name.value).observe(time.monotonic() - start)

    return SyncResult(
        list_name=list_name,
        entry_count=len(current),
        previous_count=previous_count,
        diff=diff,
        validated=validated,
        alias_swapped=alias_swapped,
    )


@celery_app.task(name="app.tasks.sync_ofac")
def sync_ofac() -> dict:
    return _run_sync(SanctionsList.OFAC_SDN, settings.ofac_sdn_url, parse_ofac_sdn, fetch_kind="bytes").model_dump(mode="json")


@celery_app.task(name="app.tasks.sync_ofsi")
def sync_ofsi() -> dict:
    return _run_sync(SanctionsList.OFSI_CONSOLIDATED, settings.ofsi_url, parse_ofsi, fetch_kind="text").model_dump(mode="json")


@celery_app.task(name="app.tasks.sync_eu")
def sync_eu() -> dict:
    return _run_sync(SanctionsList.EU_CONSOLIDATED, settings.eu_consolidated_url, parse_eu_consolidated, fetch_kind="bytes").model_dump(mode="json")


@celery_app.task(name="app.tasks.sync_un")
def sync_un() -> dict:
    return _run_sync(SanctionsList.UN_CONSOLIDATED, settings.un_consolidated_url, parse_un_consolidated, fetch_kind="bytes").model_dump(mode="json")


@celery_app.task(name="app.tasks.sync_pep")
def sync_pep() -> dict:
    return _run_sync(SanctionsList.PEP, settings.opensanctions_pep_url, parse_pep_list, fetch_kind="text").model_dump(mode="json")


SYNC_TASKS = {
    SanctionsList.OFAC_SDN: sync_ofac,
    SanctionsList.OFSI_CONSOLIDATED: sync_ofsi,
    SanctionsList.EU_CONSOLIDATED: sync_eu,
    SanctionsList.UN_CONSOLIDATED: sync_un,
    SanctionsList.PEP: sync_pep,
}
