# Decision Log

> Append every decision here the moment it's made — especially mid-build deviations. This is the file that prevents context loss between sessions.

## 2026-08-11

- **Initial scope locked.** CodeOracle = evidence-driven AI agent for understanding + safely modernizing legacy software. Python + Java only. Web dashboard (no IDE plugin, no team accounts).
- **Stack:** React/Vite/Tailwind/Monaco/React Flow/Recharts · FastAPI/Celery/Redis · tree-sitter + Python `ast` + JavaParser + NetworkX + Radon · PostgreSQL + pgvector · LLM API behind gateway · Docker sandbox. (ADRs 001–007 in `docs/06-codebase-context.md`.)
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

## Template for new entries

```
## YYYY-MM-DD
- **Decision:** <what we chose>
- **Why:** <reason>
- **Replaces:** <option/decision superseded, if any>
- **Notes:** <consequences, follow-ups>
```
