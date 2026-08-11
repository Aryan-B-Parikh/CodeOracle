# CLAUDE.md

Single source of truth for AI coding tools working on this repo. Read this first, then the referenced docs.

## What this is

**CodeOracle** — an evidence-driven AI agent for understanding and safely modernizing legacy software. Upload a ZIP/GitHub repo → static-analysis knowledge graph → AI explanations with `file:line` citations → test generation in a `>60%` line-coverage loop → modernization proposals with breaking-change detection and a Refactor Safety Score. Original code is never modified.

## Stack (do not swap without an ADR — see docs/06)

- **Frontend:** React + Vite + TypeScript + Tailwind, Monaco, React Flow, Recharts, TanStack Query
- **Backend:** Python 3.11+, FastAPI, Celery + Redis, SQLAlchemy 2.x + Alembic
- **Analysis:** Python `ast` + tree-sitter (incl. `tree-sitter-java` for Java), NetworkX, Radon
- **Storage:** PostgreSQL 15 + pgvector (HNSW)
- **AI:** LLM API behind a provider-agnostic gateway (`LLM_PROVIDER`/`LLM_MODEL` env-driven)
- **Execution:** Docker sandbox (pytest + coverage.py, JUnit + JaCoCo); never run uploaded code on the host

## Golden principle

**The AI reasons over facts from static analysis; it never replaces it.** The graph/AST/test results are ground truth. The LLM never receives the whole repository — only retrieved relevant functions + dependency neighbors + docs + static facts. Every AI claim must cite `file:line` evidence. Never infer behavior unsupported by the supplied code.

## Hard constraints

1. Refactors are proposals in a diff viewer only — never modify original uploaded code.
2. Tests run only inside the Docker sandbox (CPU/memory limits + timeout). Never execute uploaded code on the backend host.
3. Never send full repos (10K LOC) to the LLM — always go through retrieval.
4. Languages: Python + Java only (MVP).
5. Secrets never hardcoded, never logged; `.env` gitignored, commit only `.env.example`.
6. Do not swap ORM, state manager, vector store, or LLM provider mechanism without an ADR.

## Conventions (summary — full details in docs/04)

- Backend: Black (line-length 100), Ruff, mypy, fully-typed signatures, pydantic schemas in `backend/app/schemas/`. Parsers/graph modules are pure (no I/O, no LLM).
- Frontend: Prettier (`singleQuote`, no semi), ESLint + TS recommended, one component per PascalCase file.
- DB: snake_case tables/columns, UUID PKs, `<entity>_id` FKs, `created_at`/`updated_at`.
- API: `/api/v1/...`, JSON keys camelCase, shared envelope `{ "data", "error" }`.
- Graph entity types: `function` / `method` / `class` / `interface` / `enum` / `record` / `annotation`.

## Quality gates (run before finishing any task)

```bash
# backend
ruff check backend/app
mypy backend/app
pytest backend/tests

# frontend
cd frontend && npm run lint && npm run typecheck && npm run test
```

## Key commands

```bash
# backend dev
cd backend && uvicorn app.main:app --reload --port 8000
celery -A app.workers.celery_app worker --loglevel=info

# migrate
cd backend && alembic upgrade head

# frontend dev
cd frontend && npm run dev

# sandbox image
cd backend/sandbox && docker build -t codeoracle/sandbox:latest .

# sandbox run (returns canonical coverage JSON: lineCoverage/branchCoverage/uncoveredLines)
cd backend/sandbox && python run.py --language python --source <repo-dir> [--tests <tests-dir>]
cd backend/sandbox && python run.py --language java --source <maven-project-root>
```

Env vars: `DATABASE_URL`, `REDIS_URL`, `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_MODEL`, `SANDBOX_IMAGE`, `SANDBOX_TIMEOUT_SECONDS`, `UPLOAD_DIR`, `LOG_LEVEL`. See docs/05.

## How to work on this repo

1. Read `docs/07-task-breakdown.md`; pick one task at a time with its acceptance criteria (do NOT implement the whole PRD at once).
2. After changes, update docs/`DECISIONS.md` immediately if you deviate from the plan.
3. Verify: acceptance criteria + quality gates. Tests live in `backend/tests/` with committed golden fixtures under `backend/tests/fixtures/`.
4. Update docs when behavior/contracts change (PRD, data model, ADRs).

## Docs index

- `docs/01-prd.md` — requirements, user stories, non-goals
- `docs/02-architecture.md` — stack, system design, why
- `docs/03-data-model.md` — schema, entities, API contracts, naming
- `docs/04-coding-conventions.md` — style guide, layout, error/logging
- `docs/05-environment-setup.md` — local run, env vars, sandbox, secrets
- `docs/06-codebase-context.md` — workflow + ADRs (001–007)
- `docs/07-task-breakdown.md` — tasks T-01..T-21 with acceptance criteria
- `docs/08-testing-strategy.md` — test pyramid + coverage loop
- `DECISIONS.md` — decision log
