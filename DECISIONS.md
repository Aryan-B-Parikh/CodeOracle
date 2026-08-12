# Decision Log

> Append every decision here the moment it's made — especially mid-build deviations. This is the file that prevents context loss between sessions.

## 2026-08-11

- **Initial scope locked.** CodeOracle = evidence-driven AI agent for understanding + safely modernizing legacy software. Python + Java only. Web dashboard (no IDE plugin, no team accounts).
- **Stack:** React/Vite/Tailwind/Monaco/React Flow/Recharts · FastAPI/Celery/Redis · tree-sitter + Python `ast` + NetworkX + Radon · PostgreSQL + pgvector · LLM API behind gateway · Docker sandbox. (Initial snapshot listed JavaParser for Java; **superseded by tree-sitter-java** in T-05 / ADR-008. ADRs 001–007 in `docs/06-codebase-context.md`.)
- **Golden principle:** AI reasons over static-analysis facts, never replaces them; every claim cites `file:line`. (ADR-001.)
- **Coverage gate:** product feature must reach `>60%` line coverage via the Test → Coverage → Repair loop, surfaced in the UI.
- **4-tab UI** maps 1:1 to judging criteria: Explanation / Dependency Graph / Tests / Refactor.
- **Demo flow:** 5–8K LOC upload → pipeline → architecture → explanation → tests → 73% coverage → modernization → breaking change detected → safety 89/100.

## 2026-08-11 — T-01 scaffold decisions

- **pytest excludes golden fixtures.** Running `pytest backend/tests` collected the fixture repos under `backend/tests/fixtures/` and `python_basic/app.py` shadowed the `app` package (fixture dir got prepended to `sys.path`, so `app.main` failed as "not a package"). Fixed with `norecursedirs = ["fixtures", "venv", ".venv"]` in `backend/pyproject.toml`. Fixture test files are golden inputs for the product, never part of our own suite.
- **mypy config:** strict-style (disallow untyped defs, warn-return-any, etc.) rather than `strict = true` to avoid third-party stub friction on FastAPI/pydantic; `exclude = ["tests"]`.
- **Frontend pins:** React 18 + Vite 5 + TS 5 + ESLint 8 (classic `.eslintrc.cjs`) + Vitest 2. ESLint 8 classic config over ESLint 9 flat config for now — revisit when adding plugins. Prettier `singleQuote`/no `semi` per docs/04. No state/graph/editor libs yet (added in their own tasks).
- **Local dev on Python 3.14 + pip venv** (`backend/.venv`), while CI and docs target Python 3.11. FastAPI TestClient emits a StarletteDeprecationWarning (httpx) — harmless, tracked.
- **CI:** GitHub Actions (`.github/workflows/ci.yml`), two jobs (backend ruff+mypy+pytest, frontend eslint+tsc+vitest), runs on push to `main` and PRs. Requires `git init` + GitHub remote to actually fire.

## 2026-08-11 — T-02 sandbox decisions

- **Base image `python:3.11-slim-bookworm`** (not `:slim`): the current `python:3.11-slim` is Debian trixie, which has no `openjdk-17` package. Bookworm ships JDK 17; fixtures target `maven.compiler.source/target 17`.
- **`-Dproject.build.directory` does NOT redirect compiler output** (model-interpolation gotcha — javac still wrote to read-only `/sandbox/target`). Java runs now build from a writable copy: `cp -r /sandbox /home/codeoracle/project && mvn ...` inside the scratch volume.
- **Maven is offline at runtime** (`-o`); the local repo is pre-populated at image build by running `mvn verify` on `offline-java/pom.xml` (JUnit 4, surefire/compiler plugins, JaCoCo agent + report). Runtime requires `--network none`, so no downloads are possible.
- **pytest-cov** added to the image. Coverage data file must land in writable scratch (`.coverage` in cwd): pytest runs from `/home/codeoracle` with absolute `/sandbox/...` paths.
- **JaCoCo skips the report when there are no tests**; `parse_jacoco.py` then falls back to a zero-coverage JSON instead of erroring.
- **Writable scratch = anonymous volume at `/home/codeoracle`** (auto-removed with `--rm`, initialized from the image so the Maven repo is present) + small `--tmpfs /tmp:size=64m`. Extra hardening: `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit 128`, named container + `docker kill` for timeout.
- **Runner (`backend/sandbox/run.py`) returns canonical coverage JSON** `{lineCoverage, branchCoverage, uncoveredLines}` for both languages; ANSI-tolerant extraction (Maven prints a color reset before the JSON line).
- **Verified:** python fixture 12.1% line / java fixture 21.7% line (committed tests only touch `tax.py`/`TaxCalculatorTest`, so low baseline is expected); busy-loop killed at timeout (exit 124, ~15s); memory hog OOM-killed (exit 137, ~2s); network resolution fails (`--network none`).
- **Host tests `backend/tests/test_sandbox.py`** cover the hardening flags (pure) and the two fixtures + both escapes (integration, auto-skip when the image is absent).

