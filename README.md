# CodeOracle

**An Evidence-Driven AI Agent for Understanding and Safely Modernizing Legacy Software.**

CodeOracle turns undocumented legacy repositories into understandable architecture, tested code, and safety-verified modernization plans. Upload a ZIP or GitHub repo → the system builds a static-analysis knowledge graph → AI explains with `file:line` citations, generates tests in a `>60%` coverage loop, and proposes refactors with a breaking-change report and safety score. Original code is never modified.

## Highlights

- **Evidence-backed AI** — every claim cites exact file + line ranges (no hallucination).
- **Repository knowledge graph** — functions, calls, imports, complexity, circular deps, high-risk nodes.
- **Test → Coverage → Repair loop** — automatic pytest/JUnit generation targeting `>60%` line coverage.
- **Safe modernization** — diff viewer, breaking-change detection with impacted callers, Refactor Safety Score.
- **Python + Java** — tree-sitter (incl. `tree-sitter-java`) / Python `ast` static ground truth.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React + Vite + Tailwind, Monaco, React Flow, Recharts |
| Backend | FastAPI, Celery + Redis |
| Analysis | Tree-sitter (+ `tree-sitter-java`), Python `ast`, NetworkX, Radon |
| Storage | PostgreSQL 15 + pgvector |
| AI | LLM API behind a provider-agnostic gateway |
| Execution | Docker sandbox (pytest/coverage.py, JUnit/JaCoCo) |

## Quickstart

See `docs/05-environment-setup.md` for full setup. TL;DR:

```bash
# backend
cd backend && pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env        # fill DATABASE_URL, REDIS_URL, LLM_API_KEY
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# worker
celery -A app.workers.celery_app worker --loglevel=info

# frontend
cd frontend && npm install && npm run dev
```

API docs (Swagger): http://localhost:8000/docs — Frontend: http://localhost:5173

## Docs

| Doc | Purpose |
|---|---|
| `CLAUDE.md` | Single source of truth — read this first |
| `docs/01-prd.md` | Requirements, user stories, non-goals |
| `docs/02-architecture.md` | Tech stack + system design + rationale |
| `docs/03-data-model.md` | Schema, entities, API contracts, naming |
| `docs/04-coding-conventions.md` | Style guide, layout, error/logging |
| `docs/05-environment-setup.md` | Local run, env vars, sandbox, secrets |
| `docs/06-codebase-context.md` | CONTRIBUTING summary + ADRs |
| `docs/07-task-breakdown.md` | Task list + acceptance criteria |
| `docs/08-testing-strategy.md` | Test strategy incl. the coverage loop |
| `DECISIONS.md` | Decision log (append as decisions change) |

## License

TBD.
