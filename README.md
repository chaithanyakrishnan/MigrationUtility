# MigrateIQ

**AI-first Relius → Omni / FRP pension data migration utility**

Cloud SaaS — FIS runs it for clients. Built iteratively.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (React + TypeScript)                               │
│  v5 Knowledge-Base workflow  ·  Observability dashboard     │
│  Home → Relius KB · Omni KB → Migration Project             │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS / REST
┌────────────────────▼────────────────────────────────────────┐
│  API tier  (FastAPI · Python 3.12)                          │
│  /api/v1/{knowledge-bases, engagements/.../project,          │
│           observability, engagements, schema, session}       │
└───┬────────────────┬───────────────┬────────────────────────┘
    │                │               │
┌───▼────┐    ┌──────▼──────┐  ┌────▼──────────────────────┐
│Airflow │    │  AI / ML    │  │  PostgreSQL + pgvector     │
│ DAGs   │    │  services   │  │  mapping_registry  (git)   │
│(phase  │    │  Claude API │  │  i4_learning_store         │
│ orch.) │    │  embeddings │  │  i3_audit_log              │
│        │    │  RAG store  │  │  session_state             │
└────────┘    └─────────────┘  └────────────────────────────┘
```

## Repository layout

```
migrateiq/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── api/routes/   # One file per resource group
│   │   ├── core/         # Config, security, logging
│   │   ├── services/
│   │   │   ├── ai/       # A1 RAG, A2 agent, P2.1 mapper, P2.2 scorer
│   │   │   ├── pipeline/ # P1–P5 phase services
│   │   │   └── schema/   # P1.1 extractor, P1.2 profiler
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   └── db/           # DB init, migrations (Alembic)
│   ├── tests/
│   └── requirements.txt
├── frontend/             # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── screens/  # 8 workflow screens + Observability
│   │   │   ├── shared/   # Reusable UI components
│   │   │   └── layout/   # Sidebar, topbar, bottombar
│   │   ├── hooks/        # useEngagement, useMapping, useSchema
│   │   ├── services/     # API client (auto-generated from OpenAPI)
│   │   ├── store/        # Zustand store slices
│   │   └── types/        # Shared TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── infra/
│   ├── docker/           # Compose files for local dev
│   ├── k8s/              # Kubernetes manifests (EKS/AKS)
│   └── terraform/        # AWS/Azure infrastructure as code
├── scripts/              # DB seed, migration helpers, dev tools
└── docs/                 # Architecture docs, ADRs
```

## Quick start (local dev)

### Prerequisites
- Python 3.12+
- Node 22+
- PostgreSQL 16 with pgvector extension
- Anthropic API key

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in ANTHROPIC_API_KEY, DATABASE_URL
alembic upgrade head           # run DB migrations
uvicorn app.main:app --reload  # starts on :8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local    # VITE_API_URL=http://localhost:8000
npm run dev                    # starts on :5173
```

### With Docker Compose
```bash
cd infra/docker
cp ../../backend/.env.example .env
docker compose up              # postgres + backend + frontend
```

## Build sequence

| Phase | What | Status |
|-------|------|--------|
| 4 | Architecture & Infrastructure | ✅ Complete |
| 3 | Technical Spec / PRD | 🔄 In progress |
| 2 | AI pipeline (P1–P5, A1–A4, I1–I4) | ⏳ Next |
| 1 | React frontend | ⏳ Parallel with Phase 2 |

## Iterative build approach

Each session builds the next component in dependency order:

1. **Foundation** — DB models, config, FastAPI skeleton, auth ← *start here*
2. **Schema services** — P1.1 extractor, P1.2 profiler, file upload API
3. **AI brain** — A1 RAG store, embeddings, A2 agent skeleton
4. **Mapping pipeline** — P2.1 semantic mapper, P2.2 scorer, P2.3 registry
5. **ETL codegen** — P3.1 codegen, P3.2 rule engine, P3.3 control files
6. **Validation** — P4.1–P4.5 suite, P5.1–P5.3 load/cutover
7. **Frontend** — React screens connected to live APIs
8. **Infra** — Docker Compose → Kubernetes → Terraform

---

*MigrateIQ · Confidential · FIS Internal*
