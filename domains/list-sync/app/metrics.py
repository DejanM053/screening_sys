"""Prometheus metrics for list-sync (Section CC-07)."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

SYNC_DURATION_SECONDS = Histogram(
    "list_sync_duration_seconds",
    "Time taken to sync a sanctions list end-to-end",
    ["list_name"],
)

ENTRY_COUNT = Gauge(
    "list_sync_entry_count",
    "Number of entries in the latest synced index for a list",
    ["list_name"],
)

DIFF_ADDED = Counter(
    "list_sync_diff_added_total",
    "Number of new entries detected in a sync",
    ["list_name"],
)

DIFF_REMOVED = Counter(
    "list_sync_diff_removed_total",
    "Number of removed entries detected in a sync",
    ["list_name"],
)

DIFF_MODIFIED = Counter(
    "list_sync_diff_modified_total",
    "Number of modified entries detected in a sync",
    ["list_name"],
)

NEW_WALLET_ADDRESSES = Counter(
    "list_sync_new_wallet_addresses_total",
    "Number of new crypto wallet addresses detected in a sync",
    ["list_name", "chain"],
)

LAST_SUCCESSFUL_SYNC_TIMESTAMP = Gauge(
    "list_sync_last_successful_timestamp_seconds",
    "Unix timestamp of the last successful sync",
    ["list_name"],
)

SYNC_ERRORS = Counter(
    "list_sync_errors_total",
    "Number of sync errors",
    ["list_name"],
)
