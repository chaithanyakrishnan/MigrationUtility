#!/bin/bash
# MigrateIQ — full local dev setup
# Handles: Docker, Docker Compose, Homebrew postgres, native postgres, or manual

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "=== MigrateIQ Dev Setup ==="
echo ""

# ── 1. PostgreSQL with pgvector ─────────────────────────────
echo "--- Step 1: PostgreSQL ---"

DB_READY=false

# Check if postgres is already reachable on 5432
if command -v pg_isready &>/dev/null && pg_isready -h localhost -p 5432 -U migrateiq -q 2>/dev/null; then
  echo "✓ PostgreSQL already running on :5432"
  DB_READY=true
fi

if [ "$DB_READY" = false ]; then
  # Try Docker
  if command -v docker &>/dev/null; then
    echo "Using Docker to start PostgreSQL + pgvector..."
    if docker ps 2>/dev/null | grep -q migrateiq-postgres; then
      echo "✓ migrateiq-postgres container already running"
    elif docker ps -a 2>/dev/null | grep -q migrateiq-postgres; then
      echo "Restarting existing migrateiq-postgres container..."
      docker start migrateiq-postgres
    else
      echo "Creating migrateiq-postgres container..."
      docker run -d --name migrateiq-postgres \
        -e POSTGRES_USER=migrateiq \
        -e POSTGRES_PASSWORD=password \
        -e POSTGRES_DB=migrateiq \
        -p 5432:5432 \
        pgvector/pgvector:pg16
    fi
    echo -n "Waiting for postgres to be ready"
    for i in $(seq 1 15); do
      sleep 1
      echo -n "."
      if docker exec migrateiq-postgres pg_isready -U migrateiq -q 2>/dev/null; then
        echo " ✓"
        DB_READY=true
        break
      fi
    done

  # Try Docker Compose
  elif command -v docker-compose &>/dev/null || (command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1); then
    echo "Using Docker Compose..."
    cd infra/docker
    cp ../../backend/.env.example .env 2>/dev/null || true
    docker compose up -d postgres
    sleep 4
    DB_READY=true
    cd "$ROOT_DIR"

  # Try Homebrew postgres (macOS)
  elif command -v brew &>/dev/null && brew services list 2>/dev/null | grep -q postgresql; then
    echo "Starting Homebrew PostgreSQL..."
    brew services start postgresql@16 2>/dev/null || brew services start postgresql 2>/dev/null || true
    sleep 2
    # Create database and user if needed
    psql postgres -c "CREATE USER migrateiq WITH PASSWORD 'password';" 2>/dev/null || true
    psql postgres -c "CREATE DATABASE migrateiq OWNER migrateiq;" 2>/dev/null || true
    DB_READY=true

  # Try native pg_ctlcluster (Linux)
  elif command -v pg_ctlcluster &>/dev/null; then
    echo "Attempting to start native PostgreSQL..."
    sudo pg_ctlcluster 16 main start 2>/dev/null || sudo pg_ctlcluster 15 main start 2>/dev/null || true
    sudo -u postgres psql -c "CREATE USER migrateiq WITH PASSWORD 'password';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE migrateiq OWNER migrateiq;" 2>/dev/null || true
    DB_READY=true

  else
    echo ""
    echo "⚠️  PostgreSQL could not be started automatically."
    echo ""
    echo "Please start PostgreSQL manually, then re-run this script."
    echo ""
    echo "Option A — Install Docker Desktop (recommended):"
    echo "  https://www.docker.com/products/docker-desktop/"
    echo "  Then: docker run -d --name migrateiq-postgres \\"
    echo "    -e POSTGRES_USER=migrateiq -e POSTGRES_PASSWORD=password \\"
    echo "    -e POSTGRES_DB=migrateiq -p 5432:5432 pgvector/pgvector:pg16"
    echo ""
    echo "Option B — macOS Homebrew:"
    echo "  brew install postgresql@16"
    echo "  brew services start postgresql@16"
    echo "  psql postgres -c \"CREATE USER migrateiq WITH PASSWORD 'password';\""
    echo "  psql postgres -c \"CREATE DATABASE migrateiq OWNER migrateiq;\""
    echo "  Then install pgvector: https://github.com/pgvector/pgvector"
    echo ""
    echo "Option C — Ubuntu/Debian:"
    echo "  sudo apt install postgresql postgresql-contrib"
    echo "  sudo -u postgres psql -c \"CREATE USER migrateiq WITH PASSWORD 'password';\""
    echo "  sudo -u postgres psql -c \"CREATE DATABASE migrateiq OWNER migrateiq;\""
    echo "  # pgvector: sudo apt install postgresql-16-pgvector"
    echo ""
    echo "Option D — Windows WSL2:"
    echo "  Use Docker Desktop with WSL2 backend (Option A above)."
    echo ""
    echo "After PostgreSQL is running, update DATABASE_URL in backend/.env and re-run."
    exit 1
  fi
fi

if [ "$DB_READY" = false ]; then
  echo "✗ Could not connect to PostgreSQL. Check your installation."
  exit 1
fi

# ── 2. Backend ───────────────────────────────────────────────
echo ""
echo "--- Step 2: Backend (Python) ---"
cd "$ROOT_DIR/backend"

if [ ! -d .venv ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements.txt -q --no-warn-script-location
echo "Installing ML deps (optional — skip if slow)..."
pip install -r requirements-ml.txt -q --no-warn-script-location 2>/dev/null || echo "  (ML deps skipped — app will use fallback embedder)"

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Created backend/.env from example."
  echo "    Add your Anthropic API key:"
  echo "    ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
fi

# Run Alembic migrations (must run from backend/ directory)
echo "Running database migrations..."
cd "$ROOT_DIR/backend"
alembic upgrade head
echo "✓ Migrations complete"

# ── 3. Frontend ──────────────────────────────────────────────
echo ""
echo "--- Step 3: Frontend (Node.js) ---"
cd "$ROOT_DIR/frontend"

if ! command -v node &>/dev/null; then
  echo "✗ Node.js not found. Install from https://nodejs.org (v18+)"
  exit 1
fi
NODE_VER=$(node --version | cut -d. -f1 | tr -d 'v')
if [ "$NODE_VER" -lt 18 ]; then
  echo "✗ Node.js v18+ required (found $(node --version))"
  exit 1
fi

echo "Installing npm packages..."
npm install --silent

if [ ! -f .env.local ]; then
  cp .env.example .env.local
fi
echo "✓ Frontend ready"

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "========================================="
echo " MigrateIQ setup complete ✓"
echo "========================================="
echo ""
echo "Start the backend (Terminal 1):"
echo "  cd $ROOT_DIR/backend"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Start the frontend (Terminal 2):"
echo "  cd $ROOT_DIR/frontend"
echo "  npm run dev"
echo ""
echo "  API docs → http://localhost:8000/docs"
echo "  App      → http://localhost:5173"
echo ""
echo "Tip: edit backend/.env to add your ANTHROPIC_API_KEY"
echo "     before running the mapping pipeline."
