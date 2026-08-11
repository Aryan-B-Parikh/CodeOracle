# Decision Log

> Append every decision here the moment it's made — especially mid-build deviations. This is the file that prevents context loss between sessions.

## 2026-08-11

- **Initial scope locked.** CodeOracle = evidence-driven AI agent for understanding + safely modernizing legacy software. Python + Java only. Web dashboard (no IDE plugin, no team accounts).
- **Stack:** React/Vite/Tailwind/Monaco/React Flow/Recharts · FastAPI/Celery/Redis · tree-sitter + Python `ast` + JavaParser + NetworkX + Radon · PostgreSQL + pgvector · LLM API behind gateway · Docker sandbox. (ADRs 001–007 in `docs/06-codebase-context.md`.)
- **Golden principle:** AI reasons over static-analysis facts, never replaces them; every claim cites `file:line`. (ADR-001.)
- **Coverage gate:** product feature must reach `>60%` line coverage via the Test → Coverage → Repair loop, surfaced in the UI.
- **4-tab UI** maps 1:1 to judging criteria: Explanation / Dependency Graph / Tests / Refactor.
- **Demo flow:** 5–8K LOC upload → pipeline → architecture → explanation → tests → 73% coverage → modernization → breaking change detected → safety 89/100.

## Template for new entries

```
## YYYY-MM-DD
- **Decision:** <what we chose>
- **Why:** <reason>
- **Replaces:** <option/decision superseded, if any>
- **Notes:** <consequences, follow-ups>
```
