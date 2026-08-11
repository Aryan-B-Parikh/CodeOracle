# Contributing

## Workflow

1. Branch off `main`: `feature/<short-description>`.
2. Implement, keeping changes small and one task at a time (see `docs/07-task-breakdown.md`).
3. Add tests — backend units for any parser/graph/service logic; frontend tests for non-trivial components.
4. Run the quality gates below.
5. Open a PR with a description referencing the task number.
6. Reviewers verify the acceptance criteria for the task, not just code style.

## Quality gates (must pass)

```bash
# backend
ruff check backend/app
mypy backend/app
pytest backend/tests

# frontend
cd frontend && npm run lint && npm run typecheck && npm run test
```

## Do / don't

- **Do** update docs when behavior changes (PRD, data model, DECISIONS.md).
- **Do** log decisions in `DECISIONS.md` the moment you deviate from the plan.
- **Don't** swap the stack (ORM, state manager, vector store, LLM provider mechanism) without an ADR.
- **Don't** commit secrets or real uploaded repositories.
- **Don't** modify original uploaded code — refactors are proposals only.

## Definition of done

- Acceptance criteria for the task pass.
- Lint + typecheck + tests green.
- Docs updated if behavior/contracts changed.
- No secrets in the diff.
