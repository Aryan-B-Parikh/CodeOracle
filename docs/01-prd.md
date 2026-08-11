# 1. PRD — CodeOracle

## Product

**CodeOracle** — An Evidence-Driven AI Agent for Understanding and Safely Modernizing Legacy Software.

**One-line pitch:** CodeOracle turns undocumented legacy repositories into understandable architecture, tested code, and safety-verified modernization plans.

## Problem

- Legacy codebases are undocumented, so LLM code "explanations" are generic and often hallucinated.
- Engineers can't tell which refactors are safe, so modernization is risky and avoided.
- Test coverage on legacy systems is low and there is no structured way to raise it.

## Goals

1. **Understand** a legacy repository (Python + Java) by reconstructing its architecture and dependency graph from static analysis — not from LLM guesses.
2. **Explain** every function with evidence (file + line ranges) supporting each claim.
3. **Test** the repository automatically, iteratively raising line coverage to a `>60%` target.
4. **Modernize** safely: propose refactors, detect breaking changes, and score safety without overwriting original code.

## User stories / use cases

- **As a developer joining a legacy project**, I can upload a ZIP or GitHub repo and get a structural map of modules, dependencies, and high-risk functions within minutes.
- **As a developer**, I can ask about any function and receive a structured explanation (purpose, inputs, outputs, side effects, dependencies, control flow, error handling, business rules, complexity, risks) with cited `file:line` evidence.
- **As a developer**, I can click a function in the dependency graph and see everything that calls it and everything it calls (impact analysis).
- **As a quality engineer**, I can trigger test generation and watch coverage rise in a Test → Coverage → Repair loop until it passes the `>60%` line-coverage gate.
- **As a tech lead**, I can request a modernization proposal, see the behavioral diff, review a Refactor Safety Score, and see exactly which callers would break.
- **As a judge/stakeholder**, I can watch a live processing pipeline and export a report.

## Explicit non-goals (scope control)

- **No automatic code rewriting.** Refactors are shown as proposals in a diff viewer only; the original source is never modified.
- **No local/hosted LLM.** Use an LLM API; keep the provider abstract behind a gateway.
- **No C++/JavaScript support** in the MVP. Only Python (pytest) and Java (JUnit).
- **No execution of uploaded code on the backend host.** All test runs happen inside a Docker sandbox with CPU/memory/time limits.
- **No sending full repositories to the LLM.** The AI reasons over facts extracted by static analysis (knowledge graph + retrieved chunks), never over raw 10,000-line dumps.
- **No IDE plugin** in the MVP (web dashboard only).
- **No collaboration/team accounts** in the MVP.

## Functional requirements by phase

### Phase 1 — Core ingestion
- Upload a ZIP archive or import a GitHub repository.
- Detect languages (Python / Java / unsupported → warn).
- Parse with Python `ast` / tree-sitter (`tree-sitter-java` for Java); extract files, functions, classes, imports, calls.
- Build a dependency graph (repository → packages → modules → classes → functions → calls).
- Support 10,000+ LOC via parallel file processing.

### Phase 2 — AI explanation
- Per-function structured explanation (10 fields, evidence-cited).
- Module-level and repository-level architecture summaries.
- Automatic architecture classification (Presentation → Business Logic → Data Access → DB) with architectural issues (coupling, circular deps, global state).
- Semantic search over the repository (embeddings in pgvector).

### Phase 3 — Test generation
- Generate pytest/JUnit tests from AST (signatures, branches, conditions, exception paths).
- Execute in Docker sandbox; measure line + branch coverage.
- Iterative loop: find uncovered branches → generate targeted tests → rerun → stop when `>60%` line coverage or budget exhausted.
- Show coverage UI: tests generated/passed/failed, line %, branch %, target vs. status, uncovered lines list.

### Phase 4 — Modernization
- Refactor proposals with diff viewer (original vs. proposed).
- Per-proposal rationale (naming, magic numbers, readability).
- Breaking-change detection: compare signatures, return types, exceptions, side effects, caller behavior across original vs. refactored API; list impacted callers.
- Refactor Safety Score (API compatibility, test compatibility, dependency impact, behavioral risk) and risk level.

### Phase 5 — Polish
- Monaco editor, interactive graph (zoom/search/click/highlight/circular-dep/high-risk nodes), processing pipeline UI, analytics dashboard, export report.

## Non-functional requirements

- **Scale:** a ~10,000 LOC repository must be analyzable end-to-end; the LLM must never receive the full source in one prompt.
- **Evidence:** every AI claim must cite exact `file:line` ranges; the system must never infer behavior unsupported by supplied code.
- **Safety:** test execution only inside sandboxed containers (CPU/memory/time limits, no network to internal services, no writes to original repo).
- **Performance:** files parsed in parallel; graph aggregation after per-file workers complete.
- **Security:** uploaded code is untrusted; treat it as such everywhere (no execution on backend, restricted sandbox, secrets never logged).

## Success metrics

- Repository graph and explanations generated for a 10K LOC Python and Java repo.
- Test coverage loop reaches `>60%` line coverage on the demo repo.
- Refactor proposals carry a computed safety score and an accurate breaking-change report.
- Zero hallucinations in cited evidence (spot-check).

## Demo flow (primary)

1. Upload 5,000–8,000 LOC legacy repository.
2. "Analyzing repository..." → pipeline status shown live.
3. Architecture reconstructed + dependency graph.
4. AI-generated function/module explanation with citations.
5. Generate unit tests → 73% coverage achieved.
6. Propose modernization → detect breaking change → safety score 89/100.
