# Sandbox Security Policy

Uploaded code is **untrusted**. Every test run must satisfy all of the
constraints below. This policy is enforced at the Docker CLI level by
`backend/sandbox/run.py` — implementation detail, not documentation-only.

## Mandatory constraints

| # | Constraint | Enforcement |
|---|---|---|
| 1 | No network | `docker run --network none` |
| 2 | Limited CPU | `--cpus=1.0` |
| 3 | Limited memory | `--memory=512m --memory-swap=512m` (no swap escape) |
| 4 | Hard timeout | runner `timeout` + `docker stop`/`--stop-timeout` after deadline |
| 5 | Read-only base | `--read-only` filesystem |
| 6 | Temporary working dir | fresh per-run staging dir, removed after the run |
| 7 | Non-root user | image `USER codeoracle` + `--user codeoracle` |
| 8 | No Docker socket | never mount `/var/run/docker.sock` |
| 9 | No host mounts | only a read-only mount of the per-run staging copy: `-v <staging>:/sandbox:ro` |

## Additional hardening (as applicable)

- **Writable scratch** only via an in-container tmpfs: `--tmpfs /tmp:size=64m`
  (coverage reports, Maven local repo `-Dmaven.repo.local=/tmp/.m2`).
- **Source is immutable** inside the sandbox: staging copy is mounted
  `:ro`; generated tests are added to the staging copy before the run, never
  written by the container back to the repo.
- **Disable pytest cache**: `-p no:cacheprovider` so no writes hit the
  read-only tree.
- **No secrets, ever**: the container gets only the staging copy; API keys and
  env vars are not passed through (`--env` not used).

## Non-negotiables

- Never execute uploaded code with the host network, host user, or host mounts.
- If a sandbox constraint cannot be satisfied in an environment, the test run
  must FAIL CLOSED (report an error), never run unconstrained.
- Escape tests: a busy-loop / memory-gobbling fixture must be killed by the
  timeout or memory limit, and surfaced as a failed run.

## Escape-test fixtures

Kept under `backend/tests/fixtures/escape/` (busy loop, unbounded allocation)
and asserted by the integration tests for T-14.
