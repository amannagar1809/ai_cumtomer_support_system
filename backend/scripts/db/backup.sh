#!/usr/bin/env bash
# Daily logical backup — User Story 1.2.2
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-35}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-ai_support}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="${BACKUP_DIR}/ai_support_${STAMP}.dump"

echo "Backing up ${PGDATABASE} -> ${FILE}"
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$FILE"

# Retention: delete backups older than RETENTION_DAYS
find "$BACKUP_DIR" -name 'ai_support_*.dump' -type f -mtime +"$RETENTION_DAYS" -delete

echo "Backup complete. Retention: ${RETENTION_DAYS} days."
