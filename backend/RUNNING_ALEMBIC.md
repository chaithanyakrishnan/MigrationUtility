# Running Alembic Migrations

## Important: always run from the `backend/` directory

```bash
cd migrateiq/backend
source .venv/bin/activate
alembic upgrade head
```

Running from any other directory will cause `ModuleNotFoundError: No module named 'app'`
because `env.py` adds `backend/` to `sys.path` relative to its own location.

## Common commands

```bash
# Apply all pending migrations
alembic upgrade head

# Check current migration state
alembic current

# Show migration history
alembic history

# Roll back one migration
alembic downgrade -1

# Roll back all migrations
alembic downgrade base

# Generate a new migration after model changes
alembic revision --autogenerate -m "describe your change"
```

## Database URL

Alembic reads `DATABASE_URL` in this priority order:
1. `DATABASE_URL` environment variable (e.g. set in your shell or CI)
2. `DATABASE_URL=` line in `backend/.env`
3. `sqlalchemy.url` in `alembic.ini` (default: `postgresql://migrateiq:password@localhost:5432/migrateiq`)

The URL is automatically converted from `postgresql+asyncpg://` (used by the app at
runtime) to `postgresql://` (used by Alembic's sync psycopg2 driver).

## Troubleshooting

**`ModuleNotFoundError: No module named 'app'`**
→ You're not in the `backend/` directory. `cd migrateiq/backend` first.

**`connection refused` / `could not connect to server`**
→ PostgreSQL isn't running. Start it with Docker:
```bash
docker start migrateiq-postgres
# or
docker run -d --name migrateiq-postgres \
  -e POSTGRES_USER=migrateiq -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=migrateiq -p 5432:5432 pgvector/pgvector:pg16
```

**`psycopg2` not found**
→ Install it: `pip install psycopg2-binary`

**pgvector extension error**
→ The migration runs `CREATE EXTENSION IF NOT EXISTS vector` — this requires
the pgvector extension to be installed in your PostgreSQL.
If using the `pgvector/pgvector:pg16` Docker image it's pre-installed.
For a local Postgres: `sudo apt install postgresql-16-pgvector` (Ubuntu)
or `brew install pgvector` (macOS).
