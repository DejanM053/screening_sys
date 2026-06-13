#!/usr/bin/env sh
# Sanctions Screening System — MinIO bucket bootstrap
# Creates the audit-documents bucket used by the audit-trail service
# for screening-decision document storage (Section 11.4 / CC-audit-trail).
#
# Usage: ./infrastructure/minio/buckets.sh
# Requires the MinIO client (mc) and a running minio container (see docker-compose.yml).

set -eu

MINIO_ALIAS="${MINIO_ALIAS:-sanctions-minio}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-sanctions_minio}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-sanctions_minio_pass}"
BUCKET="audit-documents"

mc alias set "$MINIO_ALIAS" "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"

if mc ls "$MINIO_ALIAS/$BUCKET" >/dev/null 2>&1; then
  echo "Bucket '$BUCKET' already exists."
else
  mc mb "$MINIO_ALIAS/$BUCKET"
  echo "Created bucket '$BUCKET'."
fi

# Write-once-style retention: object versioning so audit documents cannot be
# silently overwritten or lost.
mc version enable "$MINIO_ALIAS/$BUCKET"

# Default retention matches the longest jurisdiction retention period (10 years
# for EU high-risk per Section 9.2); per-record retention overrides are applied
# by audit-trail/app/retention.py at upload time.
mc retention set --default GOVERNANCE 3650d "$MINIO_ALIAS/$BUCKET" || \
  echo "Warning: could not set default bucket retention (requires object-lock enabled bucket created with mc mb --with-lock)."