## 2026-08-11 — T-03 repository scanner decisions

- **DB layer added** (`app/db/`): SQLAlchemy 2.x `session.py` + `repositories`/`files` models; Alembic setup (`alembic.ini`, `migrations/`) with migration `0001_initial`.
- **JSONB with SQLite variant** (`JSONB().with_variant(JSON(), "sqlite")`) on `languages`/`warnings`: production PG gets JSONB (ADR-003), tests/CI get portable JSON. Tests run on in-memory SQLite (StaticPool) so CI needs no Postgres; production schema is applied via `alembic upgrade head`.
- **camelCase JSON** enforced with pydantic `alias_generator=to_camel` + `populate_by_name` — matches the `docs/03` API contract and `docs/api-examples`; internal fields stay snake_case.
- **Scanner is pure** (`app/analyzers/scanner.py`): walks files, classifies by extension, counts LOC + sha256, flags unsupported as `other` with a warning — never a failure. Ingestion is synchronous in the endpoints for now; the analysis pipeline (parsing etc.) will run via Celery in later tasks (T-06).
- **Zip hardening:** path-traversal rejection, 100MB upload cap, 200MB/20k-file extract caps, single-top-dir collapse (repo root detection).
- **Import hardening:** URL scheme whitelist (`http/https/ssh`, `git@`), `git clone --depth 1` with 300s timeout; the clone step is a monkeypatchable function for hermetic tests.
- **Local PG gotcha:** this machine has a Postgres service squatting on host port 5432 (two listeners). The dev container runs on **5433**; docs/05 gained a troubleshooting note. Role `codeoracle` created with password `codeoracle`.
- **Verified:** `alembic upgrade head` applied to real PostgreSQL; upload of the `python_basic` fixture returns camelCase JSON, 8 files / 226 LOC, `languages={"python": true}`; rows confirmed via psql. All 15 tests pass, including a network-gated real GitHub clone (`octocat/Hello-World`).

## 2026-08-11 — T-04 Python AST analyzer decisions

- **Parser is pure** (`app/analyzers/python_parser.py`): takes source text, returns typed `ParsedFile` (entities, calls, imports). Uses `ast` + radon; no I/O, no LLM. Call/import `resolved`/`external` decisions happen in the persistence service where repo context exists.
- **Radon CCN is ground truth** for complexity; verified against manual counts (charge=8, apply_discount=3, legacy_summary=3, monthly_summary=2, get_tax_rate=2, etc.). Class complexity uses radon's `Class.complexity`. mypy override added for radon (no stubs).
- **Schema additions beyond docs/03 (logged):** `calls.callee_name` (needed to display external/unresolved call targets) and `imports.line` (evidence/citation). `entities.metadata` is mapped via the `metadata_json` Python attribute because SQLAlchemy reserves `metadata`.
- **Call resolution is file-local** by name; dotted calls resolve via their last component (`self.charge` → `charge`). Cross-file/import-based resolution is deferred to the T-06 graph builder. Calls to module attributes (`customer.load_customer`) stay `external`.
- **Analysis service** (`app/services/analysis.py`) persists imports, entities (with class→method `parent_id`), and calls (with `external` flag), updates `repository.entity_count`. Runs synchronously for now; Celery orchestration lands in T-07.
- **Verified:** 25/25 tests (golden extraction + manual CCN counts on the 3 fixture files); migration `0002_entities` applied to real PostgreSQL; e2e on PG = 23 entities / 8 files with correct call edges (`apply_discount`/`calculate_subtotal` resolved, `customer.load_customer`/`tax.calculate_tax` external).

