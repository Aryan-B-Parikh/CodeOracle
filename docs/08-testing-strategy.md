# 8. Testing Strategy

## Pyramid

| Level | Scope | Tools |
|---|---|---|
| Unit | Parsers, graph algorithms, safety scoring, prompts/gateway, UI components | pytest / Vitest + React Testing Library |
| Integration | API ↔ DB (pgvector), API ↔ Celery job flow, sandbox runner | pytest + Docker (sandbox), FastAPI TestClient |
| E2E | Upload → analyze → explain → generate tests → refactor, live pipeline UI | Playwright (frontend) + seeded fixture repos |

## Coverage expectations

- **Own code:** ≥ 80% line coverage on `backend/app` and `frontend/src` (measured by the same coverage.py / Vitest coverage tooling we ship). CI enforces it.
- **Analyzed repos (the product feature):** target **> 60% line coverage** achieved via the Test → Coverage → Repair loop. This is a product gate, shown in the UI, separate from our own coverage.

## What to test where

### Unit
- **Analyzers:** AST extraction accuracy (name, lines, signature, calls, imports, complexity) on fixture files — golden-output tests.
- **Graph:** circular-dependency detection, high-risk computation, deterministic aggregation.
- **Safety score:** scoring functions on crafted breaking-change scenarios.
- **LLM gateway:** prompt assembly, token budget, provider abstraction, retry — with a mock provider.
- **Frontend:** coverage/safety presenters, impact panel, evidence-link rendering.

### Integration
- **API ↔ DB:** every `v1` route against a real (containerized) PostgreSQL+pgvector; Alembic migrations run clean.
- **Job flow:** upload → analysis job → results visible; status/pipeline_state transitions correct.
- **Sandbox:** pytest/JUnit runs inside the Docker sandbox return coverage JSON; CPU/memory/timeout limits actually enforced (a busy-loop fixture must be killed).

### E2E
- **Happy path (the demo flow):** upload 5–8K LOC fixture → pipeline completes → graph renders → explanation shows citations → tests reach `>60%` → refactor proposal with breaking-change report + safety score.
- **Negative paths:** unsupported-language repo warns; empty/invalid ZIP errors cleanly; sandbox timeout surfaces as failed test run.

## The coverage loop (product-critical, test it explicitly)

```
Generate Tests → Run → Coverage = 47% → find uncovered branches
→ generate targeted tests → Run → 68% → STOP (>60%)
```

Integration test asserts the benchmark (`benchmark/legacy_demo`, python + java)
starts at a ~30–40% baseline and reaches `>60%` within a bounded number of
iterations, and the loop stops once the target is met.

## Practical tips for AI coding tools

1. **One task at a time** — hand over a single task from `docs/07-task-breakdown.md` with its acceptance criteria; do not paste the full PRD.
2. **Keep `CLAUDE.md` current** — it's the first thing read; it holds stack, conventions, constraints, and the "do not swap X without an ADR" rules.
3. **Point tests at fixtures, not mocks of real repos** — commit small golden fixture repos (Python + Java) under `backend/tests/fixtures/` so every AI run has deterministic inputs. See `backend/tests/fixtures/README.md` for the intentional-feature manifest; the repeatable judging repo lives in `benchmark/legacy_demo/`.
4. **Ground the LLM with the prompt specs** — keep prompts in `backend/app/llm/prompts/`; static facts are ground truth, the LLM is the reasoning layer.
5. **Verify after generating tests**: always run `pytest`/`npm run test` + lint + typecheck; acceptance criteria are the definition of done.
6. **Mock the API against `docs/api-examples/`** — the committed response shapes make frontend/backend integration deterministic.
7. **Log deviations immediately** in `DECISIONS.md` — that's what gets lost in long sessions.
