# 6. Existing Codebase Context

> This doc will grow as the repo does. Keep the README as the project overview; keep CONTRIBUTING as the workflow reference; use this file for architecture decision records (ADRs) explaining past tradeoffs.

## Project overview

See `README.md`.

## Team workflow

See `CONTRIBUTING.md` (branching, quality gates, definition of done).

## Architecture decision records (ADR)

ADRs are short: Context → Decision → Consequences. Append new ones here as decisions are made; never rewrite history silently.

### ADR-001 — Static analysis is ground truth; LLM reasons over facts only
- **Status:** Accepted
- **Context:** Generic LLM code explanation hallucinates. The system must be technically credible.
- **Decision:** The knowledge graph, AST metadata, and test results are authoritative. The LLM never receives a full 10K-LOC repository; it receives retrieved relevant functions, dependency neighbors, documentation, and static-analysis facts. Every AI claim must cite `file:line` evidence.
- **Consequences:** Higher engineering cost for parsers/indexing; lower hallucination risk; explainability is a differentiator.

### ADR-002 — Language support: Python + Java only (MVP)
- **Status:** Accepted (parser sub-choice updated by ADR-008)
- **Context:** Need strongest enterprise-modernization story for a hackathon; C++ refactoring complexity is very high; JS ecosystem split test runners.
- **Decision:** Python (`ast`/tree-sitter, pytest + coverage.py) and Java (tree-sitter-java, JUnit + JaCoCo). No C++/JS in MVP. (The original decision named JavaParser for Java; ADR-008 supersedes that parser choice.)
- **Consequences:** Clean scope; clear `>60%` coverage story in both languages.

### ADR-003 — PostgreSQL + pgvector (not FAISS)
- **Status:** Accepted
- **Context:** Need relational metadata + vector search; don't want to operate a second store.
- **Decision:** Single PostgreSQL 15 DB with pgvector for `chunks.embedding`. HNSW index. FAISS is the documented fallback if pgvector underperforms.
- **Consequences:** One store to manage; pgvector maturity acceptable for MVP.

### ADR-004 — LLM API behind a provider-agnostic gateway (no self-hosted model)
- **Status:** Accepted
- **Context:** Hackathon scale; no GPU budget; model choice may change.
- **Decision:** Abstract `llm/` gateway; `LLM_PROVIDER`/`LLM_MODEL` env-driven. Never call a provider SDK directly outside the gateway.
- **Consequences:** Swappable models; single place to manage prompts and token budgets.

### ADR-005 — Uploaded code executes only in a Docker sandbox
- **Status:** Accepted
- **Context:** Untrusted uploaded code must never run on the backend host.
- **Decision:** Test runs go through a sandbox container (CPU/memory limits, hard timeout, no internal network, copy of code). Original repo is never modified.
- **Consequences:** Extra infra (Docker) but non-negotiable for safety and credibility.

### ADR-006 — Celery + Redis for background jobs
- **Status:** Accepted
- **Context:** Analysis/test generation are long-running; API must stay responsive and the live pipeline UI needs progress.
- **Decision:** FastAPI stays thin; Celery workers run the pipeline, persisting `pipeline_state`/`status` to PostgreSQL.
- **Consequences:** Distributed-state complexity, but required for the live pipeline UX and parallel file processing.

### ADR-007 — Async file-level parallelism for 10K LOC
- **Status:** Accepted
- **Context:** A 10K-LOC repo must be analyzable quickly and deterministically.
- **Decision:** Files are parsed independently in parallel workers; per-file results are then aggregated into the repository graph.
- **Consequences:** Faster analysis; aggregation step must be deterministic (sort/merge semantics specified in code).

### ADR-008 — Java parsed with tree-sitter-java (not JavaParser)
- **Status:** Accepted
- **Context:** The stack originally specified JavaParser for Java. JavaParser requires a JVM; the backend host (and CI) does not guarantee one, and running Java tooling from the Python service adds a second runtime.
- **Decision:** Java is parsed with `tree-sitter-java` from `app/analyzers/java_parser.py`, returning the same typed `ParsedFile`/`ParsedEntity` shapes as the Python parser so one persistence service covers both languages. JavaParser is no longer an active dependency.
- **Consequences:** No JVM needed on the backend; same extraction coverage as T-04 (classes, methods, calls, imports, complexity). Cyclomatic complexity for Java uses decision-point counting (class = max of methods) rather than radon, which stays Python-only.

## Past tradeoffs tracker

| Date | Decision | Replaced by | ADR |
|---|---|---|---|
| 2026-08-11 | Initial stack locked | — | 001–007 |
| 2026-08-11 | Java parsed via JavaParser (ADR-002) | tree-sitter-java | 008 |

Append rows here when a decision changes; note the replacing ADR and the date in `DECISIONS.md` too.