## 2026-08-11 — T-05 Java parser decisions

- **Parsing via tree-sitter-java, not JavaParser (deviation from stack docs, logged).** JavaParser needs a JVM on the backend host; tree-sitter is pure-Python and is already part of the stack. `app/analyzers/java_parser.py` returns the identical `ParsedFile`/`ParsedEntity` types as the Python parser, so one persistence service handles both.
- **Shared types module** `app/analyzers/types.py`; `python_parser` re-exports them (test compat).
- **Java complexity** = 1 + decision points (if/while/for/enhanced-for/do/catch/ternary/switch + case, plus each `&&`/`||`). Class complexity = **max of its methods** (Python classes use radon's own formula — documented cross-language asymmetry). Verified: charge=8, discount=3, parseAmount=3, legacyCalc=2, isVip=2.
- **Grammar quirk:** `modifiers` is a child node, not a field (`child_by_field_name("modifiers")` → None) in this tree-sitter-java version — `_is_public` scans children. Constructors are extracted as methods (parent = class, e.g. private ctor → `is_public=False`).
- **Java imports external** = last dotted segment not in the repo's local class names; `globals_used` for Java = referenced class fields (instance + static).
- **Verified:** 32/32 tests (golden extraction + manual CCN); e2e on real PostgreSQL = 27 entities / 6 files (incl. committed `TaxCalculatorTest`), `discount` call edge resolved, `java.util.*` imports external.

## 2026-08-11 — T-02 follow-up: explicit resource policy

- **New `backend/sandbox/policy.py`** is the single source of truth for every limit (CPU 1.0, memory 512m/swap 512m, pids 128, /tmp 64m, runtime 300s, **staged source 50MB**, **generated tests 10MB**, **stdout 1MB**, **stderr 1MB**); `run.py`/`stage.py` import it so policy and code can't drift. `security-policy.md` now carries the full table + exit codes (124 timeout / 125 resource / 137 OOM).
- **Bounded output capture** — replaced `subprocess.run(capture_output=True)` (unbounded host memory risk) with capped reader threads; overflow kills the container and reports `stdout/stderr limit exceeded` (exit 125).
- **Fail-closed staging limits** — `stage.py` raises `StageLimitError` (exit 125) before `docker run` when the extracted repo or generated tests exceed their caps.
- **`pytest -s` in the sandbox** — pytest's fd-level capture was swallowing `os.write(1|2, ...)` floods; raw output must reach the Docker pipe for the stdout/stderr limits to be meaningful.
- **Escape fixtures** `escape/python/stdout_flood` + `stderr_flood`; both killed at the 1MB cap. Verified: 36/36 tests.

## 2026-08-11 — T-03 hardening (uploads + classification)

- **Streamed uploads** — `POST /repositories/upload` no longer does `await file.read()` (up to 100MB resident). It streams 1MB chunks to the on-disk `source.zip` (`_stream_upload` in `repositories.py`), aborting with 413 when `MAX_UPLOAD_BYTES` is exceeded mid-stream, then ZIP validation runs against the file. On any failure the workdir is removed, so no partial rows/files leak. Flow is now: upload stream → temp file → size enforcement → ZIP validation.
- **Known-unsupported language classification** — the scanner keeps Python/Java as supported ground truth, but now classifies 30+ known-but-unsupported extensions (JS/TS, C/C++/C#, Go, Rust, SQL, shell, HTML/CSS, etc.) by name. New `repositories.language_counts` JSONB column (migration `0003_language_counts`) stores per-language file counts (`{"python": 8, "JavaScript": 2, "other": 1}`) so the UI can render a Supported/Unsupported breakdown instead of one generic warning. `other` = truly unrecognized extensions; the old `languages` booleans are unchanged.

## 2026-08-11 — T-04 limitations: nesting + dynamic calls

- **Nested entities extracted** (Python: nested functions/classes to arbitrary depth; Java: inner/static-nested classes). Entity identity is now a **qualified name** (`outer.inner`, `Outer.Inner.run`) stored in `entities.metadata_json.qualified_name`; `parent_id` resolves by qualified name, so the old `parent`-as-class-name contract is unchanged for top-level entities (tests untouched).
- **Dynamic calls are marked, not resolved.** `CallRef.dynamic` flags `getattr(x, n)()` / `getattr(x, n)` / `obj[k]()`; the parser never marks them resolved, and persistence writes `calls.dynamic = true` with `callee_id NULL` + `external true` so the UI can render "⚠ Dynamic call" instead of a definite dependency. Migration `0004_call_dynamic` adds the column.

## 2026-08-11 — T-05: inheritance, modern Java types, imports, javadoc

- **Inheritance edges extracted + persisted** (HIGH). New `inheritances` table (migration `0005_inheritances`): subclass → `parent_name` (as written, incl. generics like `Comparable<PremiumCustomer>`) with `kind` `extends`/`implements` and a `line` for evidence. `parent_id` resolves when the parent type exists locally in the file; cross-file resolution and graph building (CALLS/IMPORTS/INHERITS/IMPLEMENTS) is T-06's job. Python class bases map to `extends`.
- **Modern Java types modeled** — `interface` / `enum` / `record` / `annotation` are now first-class entity kinds (enum bodies flattened through `enum_body_declarations`; record compact constructors and annotation elements treated as methods). Backward compatible: existing fixture counts unchanged.
- **Imports preserved** — wildcards and static members no longer stripped (`java.io.*`, `java.util.Collections.emptyList`), and `imports.kind` (`normal`/`static`) added.
- **Basic javadoc extraction** — `description` + `@tags` (param/return/throws/…) parsed structurally into `entities.metadata.javadoc`; raw comment text stays in `docstring`.
- **Deferred (documented):** Java call resolution remains file-local (T-06 graph scope); complexity algorithms intentionally differ per language (Radon CCN vs. Java decision-count) and are already documented — UI must label generically as "Cyclomatic complexity".

## 2026-08-11 — T-06 dependency graph

- **`app/services/graph.py`** builds the NetworkX graph from persisted facts and serves `GET /api/v1/repositories/{id}/graph` (`app/api/routes/graph.py`) as React Flow `nodes`/`edges` + `meta`.
- **Nodes:** one `module` node per file plus one node per entity (`{file}::{qualified_name}`) with `type` (function/method/class/interface/enum/record/annotation), complexity, file, line range, `qualifiedName`, `riskScore`.
- **Edges** carry a `kind`: `contains` (module→entity, parent→child), `call` (incl. **cross-module re-resolution** — `tax.calculate_tax` and import aliases like `from billing import describe_invoice` now resolve at repository scope, matching the fixture's intended edges), `imports` (local), `inherits`/`implements` (from the `inheritances` table). Dynamic calls never become edges.
- **Circular deps** are detected on the **module** dependency graph (cross-module calls + local imports) — the deliberate `billing ↔ database` import cycle in `python_basic` is correctly reported. Entity-level cycles are aggregated to their modules.
- **High-risk** = top 10 entities by `complexity × (callers + callees + 1)`, surfaced as `riskScore` per node and `meta.highRiskNodeIds`.
- Verified: `GET .../graph` on `python_basic` resolves cross-module calls, reports the `[billing.py, database.py]` cycle, and ranks `calculate_invoice` correctly; `java_modern` yields `inherits` edges and all modern type nodes. 56/56 tests.

## 2026-08-12 — T-07 parallel pipeline (Celery)

- **Pipeline driver + fan-out:** `POST /api/v1/repositories/{id}/analyze` (`app/api/routes/pipeline.py`) creates an `analyses` row and enqueues `analysis.run` (`app/workers/tasks.py`), which fans out one `analysis.parse_file` task per file as a Celery `group` — files parse **concurrently on the prefork pool** (tasks are DB-free; they read + parse + return serialized facts). Results are joined with `disable_sync_subtasks=False` (Celery 5.6 blocks `.get()` inside tasks), falling back to inline `.apply()` when `CELERY_TASK_ALWAYS_EAGER=1` (test env, no broker).
- **Deterministic aggregation:** `store_parse_results` (`app/services/analysis.py`) merges worker results in fixed `(language, path)` order regardless of finish order; `analyze_repository` (sequential, used by tests) and the pipeline share the same primitives. Verified: pipeline output == 2× pipeline == sequential, fact-for-fact (normalized sets of entities/calls/imports/inheritances). Unparseable files skip (recorded), never fail the run; re-analysis deletes prior facts first (`delete_analysis_facts`).
- **`pipeline_state`** lives on the new `analyses` table (migration `0006_analyses`) and persists every stage transition (`uploaded`/`scanned`/`parsing`/`aggregating`/`graph` with `pending`/`running`/`done`/`error`; parsing also tracks `filesTotal`/`filesParsed`). `GET /api/v1/repositories/{id}/status` reports `repositoryStatus`, `analysisStatus`, `currentStage` (first non-done stage, `completed` when all done). PRD/ADR keep: stage keys JSON use camelCase like all API payloads (nested dicts are not pydantic-aliased).
- **10K-LOC gate:** synthetic 10K-LOC fixture (100 modules × 5 funcs) analyzes well under the 5-minute bound (`ANALYSIS_TIMEOUT_SECONDS = 300` on the group join; exceeding it fails the analysis and marks `repository.status=failed`).
- **Ops notes:** run the worker with `celery -A app.workers.celery_app worker --loglevel=info` (docs/05); `analysis.run` blocks one prefork slot while joining the group (`--without-gossip --without-mingle` recommended); `graph` stage is marked done once facts are complete — the NetworkX graph itself is still derived on demand by `GET .../graph` (T-06).

## 2026-08-12 — T-08 semantic index

- **`app/index/`** = chunking + embeddings + search. `chunking.py` builds module/class/function chunks **from persisted facts** (signature, docstring, arguments, calls, globals, inheritance) — never raw source dumps, so the index feeds the LLM retrieval layer the same ground truth.
- **Embedding gateway** (`embeddings.py`): provider-agnostic. With `EMBEDDING_MODEL` unset it uses a **deterministic local feature-hashing embedder** (256-dim, L2-normalized) — no network/key, stable across runs, which keeps the test suite hermetic; when set, it calls the OpenAI-compatible `/embeddings` API via `LLM_API_KEY` with batching (`EMBEDDING_BATCH_SIZE`) and retries (`EMBEDDING_RETRIES`). Both produce comparable cosine scores.
- **Search endpoint** `GET /api/v1/repositories/{id}/search?q=` returns ranked results with `entityId`, `qualifiedName`, `file`, `type`, `level`, line range, `score`. Test/`conftest` sources are excluded from the index so entity ranking stays clean on fixtures.
- **Pipeline wiring**: new `index` stage appended to `PIPELINE_STAGES`; `tasks._aggregate` builds the index after graph facts, and the sequential `analyze_repository` path builds it too.
- **pgvector implementation (production):** Migration `0008_pgvector.py` creates the vector extension, alters `chunks.embedding` to `vector(N)` type (N from `EMBEDDING_DIMENSIONS`), and creates HNSW index `ix_chunks_embedding_hnsw` with `vector_cosine_ops`. Database-side similarity search uses pgvector's `<=>` cosine distance operator via SQLAlchemy's `cosine_distance()` method. SQLite test dialect uses JSON float list with Python cosine fallback (identical semantics).
- **Embedding cache:** Content-addressed by (model, dimensions, content_hash) in `embedding_cache` table; API-backed embedder only invoked for new content.
- **Configuration:** `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` (default 256), `EMBEDDING_BATCH_SIZE` (default 64), `EMBEDDING_RETRIES` (default 3), `EMBEDDING_BASE_URL`, `EMBEDDING_CACHE` (default True).
- Verified: `calculate tax` → `calculate_tax` is the top-ranked entity; `invoice discount customer` → billing logic; `data layer…` → `database.py` fetch/connection; Java `payment charge` → `PaymentService.charge`. 72/72 tests pass on SQLite. PostgreSQL/pgvector integration tests added in `test_pgvector.py` (auto-skipped without PG).

## Template for new entries

```
## YYYY-MM-DD
- **Decision:** <what we chose>
- **Why:** <reason>
- **Replaces:** <option/decision superseded, if any>
- **Notes:** <consequences, follow-ups>
```
