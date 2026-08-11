# 2. Architecture & Tech Stack

## Golden principle

**The AI reasons over facts extracted by static analysis; it does not replace static analysis.** The knowledge graph, AST metadata, and test results are ground truth. The LLM is a layer on top of that ground truth, never the source of it. This is what makes CodeOracle credible rather than "upload code → ChatGPT explains it."

## Recommended stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React + Vite + Tailwind CSS | SPA |
| Code editor | Monaco Editor | diffs + viewer |
| Graph | React Flow | dependency graph |
| Charts | Recharts | coverage/safety dashboards |
| Backend | Python 3.11+ / FastAPI | async API |
| Queue | Celery + Redis | background jobs |
| Parsing | Tree-sitter, Python `ast`, JavaParser | language analysis |
| Analysis | NetworkX, Radon | graph + complexity |
| Database | PostgreSQL 15 + pgvector | relational + embeddings |
| AI | LLM API behind an abstract gateway | switchable provider |
| Test execution | Docker sandbox | pytest/coverage.py, JUnit/JaCoCo |
| Deployment | Vercel (frontend) + Render/Railway/GCP (backend) | |

## Why these choices (do not "helpfully" swap them)

- **Python + Java** (not JS/C++): best legacy-modernization story. Python AST tooling is excellent and built-in; JavaParser is mature; pytest/JUnit are the de-facto test frameworks; refactoring complexity is medium vs. "very high" for C++.
- **FastAPI**: async, typed, auto OpenAPI spec for free (feeds the data-model/API-contract doc).
- **Celery + Redis**: long analysis/test jobs must not block API workers.
- **Tree-sitter + Python `ast` + JavaParser**: static ground truth. Tree-sitter is incremental & multi-language; Python `ast` is dependency-free for Python; JavaParser gives type info for Java.
- **NetworkX** for graph algorithms (circular dependency detection, centrality → high-risk nodes). **Radon** for complexity (CCN).
- **PostgreSQL + pgvector**: one store for relational metadata + `embedding` vectors; avoids running a second vector DB (FAISS is the fallback if pgvector ops become painful).
- **React Flow** (not a bespoke canvas): zoom, search, click, edge highlighting out of the box.
- **LLM API, not self-hosted**: hackathon-appropriate; keep a provider abstraction so the model is swappable.
- **Docker sandbox for execution**: never execute uploaded code on the backend host. CPU/memory limits + timeout mandatory.

## System overview

```
ZIP / GitHub Repo
        ↓
Repository Scanner (language detection, file classification)
        ↓
┌──────────────┬──────────────┐
│ Static Code  │ Code Chunking│
│ Parser       │ (module/class│
│ AST/tree-    │ /function +  │
│ sitter/Java  │ semantic     │
│ Parser:      │ chunks)      │
│ imports/calls│              │
└──────┬───────┴──────┬───────┘
       └──────┬───────┘
              ↓
   Code Knowledge Graph + Vector DB (pgvector)
              ↓
       ┌──────┴──────┐
       ↓             ↓
AI Explanation   AI Modernizer
       ↓             ↓
Test Generator   Safety Checker
       └──────┬─────┘
              ↓
        Web Dashboard
```

## Backend service layout

```
FastAPI
  ├── Upload API     → Storage
  ├── Analysis API   → Job Queue (Celery) → PostgreSQL
  └── Results API    ← PostgreSQL

Analysis Worker pipeline:
  Language AST Parser → Dependency Builder → Complexity Analyzer
        → Repository Graph (NetworkX)
        → Vector Index (pgvector)
        → [Explanation | Test Generator] → [Refactor Engine → Safety Checker]
```

## Handling 10,000+ LOC

- **Never send 10,000 lines to the LLM.** Flow: 10K LOC → parser → ~500 functions/classes → AST metadata → semantic chunks → embeddings → relevant-context retrieval → LLM.
- **Parallel processing:** files are processed independently (`file1.py → Worker 1`, etc.), then the graph is aggregated. This makes the 10K requirement realistic.
- LLM receives only: user question + retrieved relevant functions + dependency neighbors + relevant documentation + static-analysis facts.

## Multi-stage AI explanation pipeline

1. **Stage 1 — Static analysis:** imports, functions, classes, variables, calls, inheritance, control flow, complexity, dead code, circular dependencies.
2. **Stage 2 — Semantic indexing:** chunk at module/class/function level, embed, store in pgvector.
3. **Stage 3 — LLM reasoning:** system prompt = "senior software architect analyzing a legacy repository; never infer behavior unsupported by supplied code; for each function provide the 10 fields; cite exact file+line ranges supporting each claim."

## Frontend tab mapping (maps 1:1 to judging criteria)

1. **Explanation** — repository/module/function explanations with evidence.
2. **Dependency Graph** — static, zoomable, searchable, clickable, circular-dep + high-risk-node highlighting.
3. **Tests** — generated/passed/failed counts, line % + branch %, target `>60%` status, uncovered lines, "Generate Tests for Uncovered Code" button.
4. **Refactor** — original vs. proposed diff, WHY list, behavioral risk, breaking-change report (impact + affected files), Refactor Safety Score.

## Live pipeline UI

Show real progress (never a blank loader):

```
✓ Repository uploaded
✓ Language detection
✓ AST parsing
✓ Dependency extraction
✓ Complexity analysis
✓ Repository graph generated
⟳ Generating explanations
○ Generating unit tests
○ Running test suite
○ Analyzing refactor safety
```

## Deployment notes

- Frontend on Vercel; backend + worker on Render/Railway/GCP.
- PostgreSQL + pgvector as a managed service.
- Docker sandbox runner needs its own host/runner config (see `docs/05-environment-setup.md`).
