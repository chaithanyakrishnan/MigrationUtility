# MigrateIQ — How to Run

Every command you need, in the exact order to run them.
No assumptions. Works every restart.

---

## Prerequisites (install once, never again)

### 1. PostgreSQL
```bash
brew install postgresql@16
brew services start postgresql@16
```

### 2. Node.js 18+
Download from https://nodejs.org and install.

### 3. pgvector (optional — for AI semantic search)
```bash
brew install pgvector
brew services restart postgresql@16
```
Skip this for now — the app works without it, just with weaker search.

---

## First-time database setup (run once only)

```bash
# Create the database user and database
psql postgres -c "CREATE USER migrateiq WITH PASSWORD 'password';"
psql postgres -c "CREATE DATABASE migrateiq OWNER migrateiq;"
```

If you get "role migrateiq already exists" — that's fine, continue.

---

## First-time Python setup (run once only)

```bash
cd ~/Documents/migrateiq/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the env file:
```bash
cp .env.example .env
```

Run migrations (creates all database tables):
```bash
cd ~/Documents/migrateiq/backend
source .venv/bin/activate
alembic upgrade head
```

You should see:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema — all tables
```

---

## First-time Node setup (run once only)

```bash
cd ~/Documents/migrateiq/frontend
npm install
cp .env.example .env.local
```

---

## Every time you want to run the app

You need **two terminal windows open at the same time**.

### Terminal 1 — Backend

```bash
# Step 1: make sure postgres is running
brew services start postgresql@16

# Step 2: go to backend folder and activate the venv
cd ~/Documents/migrateiq/backend
source .venv/bin/activate

# Step 3: start the backend
uvicorn app.main:app --reload --port 8000
```

Wait until you see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Keep this terminal open.**

### Terminal 2 — Frontend

```bash
# In a NEW terminal window:
cd ~/Documents/migrateiq/frontend
npm run dev
```

Wait until you see:
```
  ➜  Local:   http://localhost:5173/
```

**Keep this terminal open.**

### Open the app

Go to **http://localhost:5173** in your browser.

API docs (test any endpoint): **http://localhost:8000/docs**

---

## If you see "Backend not connected" in the app

The frontend loaded but cannot reach the backend. Fix:

1. Check Terminal 1 — is uvicorn still running? If not, restart it:
   ```bash
   cd ~/Documents/migrateiq/backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. Check postgres is running:
   ```bash
   brew services start postgresql@16
   pg_isready -h localhost -p 5432
   # Should print: localhost:5432 - accepting connections
   ```

3. Try the health endpoint directly:
   ```
   http://localhost:8000/api/v1/health
   ```
   Should return `{"status":"ok",...}`

---

## Stopping the app

- Press `Ctrl+C` in both terminals.

---

## After a Mac restart

Postgres does NOT start automatically after a reboot. You must run:

```bash
brew services start postgresql@16
```

Then follow the "Every time you want to run the app" steps above.

To make postgres start automatically on login:
```bash
brew services enable postgresql@16
```

---

## Troubleshooting

### Port already in use
```bash
lsof -ti:8000 | xargs kill -9   # free backend port
lsof -ti:5173 | xargs kill -9   # free frontend port
```
Then start again normally.

### "relation does not exist" database error
The tables were not created. Run:
```bash
psql postgres -c "DROP DATABASE IF EXISTS migrateiq;"
psql postgres -c "CREATE DATABASE migrateiq OWNER migrateiq;"
cd ~/Documents/migrateiq/backend
source .venv/bin/activate
alembic upgrade head
```

### "connection refused" on port 5432
Postgres is not running:
```bash
brew services start postgresql@16
```

### Module not found / import errors
You forgot to activate the venv:
```bash
cd ~/Documents/migrateiq/backend
source .venv/bin/activate
```

### Frontend changes not showing
The frontend hot-reloads automatically. If it seems stuck:
```bash
# In Terminal 2: Ctrl+C then:
cd ~/Documents/migrateiq/frontend
npm run dev
```

### Backend changes not reloading
`--reload` watches for file changes automatically.
If it's stuck, `Ctrl+C` in Terminal 1 and restart uvicorn.
