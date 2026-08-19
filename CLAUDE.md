# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**MigrateIQ** — AI-first Relius → Omni / FRP pension data migration utility. FastAPI backend + React/Vite frontend, plus an AI pipeline (Anthropic Claude + pgvector embeddings) that semantically maps source schema fields to target schema fields.

### v5 Knowledge-Base architecture (current)
The app is organised around **two one-time Knowledge Bases** plus **repeatable migration projects** — not the old linear 8-screen flow.
- **Home** launchpad shows KB build status; a New Project is gated until both KBs are built.
- **Relius KB** (`rkb` flow, 2 steps): upload schema → review/approve domains → save.
- **Omni KB** (`okb` flow, 5 steps): upload schema → review records → upload transaction-card layouts → review card layouts + **Omni load order + constants registry** → summary & save.
- **Migration project** (`mig` flow, 4 steps): select Relius tables (from the KB) → AI mapping with **Omni transaction-card (T-code) assignment** → transaction cards → **batch run** that writes fixed-width Omni transaction-card `.txt` output.
- **Observability** dashboard: real audit events + headline counts.
- **Removed** from the v5 flow: recon/cutover and ETL codegen. `recon.py`/`etl.py`/`counter_sync.py`/`codegen.py` remain on disk but their routers are **not mounted**; `codegen.py`'s `OMNI_LOAD_ORDER` is still the reference load ordering.

## Common commands

### Setup & run (preferred entrypoint)
```bash
./start.sh setup       # one-time: starts pg, creates DB, venv, npm install, runs migrations
./start.sh             # run backend (8000) + frontend (5173) together
./start.sh backend     # backend only
./start.sh frontend    # frontend only
./start.sh db          # postgres only
```

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000     # API on :8000, docs at /docs
alembic upgrade head                            # apply migrations (MUST be run from backend/)
alembic revision --autogenerate -m "..."        # create migration after model edits
pytest                                          # run tests (pytest + pytest-asyncio configured)
pytest tests/unit/test_foo.py::test_bar         # single test
```

### Frontend (run from `frontend/`)
```bash
npm run dev          # vite dev server on :5173 with /api proxy → :8000
npm run build        # tsc + vite build
npm run typecheck    # tsc --noEmit
npm run lint         # eslint src --ext .ts,.tsx
```

### Reset a broken local DB
```bash
psql postgres -c "DROP DATABASE IF EXISTS migrateiq;"
psql postgres -c "CREATE DATABASE migrateiq OWNER migrateiq;"
cd backend && source .venv/bin/activate && alembic upgrade head
```

## Architecture

### Three-tier with an AI pipeline in the middle
```
React (Vite, Zustand, axios)  ──HTTPS──▶  FastAPI (async SQLAlchemy)  ──▶  PostgreSQL + pgvector
                                          │
                                          ├─ Anthropic Claude (semantic mapping, ETL codegen)
                                          └─ embeddings (all-mpnet-base-v2, 768-dim)
