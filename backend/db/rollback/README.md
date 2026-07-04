# Rollback scripts

Each file reverses one Alembic revision. Prefer Alembic when possible:

```bash
cd backend
python -m alembic downgrade 20260602_0003   # one step
python -m alembic downgrade base            # all tables
```

| Revision | Rollback SQL | Alembic equivalent |
|----------|--------------|-------------------|
| `20260602_0004` | `rollback_20260602_0004.sql` | `alembic downgrade 20260602_0003` |
| `20260602_0003` | `rollback_20260602_0003.sql` | `alembic downgrade 20260602_0002` |
| `20260602_0002` | `rollback_20260602_0002.sql` | `alembic downgrade 20260602_0001` |
| `20260602_0001` | `rollback_20260602_0001.sql` | `alembic downgrade base` |

Run order for full rollback: **0004 → 0003 → 0002 → 0001**.
