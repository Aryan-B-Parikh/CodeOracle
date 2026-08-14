# CodeOracle

**An Evidence-Driven AI Agent for Understanding and Safely Modernizing Legacy Software.**

CodeOracle turns undocumented legacy codebases into understandable architecture, tested code, and safety-verified modernization plans. Upload a ZIP or import a GitHub repo $\rightarrow$ the system builds a static-analysis knowledge graph $\rightarrow$ AI explains code with verifiable `file:line` citations, generates test suites in an automatic $>60\%$ coverage loop, and proposes refactors with breaking-change detection and a 4-pillar Safety Score. Original code is never modified.

---

## 🏛 Architecture & Tech Stack

| Layer | Technology | Architectural Rationale |
|---|---|---|
| **Frontend UI** | React 18, TypeScript, Vite | 5-workspace responsive SPA with custom design system tokens |
| **Interactive Graph** | Custom SVG/Canvas Graph Engine | Pan/zoom, cycle path visualization, blast radius inspection drawer |
| **Backend API** | FastAPI, SQLAlchemy 2.x | Asynchronous REST endpoints with typed Pydantic V2 envelopes |
| **Task Queue** | Celery + Redis | Asynchronous parallel pipeline worker pool for repository analysis |
| **Static Analyzers** | Tree-Sitter (`tree-sitter-java`), Python `ast`, Radon | Deterministic ground-truth parsing (no LLM hallucination) |
| **Knowledge Graph** | NetworkX, SQL Relational Graphs | Circular dependency cycle detection, caller/callee fan-in/fan-out |
| **Semantic Store** | PostgreSQL 15 + `pgvector` (HNSW) | Multi-level semantic embeddings (`module`, `class`, `function`) |
| **AI Gateway** | Provider-Agnostic LLM Gateway | Zero-leakage token budgeting (OpenAI, Anthropic, Mock fallback) |
| **Execution Sandbox** | Docker (fail-closed cgroup isolation) | Hermetic, offline test runner (`pytest-cov`, `JUnit 4`/`JaCoCo`) |

---

## 🛡️ Security Model & Ingestion Hardening

CodeOracle enforces multi-layered defense-in-depth across remote ingestion and code execution:

1. **Strict Protocol Whitelist**: Only secure remote `https://` (and `http://`) Git schemes are accepted. Protocols like `file://`, `ssh://`, `git@` SCP syntax, and UNC paths are rejected immediately ($422$).
2. **Fail-Closed DNS SSRF Resolution**: All destination hostnames are resolved via `socket.getaddrinfo()`. If DNS resolution fails, or if any resolved IP maps to loopback (`127.0.0.1`, `::1`), private networks (`10.*`, `172.16-31.*`, `192.168.*`), link-local (`169.254.*`), or multicast/reserved blocks, the request is rejected before any network socket connects.
3. **Hermetic Docker Sandbox**:
   - Dropped capabilities: `--cap-drop ALL`, `--security-opt no-new-privileges`
   - Network isolation: `--network none` (no outbound egress)
   - Resource limits: CPU $1.0$, Memory $512\text{MB}$, PIDs limit $128$, tmpfs $/tmp$ ($64\text{MB}$)
   - Output flood protection: Hard caps on stdout/stderr ($1\text{MB}$) to eliminate memory exhaustion.

---

## 🧪 Automatic Test Generation & Coverage Repair Loop

CodeOracle implements an unbroken automatic test-generation and repair loop:

$$\text{Scan Repository} \longrightarrow \text{Generate Initial Tests} \longrightarrow \text{Docker Sandbox Execution} \longrightarrow \text{Iterative Repair} \longrightarrow \ge 60\% \text{ Line Coverage}$$

- **Real `coverage.py` / `JaCoCo` Measurement**: Line and branch coverage are measured from genuine test coverage reports (no synthetic or fabricated metrics).
- **Targeted Repair**: Automatically identifies uncovered line numbers and generates targeted test cases to cover missing branches and exception paths.
- **Benchmark Proven**: Verified on the legacy demo repository moving from $45.7\%$ baseline $\rightarrow$ $62.9\%$ $\rightarrow$ $80.0\%$ $\rightarrow$ **$94.3\%$ final coverage** in $3$ iterations.

---

## 🔍 Grounded Explanations & Behavioral Safety

### Grounded 10-Field Explanations
Every AI-generated explanation is strictly anchored to static AST facts:
- **Structure**: Purpose, Business Rules, Inputs, Outputs, Control Flow, Dependencies, Error Handling, Side Effects, Cyclomatic Complexity, Risks.
- **Static Citations**: Every claim links to an exact source code span (`L{start}–L{end}`) with code snippets and caller/callee blast radius.

### Refactor Modernization & Safety Engine
- **Behavioral Verification**: Compares sandbox test suite results between original and modern code:
  - `BEHAVIOR_PRESERVED` (Green) — all tests pass identically.
  - `BEHAVIOR_MUTATED` (Red) — test regressions or behavioral divergence detected.
  - `UNVERIFIED` (Amber) — clearly warns when no proposal-bound test execution exists.
- **Breaking Changes**: Detects signature mutations, changed parameter names, return type shifts, and flags impacted callers.
- **4-Pillar Safety Score**:
  $$\text{Safety Score} = 0.35 \times \text{API} + 0.25 \times \text{Tests} + 0.20 \times \text{Dependencies} + 0.20 \times \text{Behavior}$$

---

## ⚡ Scalability Benchmark (10,000+ LOC)

The static analysis pipeline is engineered for high throughput:
- **10,000+ LOC Parsing**: Benchmark suite processes $\ge 10,000$ lines of code and hundreds of entities across parallel Celery workers in **$<20$ seconds**.
- **Deterministic Aggregation**: Language and path ordering ensures reproducible graph outputs regardless of worker completion order.

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- Docker (for sandbox test execution)
- PostgreSQL 15+ with `pgvector` & Redis (optional; SQLite & eager Celery supported for offline testing)

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 2. Celery Worker (Optional for background queues)
```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

API Documentation (Swagger UI): `http://localhost:8000/docs`  
Web Dashboard: `http://localhost:5173`

---

## 📊 Verification & Quality Gates

```bash
# Backend Quality Gates
ruff check backend/app
mypy backend/app
pytest backend/tests -v
python benchmark/legacy_demo/python/run_benchmark.py

# Frontend Quality Gates
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```