```

### Backend layout (`backend/app/`)
- `main.py` — FastAPI app factory; mounts all routers under `/api/v1`; runs `init_db()` (creates `vector` + `pg_trgm` extensions, then `create_all` as a dev safety net) on lifespan startup.
- `core/config.py` — single source of truth for settings via `pydantic-settings`. Always `from app.core.config import get_settings`; never read `os.environ`. `settings.ai_enabled` gates AI features on a valid `sk-...` key.
- `db/session.py` — lazy async engine, `get_db()` FastAPI dep yields a session per request and auto-commits/rolls back.
- `models/models.py` — **all SQLAlchemy ORM models live in this one file**. Core: `Engagement` (= the migration project) → owns `SchemaFile`, `DomainReview`, `MappingEntry`, `AuditEvent`. **v5 KB models**: `KnowledgeBase` (one per `kind` relius|omni; holds `stats`, and for Omni `load_order`+`constants`) → `KBReliusDomain`/`KBReliusField`, `KBOmniRecord`/`KBOmniField`, `KBTransactionCard`/`KBTransactionCardField`. **v5 project models** (new tables so `create_all` works without altering existing ones): `ProjectState` (selected tables + approved cards), `ProjectMapping` (proposals + T-code + overrides), `ProjectExport` (batch `.txt` output).
- `schemas/schemas.py` — Pydantic request/response models (all in one file, mirrors models layout).
- `api/routes/` — one router per resource group. **v5**: `knowledge_base.py` (`/knowledge-bases`, Relius + Omni analyze/review/save), `project.py` (`/engagements/{id}/project/*` — tables, mapping, cards, batch), `observability.py` (`/observability`). `etl.py`/`recon.py` exist but are **not mounted**.
- `services/kb/` — **v5 seed catalogues**: `relius_seed.py` (domains+fields), `omni_seed.py` (records, transaction cards, load order, constants), `mapping_seed.py` (proposal catalogue + `derive_txn_code`).
- `services/schema/` — `extractor.py` parses uploaded SQL/JSON/XLSX/PDF/DOCX schemas; `profiler.py` profiles them (used by the legacy engagement-scoped upload, still mounted).
- `services/ai/` — `rag.py` builds field embeddings + semantic retrieval; `mapper.py` is the Claude-driven semantic mapper.
- `services/pipeline/` — **v5**: `txn_export.py` builds the fixed-width Omni transaction-card `.txt` (`build_card_line`/`generate_export`). Retired-but-present: `codegen.py` (keeps `OMNI_LOAD_ORDER`), `rules.py`, `recon_engine.py`, `counter_sync.py`.
- `migrations/` — Alembic; head is `003_v5_kb_architecture`. `alembic.ini` has `prepend_sys_path = .`, so **always run `alembic` from `backend/`**. Note `init_db()`'s `create_all` makes new tables in dev but does NOT alter existing ones — schema changes to existing tables need a migration. See `backend/RUNNING_ALEMBIC.md`.

### Frontend layout (`frontend/src/`)
- **Flow + screen navigation** in `nav.ts` (`SCREEN_META`, flows `rkb`/`okb`/`mig` + `home`/`obs`) — replaces the old linear 1–8 `currentStep`. `App.tsx` switches on `currentScreen`; screens live in `components/screens/` (`Home`, `ReliusSchema/Review`, `Omni*`, `SelectTables`, `AIMapping`, `TransactionCards`, `BatchRun`, `Observability`).
- **Single Zustand store** in `store/index.ts`, slices: navigation, knowledge bases (Relius+Omni), migration project, engagement, notifications. All API calls go through `services/api.ts` (`api.knowledgeBases.*`, `api.project.*`, `api.observability.*`).
- Path alias `@/*` → `src/*` (set in both `tsconfig.json` and `vite.config.ts`).
- Vite dev proxies `/api` → `VITE_API_URL` (default `http://localhost:8000`).

### Key conventions worth knowing before changing things
- **Async all the way** in the backend — SQLAlchemy 2.0 async engine, `asyncpg` driver at runtime; Alembic uses sync `psycopg2-binary`. The URL conversion happens in `Settings.database_url_async`.
- **AuditEvent is append-only** (`audit_events`). Never `UPDATE` or `DELETE` rows — every system / AI / human action is logged here, indexed by `(engagement_id, created_at)` and `event_type`.
- **Navigation is flow-relative** (v5): the store's `currentScreen` + `nav.ts` `SCREEN_META` drive screens within a flow (`rkb`/`okb`/`mig`); the old linear `current_step`/`max_unlocked` counters on `Engagement` are legacy (the step bound was relaxed to `le=20`).
- **KBs seed from reference catalogues** in `services/kb/*_seed.py` (ported from the v5 prototype) so a KB is always populated on "analyze"; real schema/transaction-layout extraction augments this later. `analyze`/`save` endpoints are idempotent.
- **A migration project requires both KBs built** — New Project is gated on `GET /knowledge-bases` → `both_built`.
- **AI features are optional.** Without `ANTHROPIC_API_KEY`, schema upload / parsing / UI all still work — only mapping (P2), codegen (P3), and failure explanation degrade. Check `settings.ai_enabled` before calling Claude.
- **pgvector is optional in code too.** `models.py` falls back to `JSONB` for embedding columns if `pgvector` isn't importable; `init_db()` tries `CREATE EXTENSION` in an isolated AUTOCOMMIT connection so a missing extension never poisons startup.
- The Omni load order is **business-critical** — records must load in the exact order (Plan → Division → Fund Control → … → File Maintenance). Domain-level order lives in `services/pipeline/codegen.py` (`OMNI_LOAD_ORDER`); the record-level display order is seeded on the Omni KB (`omni_seed.OMNI_LOAD_ORDER`).

## Prerequisites
- Python 3.12+ (Settings/models are `from __future__ import annotations`; code claims 3.9+ compat but README pins 3.12)
- Node 18+ (22+ per README)
- PostgreSQL 16, ideally with `pgvector` and `pg_trgm` extensions (`brew install pgvector` on macOS)
- Anthropic API key for AI features (put in `backend/.env` as `ANTHROPIC_API_KEY=sk-...`)

## Reference docs in this repo
- `README.md` — architecture diagram, repo layout, build sequence
- `LOCALDEV.md` — quickest path to a running local stack
- `RUNBOOK.md` — exhaustive step-by-step for every restart scenario
- `backend/RUNNING_ALEMBIC.md` — migration commands and the working-directory gotcha
