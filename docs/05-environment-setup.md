# 5. Environment & Setup

## Prerequisites

- Python 3.11+
- Node.js 18+ (npm)
- Docker Desktop (required for the sandbox runner)
- PostgreSQL 15+ with the `pgvector` extension enabled
- Redis (for Celery broker/result backend)

## Clone & install

```bash
git clone <repo-url> && cd CodeOrecal
```

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell)
# .venv/bin/activate             # macOS/Linux
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Environment variables (backend `.env`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg://user:pass@localhost:5432/codeoracle` |
| `REDIS_URL` | yes | `redis://localhost:6379/0` |
| `LLM_API_KEY` | yes | API key for the LLM provider |
| `LLM_PROVIDER` | no | `openai` (default); switch provider here — never in code |
| `LLM_MODEL` | no | model name |
| `EMBEDDING_MODEL` | no | embedding model name; dims must match `chunks.embedding` vector(1536) |
| `SANDBOX_IMAGE` | no | `codeoracle/sandbox:latest` |
| `SANDBOX_TIMEOUT_SECONDS` | no | default `300` |
| `UPLOAD_DIR` | no | where uploaded archives are staged |
| `LOG_LEVEL` | no | `INFO` default |

Copy `backend/.env.example` → `backend/.env` and fill in values. **Never commit `.env`.**

## Database setup

```bash
# one-time: enable extension (as postgres superuser)
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"

cd backend
alembic upgrade head
```

## Run locally (dev)

```bash
# terminal 1 — backend API
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2 — Celery worker
cd backend && celery -A app.workers.celery_app worker --loglevel=info

# terminal 3 — Redis (Docker)  [if not already running]
docker run -d --name codeoracle-redis -p 6379:6379 redis:7

# terminal 4 — PostgreSQL (Docker)  [if not already running]
docker run -d --name codeoracle-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=codeoracle -e POSTGRES_DB=codeoracle \
  pgvector/pgvector:pg15

# terminal 5 — frontend
cd frontend && npm run dev
```

- API: http://localhost:8000 (Swagger: `/docs`)
- Frontend: http://localhost:5173

## Sandbox

The test-execution sandbox is a Docker image that runs `pytest + coverage.py` (Python) or `JUnit + JaCoCo` (Java) against a **copy** of the uploaded code with CPU/memory limits and a hard timeout.

```bash
cd backend/sandbox
docker build -t codeoracle/sandbox:latest .
```

Run the sandbox via `backend/sandbox/run.py` — it stages the repo into a
read-only scratch copy, enforces every constraint in
`backend/sandbox/security-policy.md` (no network, CPU/memory limits, hard
timeout, non-root, read-only base), and returns canonical coverage JSON:

```bash
cd backend/sandbox
python run.py --language python --source <repo-dir> [--tests <tests-dir>]
python run.py --language java --source <maven-project-root>
```

No uploaded code is ever executed on the backend host or the DB host.

## Secrets / config handling rules

1. **Never hardcode secrets** (API keys, DB passwords) in source.
2. `.env` is gitignored; commit only `.env.example` with placeholder values.
3. Never log secrets or API keys; redact in logs.
4. Uploaded source content must not be written into logs; log paths + line counts only.
5. Never commit real uploaded repositories or sample data containing credentials.

## Common commands

```bash
# backend lint + typecheck
ruff check backend/app
mypy backend/app

# backend tests
pytest backend/tests

# frontend lint + typecheck
cd frontend && npm run lint && npm run typecheck

# frontend tests
cd frontend && npm run test
```

## Troubleshooting

- **pgvector index error** → confirm the `vector` extension exists before running migrations.
- **Celery tasks stuck** → confirm Redis is reachable and worker is running (`celery inspect ping`).
- **Sandbox hangs** → check `SANDBOX_TIMEOUT_SECONDS` and Docker resource limits.
