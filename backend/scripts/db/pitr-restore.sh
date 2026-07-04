#!/usr/bin/env bash
# Point-in-time recovery helper (requires WAL archive from primary)
# Usage: ./pitr-restore.sh "2026-06-01 14:30:00+00"
set -euo pipefail

TARGET_TIME="${1:?Usage: $0 'YYYY-MM-DD HH:MM:SS+00'}"
PGDATA="${PGDATA:-./restore/pgdata}"
WAL_ARCHIVE="${WAL_ARCHIVE:-./backups/wal_archive}"
BASE_BACKUP="${BASE_BACKUP:-./backups/postgres/latest_base}"

echo "PITR target: $TARGET_TIME"
echo "1. Stop PostgreSQL application connections"
echo "2. Restore base backup to \$PGDATA"
echo "3. Create recovery.signal and set restore_command / recovery_target_time"

mkdir -p "$PGDATA"
cat > "$PGDATA/recovery.signal" <<EOF
# Recovery in progress
EOF

cat >> "$PGDATA/postgresql.auto.conf" <<EOF
restore_command = 'cp ${WAL_ARCHIVE}/%f %p'
recovery_target_time = '${TARGET_TIME}'
recovery_target_action = 'promote'
EOF

echo "4. Start PostgreSQL — it will replay WAL until $TARGET_TIME"
echo "See docs/architecture/EPIC_1.2_MIGRATIONS_AND_BACKUP.md for full runbook"
