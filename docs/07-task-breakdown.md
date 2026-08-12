# 7. Task Breakdown

> Feed one task at a time to the AI, together with its acceptance criteria — not the whole PRD. Each task is small, well-scoped, and independently verifiable.

## Phase 0 — Project scaffold

- [ ] **T-01** Repo layout + CI
  - **AC:** `backend/`, `frontend/`, `docs/` scaffolded; ruff/mypy/pytest and eslint/prettier/typecheck wired; CI runs all gates on push; docs referenced from README.
- [ ] **T-02** Docker sandbox image
  - **AC:** Image builds; runs `pytest --cov` and `mvn test` on a fixture repo; enforces CPU/memory limit and timeout; returns coverage output as JSON.

## Phase 1 — Core ingestion

- [ ] **T-03** Repository scanner (upload + GitHub import)
  - **AC:** `POST /api/v1/repositories/upload` (ZIP) and `POST /api/v1/repositories/import` (`github_url`) create a `repositories` row; language detection correct on mixed repos; unsupported language → `other` with warning, not failure.
- [ ] **T-04** Python AST analyzer
  - **AC:** Extracts functions/methods/classes, signatures, `line_start/end`, calls (resolved to local entities where possible), imports, globals usage; complexity (Radon CCN) matches manual count on 3 fixture files.
- [ ] **T-05** Java parser (tree-sitter-java)
  - **AC:** Same extraction coverage as T-04 for Java fixtures (methods, classes, calls, imports, complexity).
- [x] **T-06** Dependency graph builder (NetworkX)
  - **AC:** Repository→package→module→class→function→call graph correct on fixtures; circular-dependency detection; high-risk nodes (high complexity × many callers) computed; `GET .../graph` returns React Flow `nodes`/`edges`.
- [x] **T-07** Parallel pipeline (Celery)
  - **AC:** Files parsed in parallel workers; results aggregate deterministically; `pipeline_state` persists each stage; analysis of a 10K-LOC fixture completes < 5 min; live status endpoint reports correct stage.
- [x] **T-08** Semantic index
  - **AC:** Module/class/function chunks embedded and stored in pgvector; `GET .../search?q=` returns relevant entities ranked plausibly on fixtures.
  - **Implementation:**
    - Smart chunking from persisted static-analysis facts (signature, docstring, arguments, calls, globals, inheritance) — never raw source dumps
    - Embedding gateway: local deterministic hash embedder (256-dim, L2-normalized, for tests) + production OpenAI-compatible API embedder with batching/retries
    - PostgreSQL: `chunks.embedding` is `vector(N)` column with HNSW cosine index; SQLite falls back to JSON
    - Database-side similarity search using pgvector's `<=>` operator; Python cosine fallback for SQLite
    - Content-addressed embedding cache prevents duplicate API calls
    - All 72 tests pass (SQLite); pgvector integration tests in `test_pgvector.py` (skipped without PostgreSQL)

## Phase 2 — AI explanation

- [x] **T-09** LLM gateway
  - **AC:** `llm/` gateway wraps provider; `LLM_PROVIDER`/`LLM_MODEL` env-driven; token budget + retry handling; unit-tested with a mock provider.
- [x] **T-10** Evidence-cited function explanation
  - **AC:** Response has the 10 fields (purpose, inputs, outputs, side effects, dependencies, control flow, error handling, business rules, complexity, risks) and `evidence[]` with `file`, `line_start/end`, `code`; spot-check: claims trace to actual fixture code.
- [x] **T-11** Module & repository summary + architecture classification
  - **AC:** Summaries reference real entities; architecture classified (Presentation → Business Logic → Data Access → DB) with issues (coupling, circular deps, global config) derived from the graph, not the LLM.
- [x] **T-12** Impact analysis
  - **AC:** Selecting an entity returns its callers with `file:line`, aggregated impact level (high/med/low); verified against fixtures.

## Phase 3 — Tests

- [x] **T-13** Test generator (signatures/branches/exception paths)
  - **AC:** From AST + existing tests, emits runnable pytest/JUnit for fixture functions covering main branches and at least one exception path each.
- [x] **T-14** Sandbox execution + coverage measurement
  - **AC:** `POST .../tests/generate` queues a job; `GET .../tests/latest` returns generated/passed/failed, line % + branch %, target `>60%`, uncovered lines; sandbox isolation enforced against `backend/tests/fixtures/escape/` (busy loop + unbounded allocation must be killed by timeout/memory limit and fail closed, per `backend/sandbox/security-policy.md`).
- [x] **T-15** Coverage repair loop
  - **AC:** `generate-uncovered` targets uncovered lines, reruns, raises coverage; loop stops at `>60%` line coverage or configurable budget; the benchmark (`benchmark/legacy_demo`, python + java) starts ~30–40% and reaches `>60%` within 3 iterations.
- [ ] **T-16** Coverage UI
  - **AC:** Tests tab shows counts, line/branch %, PASSED/FAILED vs target, clickable uncovered lines, and "Generate Tests for Uncovered Code" button.

## Phase 4 — Modernization

- [ ] **T-17** Refactor proposal + diff
  - **AC:** `POST .../refactors/{entity}/propose` returns original vs. proposed code + WHY list; Monaco diff view renders; original repo unchanged (verified by checksum).
- [ ] **T-18** Breaking-change detection
  - **AC:** Comparing signatures/returns/exceptions/side effects flags changes; output lists impacted callers as `file:line`; correct HIGH/MEDIUM/LOW on crafted fixtures (e.g., changed arg count → HIGH).
- [ ] **T-19** Refactor Safety Score
  - **AC:** Score 0–100 from api compat, test compat, dependency impact, behavioral risk; risk level low/medium/high; demo fixture scores and risk match hand-computed expectations.

## Phase 5 — Polish

- [ ] **T-20** Processing pipeline UI
  - **AC:** Live pipeline stages render with ✓/⟳/○ states during analysis; no blank screens.
- [ ] **T-21** Dashboard + report export
  - **AC:** Landing shows repo stats (language, LOC, entity count), architecture tree, high-risk/circular warnings, coverage, safety; export produces a readable markdown/PDF report.

## Backlog (not MVP)

- Monaco edit-then-propose, JS/C++ support, multi-repo projects, team accounts.
