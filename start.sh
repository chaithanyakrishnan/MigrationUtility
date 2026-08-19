#!/bin/bash
# MigrateIQ — local dev starter
# Usage:
#   ./start.sh          → start everything (backend + frontend)
#   ./start.sh backend  → backend only
#   ./start.sh frontend → frontend only
#   ./start.sh setup    → first-time setup (install deps, create DB)
#   ./start.sh db       → start postgres only

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── Colours ──────────────────────────────────────────────────
GRN='\033[0;32m'; YLW='\033[0;33m'; RED='\033[0;31m'; RST='\033[0m'; BLD='\033[1m'
ok()   { echo -e "${GRN}✓${RST} $1"; }
warn() { echo -e "${YLW}!${RST} $1"; }
err()  { echo -e "${RED}✗${RST} $1"; exit 1; }
hdr()  { echo -e "\n${BLD}$1${RST}"; }

# ── Helpers ───────────────────────────────────────────────────
check_postgres() {
  pg_isready -h localhost -p 5432 -q 2>/dev/null
}

start_postgres_brew() {
  if brew services list 2>/dev/null | grep -qE "postgresql(@\d+)?\s+started"; then
    return 0
  fi
  # Try pg16 first, then pg15, then generic
  for svc in postgresql@16 postgresql@15 postgresql; do
    if brew list "$svc" &>/dev/null 2>&1; then
      brew services start "$svc" &>/dev/null
      sleep 2
      return 0
    fi
  done
  return 1
}

ensure_postgres() {
  if check_postgres; then ok "PostgreSQL already running"; return; fi

  hdr "Starting PostgreSQL..."
  # macOS: try Homebrew
  if command -v brew &>/dev/null; then
    if start_postgres_brew; then
      sleep 1
      check_postgres && ok "PostgreSQL started" && return
    fi
  fi
  # Linux: try systemctl
  if command -v systemctl &>/dev/null; then
    sudo systemctl start postgresql 2>/dev/null && sleep 1
    check_postgres && ok "PostgreSQL started" && return
  fi

  err "PostgreSQL is not running and could not be started automatically.
  
  Start it manually, then re-run this script:
    macOS:  brew services start postgresql@16
    Linux:  sudo systemctl start postgresql
    
  Or see README.md for full setup instructions."
}

ensure_db_exists() {
  # Create DB and user if they don't exist (silently skip if they do)
  if command -v psql &>/dev/null; then
    psql postgres -c "CREATE USER migrateiq WITH PASSWORD 'password';" 2>/dev/null || true
    psql postgres -c "CREATE DATABASE migrateiq OWNER migrateiq;" 2>/dev/null || true
  elif command -v brew &>/dev/null; then
    # Try with the postgres superuser via brew
    local pg_bin
    for d in /opt/homebrew/opt/postgresql@16/bin /opt/homebrew/opt/postgresql@15/bin \
              /usr/local/opt/postgresql@16/bin /usr/local/opt/postgresql@15/bin; do
      [ -d "$d" ] && pg_bin="$d" && break
    done
    if [ -n "$pg_bin" ]; then
      "$pg_bin/createuser" -s migrateiq 2>/dev/null || true
      "$pg_bin/createdb"   -O migrateiq migrateiq 2>/dev/null || true
    fi
  fi
}

setup_backend() {
  hdr "Backend setup"
  cd "$BACKEND"

  # Python venv
  if [ ! -d .venv ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv .venv
  fi
  ok "Python venv ready"

  # Activate
  source .venv/bin/activate

  # Install deps
  echo "  Installing Python packages (this takes ~60s on first run)..."
  pip install -r requirements.txt -q
  ok "Python packages installed"

  # .env
  if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env created — add your ANTHROPIC_API_KEY to backend/.env for AI features"
  else
    ok ".env already exists"
  fi

  # Run migrations
  echo "  Running database migrations..."
  cd "$BACKEND"
  alembic upgrade head 2>&1 | grep -v "^INFO" || true
  ok "Database migrations complete"
}

setup_frontend() {
  hdr "Frontend setup"
  cd "$FRONTEND"

  if ! command -v node &>/dev/null; then
    err "Node.js not found. Install from https://nodejs.org (v18+)"
  fi

  echo "  Installing npm packages (this takes ~30s on first run)..."
  npm install --silent
  ok "npm packages installed"

  if [ ! -f .env.local ]; then
    cp .env.example .env.local
    ok ".env.local created"
  else
    ok ".env.local already exists"
  fi
}

run_backend() {
  cd "$BACKEND"
  source .venv/bin/activate
  echo -e "${GRN}→${RST} Backend  http://localhost:8000  (API docs: http://localhost:8000/docs)"
  uvicorn app.main:app --reload --port 8000
}

run_frontend() {
  cd "$FRONTEND"
  echo -e "${GRN}→${RST} Frontend http://localhost:5173"
  npm run dev
}

# ── Main ──────────────────────────────────────────────────────
MODE="${1:-all}"

case "$MODE" in
  setup)
    ensure_postgres
    ensure_db_exists
    setup_backend
    setup_frontend
    echo ""
    echo -e "${GRN}${BLD}Setup complete!${RST}"
    echo ""
    echo "  Next: run  ./start.sh  to start the app"
    echo ""
    echo "  Or open in VS Code:"
    echo "    code $ROOT"
    echo "    Then press F5 to launch 'Full Stack'"
    ;;

  db)
    ensure_postgres
    ;;

  backend)
    ensure_postgres
    if [ ! -d "$BACKEND/.venv" ]; then setup_backend; fi
    run_backend
    ;;

  frontend)
    if [ ! -d "$FRONTEND/node_modules" ]; then setup_frontend; fi
    run_frontend
    ;;

  all|*)
    # Check setup is done
    if [ ! -d "$BACKEND/.venv" ] || [ ! -d "$FRONTEND/node_modules" ]; then
      hdr "First-time setup detected — running setup first..."
      ensure_postgres
      ensure_db_exists
      setup_backend
      setup_frontend
    else
      ensure_postgres
    fi

    echo ""
    echo -e "${BLD}Starting MigrateIQ...${RST}"
    echo -e "  ${GRN}→${RST} Backend  http://localhost:8000"
    echo -e "  ${GRN}→${RST} API docs http://localhost:8000/docs"
    echo -e "  ${GRN}→${RST} Frontend http://localhost:5173"
    echo -e "  Press Ctrl+C to stop"
    echo ""

    # Run backend in background, frontend in foreground
    cd "$BACKEND" && source .venv/bin/activate
    uvicorn app.main:app --reload --port 8000 &
    BACKEND_PID=$!
    trap "kill $BACKEND_PID 2>/dev/null; exit" INT TERM

    cd "$FRONTEND"
    npm run dev

    # If frontend exits, kill backend too
    kill $BACKEND_PID 2>/dev/null
    ;;
esac
