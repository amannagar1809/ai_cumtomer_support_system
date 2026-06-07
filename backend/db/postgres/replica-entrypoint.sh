#!/bin/bash
set -euo pipefail

export PGDATA="${PGDATA:-/var/lib/postgresql/data}"
PRIMARY_HOST="${POSTGRES_PRIMARY_HOST:-postgres}"
PRIMARY_PORT="${POSTGRES_PRIMARY_PORT:-5432}"
REPLICATOR_USER="${REPLICATOR_USER:-replicator}"
REPLICATOR_PASSWORD="${REPLICATOR_PASSWORD:-replicator_pass}"

until pg_isready -h "$PRIMARY_HOST" -p "$PRIMARY_PORT" -U postgres; do
  echo "Waiting for primary PostgreSQL..."
  sleep 2
done

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "Bootstrapping replica from primary..."
  export PGPASSWORD="$REPLICATOR_PASSWORD"
  rm -rf "$PGDATA"/*
  pg_basebackup \
    -h "$PRIMARY_HOST" \
    -p "$PRIMARY_PORT" \
    -U "$REPLICATOR_USER" \
    -D "$PGDATA" \
    -Fp -Xs -P -R
  chown -R postgres:postgres "$PGDATA"
  chmod 700 "$PGDATA"
fi

exec docker-entrypoint.sh postgres \
  -c hot_standby=on \
  -c max_standby_streaming_delay=30s
