# Running MigrateIQ Locally

## What you need

| Tool | Install | Check |
|------|---------|-------|
| Python 3.9+ | Already on macOS. Or [python.org](https://python.org) | `python3 --version` |
| Node.js 18+ | [nodejs.org](https://nodejs.org) | `node --version` |
| PostgreSQL 15+ | `brew install postgresql@16` | `pg_isready` |

That's it. No Docker. No Redis. No cloud accounts needed to start.

---

## First-time setup (one command)

```bash
cd migrateiq
./start.sh setup
```

This will:
1. Start PostgreSQL
2. Create the `migrateiq` database and user
3. Create a Python virtual environment in `backend/.venv`
4. Install all Python packages
5. Run database migrations
6. Install npm packages

Takes about 2 minutes on first run.

---

## Start the app

```bash
./start.sh
```

Opens:
- **Backend API** → http://localhost:8000
- **API docs** → http://localhost:8000/docs  ← interactive, try endpoints here
- **Frontend** → http://localhost:5173

Press `Ctrl+C` to stop everything.

---

## Add your Anthropic API key (for AI features)

Edit `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...   ← paste your key here
```

Get a free key at [console.anthropic.com](https://console.anthropic.com).

Without the key: schema upload, file parsing, and the UI all work fine.  
With the key: AI mapping pipeline, ETL generation, and failure explanation work.

---

## VS Code setup

```bash
code migrateiq
```

When VS Code opens:
1. It will prompt **"Install recommended extensions"** → click Install
2. Press **F5** → select **"Full Stack"** to start both backend and frontend with debugger attached
3. Set breakpoints anywhere in Python or TypeScript — they just work

The `.vscode/launch.json` is already configured.

---

## Install PostgreSQL (macOS)

```bash
brew install postgresql@16
brew services start postgresql@16

# Create the database (only needed once)
createuser -s migrateiq
createdb -O migrateiq migrateiq
```

Or check if it's already running:
```bash
pg_isready
# "localhost:5432 - accepting connections" means it's up
```

---

## Run only parts of the stack

```bash
./start.sh backend    # backend only (port 8000)
./start.sh frontend   # frontend only (port 5173)
./start.sh db         # start postgres only
```

---

## Run database migrations manually

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

---

## Common errors

**`pg_isready: command not found`**  
PostgreSQL isn't installed. Run `brew install postgresql@16`.

**`connection refused` on port 5432**  
PostgreSQL is installed but not running. Run `brew services start postgresql@16`.

**`ModuleNotFoundError`**  
You're not in the backend venv. Run `source backend/.venv/bin/activate` first,  
or use `./start.sh` which handles this automatically.

**`Error: ANTHROPIC_API_KEY is not set`**  
AI features need the key. Add it to `backend/.env`. The app still starts without it.

**Port 8000 or 5173 already in use**  
```bash
lsof -ti:8000 | xargs kill   # free port 8000
lsof -ti:5173 | xargs kill   # free port 5173
```
