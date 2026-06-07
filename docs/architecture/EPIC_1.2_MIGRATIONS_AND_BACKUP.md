# Epic 1.2 — Migrations & Backup Strategy

**User Story 1.2.2** · AI Customer Support System  
**Stack:** PostgreSQL 16 · Alembic · Docker Compose

---

## 1. Executive summary

This deliverable makes schema changes **trackable** (Alembic + rollbacks) and data **recoverable** (daily backups, WAL archiving for PITR, read replica for analytics).

---

## 2. Migration tool — Alembic

| Item | Location |
|------|----------|
| Config | `backend/alembic.ini` |
| Environment | `backend/alembic/env.py` (async, reads `DATABASE_URL`) |
| Revisions | `backend/alembic/versions/20260602_0001` … `0004` |
| Guide | `backend/alembic/README` |

### 2.1 Initial schema (all tables)

**Recommended (fresh database):**

```bash
cd backend
python -m alembic upgrade head
```

Applies in order: `users` → `conversations` → `messages` → `tickets`.

**Reference SQL files:** `backend/db/schema/001_*.sql` … `004_*.sql`  
**Index:** `backend/db/schema/000_initial_full_schema.sql`

### 2.2 Rollback scripts (per migration)

| Revision | Alembic rollback | Standalone SQL |
|----------|------------------|----------------|
| `20260602_0004` | `alembic downgrade 20260602_0003` | `db/rollback/rollback_20260602_0004.sql` |
| `20260602_0003` | `alembic downgrade 20260602_0002` | `db/rollback/rollback_20260602_0003.sql` |
| `20260602_0002` | `alembic downgrade 20260602_0001` | `db/rollback/rollback_20260602_0002.sql` |
| `20260602_0001` | `alembic downgrade base` | `db/rollback/rollback_20260602_0001.sql` |

**Full rollback:**

```bash
python -m alembic downgrade base
```

Each migration’s `downgrade()` in Python matches the SQL rollback files.

---

## 3. Daily backup schedule & retention

### 3.1 Policy

| Parameter | Value |
|-----------|-------|
| **Frequency** | Daily (02:00 UTC recommended) |
| **Format** | `pg_dump` custom format (`-Fc`) |
| **Retention** | **35 days** (aligned with Epic 1.1 data layer) |
| **Storage** | `backups/postgres/` (gitignored) |
| **Naming** | `ai_support_YYYYMMDD_HHMMSS.dump` |

### 3.2 Run backup manually

**Windows:**

```powershell
cd backend\scripts\db
.\backup.ps1
```

**Linux / macOS:**

```bash
./backend/scripts/db/backup.sh
```

### 3.3 Automated daily backup (Docker)

```bash
docker compose --profile backup up -d postgres-backup
```

Runs `backup.sh` every **24 hours** inside the `postgres-backup` container.

### 3.4 Production scheduling

| Platform | Schedule |
|----------|----------|
| **Linux cron** | `0 2 * * * /path/to/backend/scripts/db/backup.sh` |
| **Windows Task Scheduler** | Daily 02:00 → `backup.ps1` |
| **Kubernetes CronJob** | `0 2 * * *` → Job with `pg_dump` sidecar |

### 3.5 Restore from logical backup

```bash
pg_restore -h localhost -U postgres -d ai_support --clean --if-exists backups/postgres/ai_support_YYYYMMDD_HHMMSS.dump
python -m alembic stamp head
```

---

## 4. Point-in-time recovery (PITR)

### 4.1 Configuration (primary)

Docker Compose enables on `postgres` service:

| Setting | Value |
|---------|-------|
| `wal_level` | `replica` |
| `archive_mode` | `on` |
| `archive_command` | Copy WAL segments to `/wal_archive/%f` |
| Volume | `postgres_wal_archive` → `/wal_archive` |

Host path (bind mount option for prod): `./backups/wal_archive`

### 4.2 Recovery objectives

| Metric | Target |
|--------|--------|
| **RPO** (max data loss) | ≤ 5 minutes (continuous WAL) |
| **RTO** (restore time) | Depends on backup size; test quarterly |

### 4.3 PITR runbook

1. Stop application writes to primary.
2. Restore latest **base backup** (`pg_dump` or `pg_basebackup`).
3. Configure recovery:
   - `restore_command = 'cp /wal_archive/%f %p'`
   - `recovery_target_time = '2026-06-01 14:30:00+00'`
   - `recovery_target_action = 'promote'`
4. Start PostgreSQL; verify data at target time.
5. Run `alembic current` and `stamp head` if needed.

**Helper script:** `backend/scripts/db/pitr-restore.sh`

---

## 5. Read replica for analytics

### 5.1 Architecture

```mermaid
flowchart LR
    App[FastAPI OLTP] --> Primary[(postgres :5432)]
    Analytics[Analytics queries] --> Replica[(postgres-replica :5433)]
    Primary -->|streaming replication| Replica
```

### 5.2 Local setup

```bash
docker compose up -d postgres
docker compose --profile replica up -d postgres-replica
```

| Role | Host | Port | User |
|------|------|------|------|
| Primary (read/write) | `localhost` | 5432 | `postgres` |
| Replica (read-only) | `localhost` | 5433 | `analytics_reader` |

Replication user: `replicator` (created in `init-primary/01-replication.sql`).

### 5.3 Application configuration

`.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_support
DATABASE_REPLICA_URL=postgresql+asyncpg://analytics_reader:analytics_pass@localhost:5433/ai_support
```

**Code:**

- `get_db()` → primary (OLTP)
- `get_analytics_db()` → replica (`backend/app/core/database.py`)

Use replica for dashboards, reporting, and heavy `SELECT`s — never for writes.

### 5.4 Verify replication

```sql
-- On primary
SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn
FROM pg_stat_replication;
```

```sql
-- On replica
SELECT pg_is_in_recovery();  -- should be true
```

---

## 6. Operations checklist

| Task | Command |
|------|---------|
| Apply migrations | `python -m alembic upgrade head` |
| Current revision | `python -m alembic current` |
| Rollback one step | `python -m alembic downgrade -1` |
| Daily backup | `backup.ps1` or `--profile backup` |
| Start replica | `docker compose --profile replica up -d` |
| Archive old messages | `SELECT archive_messages_older_than(90);` |

---

## 7. Acceptance checklist (Story 1.2.2)

| Task | Status |
|------|--------|
| Migration tool (Alembic) | ✅ |
| Initial migration chain (all tables) | ✅ `upgrade head` |
| Rollback per migration | ✅ Alembic `downgrade` + SQL files |
| Daily backup + retention (35 days) | ✅ scripts + Docker profile |
| Point-in-time recovery config | ✅ WAL archive on primary + runbook |
| Read replica for analytics | ✅ `postgres-replica` + `get_analytics_db()` |

---

*Document version: 1.0 · Epic 1.2 · User Story 1.2.2*
