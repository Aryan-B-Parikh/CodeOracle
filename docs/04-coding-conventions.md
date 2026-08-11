# 4. Coding Conventions / Style Guide

## Backend (Python 3.11+, FastAPI)

- **Formatting:** Black (`line-length=100`).
- **Linting:** Ruff (all default rulesets); run `ruff check .` before commit.
- **Typing:** Fully typed signatures; use `pydantic` models for all API payloads and internal data structures. No untyped dicts crossing module boundaries.
- **Pydantic models** live in `schemas/`, one file per domain.
- **DB access:** SQLAlchemy 2.x ORM for queries; **do not** swap in another ORM or a raw-SQL layer without an ADR. Migrations via Alembic.
- **Async:** FastAPI endpoints are `async def`; long jobs are handed to Celery tasks, never awaited inline.
- **Imports:** stdlib → third-party → local; sorted (Ruff `I` rule).
- **Error handling:** exceptions → FastAPI exception handlers returning the shared error envelope (`docs/03-data-model.md`). Never leak stack traces or secrets in responses.
- **Logging:** module-level logger `logging.getLogger(__name__)`, structured-ish `key=value` lines. Never log secrets, API keys, or uploaded source content verbatim — log file paths and line counts only.
- **Static analysis modules** (parsers, graph builder) are pure: no I/O, no LLM calls; they return plain typed data structures so they are unit-testable.

## Frontend (React + Vite + TypeScript + Tailwind)

- **Formatting:** Prettier (`singleQuote: true`, `semi: false`).
- **Linting:** ESLint with `@typescript-eslint` recommended + React hooks rules.
- **Components:** named function components, one component per file, PascalCase filenames matching the component (`BillingGraph.tsx`).
- **Pages** under `src/pages/`, components under `src/components/`, API client under `src/api/`, hooks under `src/hooks/`.
- **State:** server state via TanStack Query; local UI state via `useState`. Do not introduce Redux/Zustand without an ADR.
- **Styling:** Tailwind utility classes; no inline `style` unless dynamic/positional (e.g. React Flow nodes).
- **Charts/graph:** React Flow for dependency graph, Recharts for coverage/safety dashboards, Monaco for code/diff.

## Repository layout

```
/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (upload, analysis, results, tests, refactor)
│   │   ├── schemas/        # pydantic models
│   │   ├── services/       # orchestrators (explanation, tests, refactor, safety)
│   │   ├── analyzers/      # ast / tree-sitter (+ tree-sitter-java) → typed AST facts
│   │   ├── graph/          # NetworkX builders + algos (circular, high-risk)
│   │   ├── index/          # chunking + embeddings + pgvector
│   │   ├── llm/            # provider-agnostic LLM gateway + prompts
│   │   ├── workers/        # Celery tasks
│   │   └── db/             # SQLAlchemy models, Alembic migrations
│   ├── tests/              # backend unit/integration tests
│   └── sandbox/            # Docker runner for test execution
├── frontend/
│   └── src/
│       ├── pages/  components/  api/  hooks/  utils/
├── docs/                     # this documentation set
├── CLAUDE.md                 # single source of truth
├── DECISIONS.md              # decision log
└── README.md
```

## Naming patterns

- **Python:** `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, `CAPITALIZED_SNAKE_CASE` module names for `LLM`, `AST` acronyms.
- **TypeScript:** `camelCase` functions/vars, `PascalCase` components/types, `UPPER_SNAKE_CASE` constants.
- **API JSON keys:** `camelCase`.
- **DB:** see `docs/03-data-model.md` (snake_case tables/columns).
- **Entity types in graph:** `function` / `method` / `class`.

## Error handling & logging conventions

- All API errors return the envelope `{ "data": null, "error": { "code", "message" } }`.
- Backend: raise domain exceptions → handled centrally; unexpected exceptions become `500 INTERNAL` with a logged traceback and an opaque message.
- Frontend: TanStack Query error handling per page; never surface raw server traces.
- Log levels: `INFO` for pipeline stage transitions, `WARN` for recoverable issues, `ERROR` for failures with a traceback. Correlation id (analysis/job id) in every log line.
