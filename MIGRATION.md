# SQLite → PostgreSQL Migration Guide — Heavenly Dao Engine (v1.0.0)

This guide provides step-by-step instructions for migrating the **Heavenly Dao Engine** from SQLite to PostgreSQL for high-concurrency production deployments (700+ Discord members).

---

## 🚀 When to Migrate to PostgreSQL

* Active concurrent Discord members exceed 100 cultivators simultaneously.
* Database file size exceeds 500MB.
* Need point-in-time recovery (PITR) and database replication across nodes.
* Require read-replicas for external web dashboards or analytics.

---

## 🛠️ Prerequisites

1. **PostgreSQL 15+** installed locally, on a VPS, or via Supabase / Managed Database.
2. Install `asyncpg` dependency in Python environment:
   ```bash
   pip install asyncpg
   ```
3. Backup existing SQLite database:
   ```bash
   cp heavenly_dao.db heavenly_dao.db.bak
   ```

---

## 📋 Step-by-Step Migration Workflow

### 1. Initialize PostgreSQL Database & Extensions

Create target PostgreSQL database and apply enterprise schema DDL:
```bash
createdb heavenly_dao
psql -d heavenly_dao -f migrations/011_postgres_schema.sql
```

### 2. Execute Automated Data Migration Script

Run the automated data migration script to convert SQLite data and JSON fields:
```bash
python scripts/migrate_sqlite_to_postgres.py heavenly_dao.db "postgresql://user:password@localhost:5432/heavenly_dao"
```

### 3. Validate Migration Parity

Run the validation script to verify row counts and data integrity:
```bash
python scripts/validate_migration.py heavenly_dao.db "postgresql://user:password@localhost:5432/heavenly_dao"
```

### 4. Update Bot Configuration

Update your `.env` configuration file to switch database layers:
```env
DATABASE_TYPE=postgres
DATABASE_URL=postgresql://user:password@localhost:5432/heavenly_dao
DB_MIN_CONNECTIONS=5
DB_MAX_CONNECTIONS=20
```

### 5. Restart Bot Engine

Restart the bot to connect to PostgreSQL pool:
```bash
python run.py
```

---

## 🔄 Zero-Data-Loss Rollback Plan

If any issue occurs during cutover, you can instantly revert to SQLite with zero downtime:

1. Stop bot process.
2. Revert `.env` setting to `DATABASE_TYPE=sqlite`.
3. Restart bot — SQLite file (`heavenly_dao.db`) remains completely untouched during migration.
