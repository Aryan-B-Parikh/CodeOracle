# Sandbox Security Policy

Uploaded code is **untrusted**. Every test run must satisfy all of the
constraints below. They are enforced at the Docker CLI level by
`backend/sandbox/run.py` — implementation detail, not documentation-only.

## Mandatory constraints

| # | Constraint | Enforcement |
|---|---|---|
| 1 | No network | `--network none` |
| 2 | Limited CPU | `--cpus=1.0` |
| 3 | Limited memory | `--memory=512m --memory-swap=512m` (no swap escape) |
| 4 | Hard timeout | host-side `subprocess` timeout + `docker kill <name>` on expiry |
| 5 | Read-only base | `--read-only` root filesystem |
| 6 | Temporary working dir | fresh per-run staging dir; removed after the run |
| 7 | Non-root user | image `USER codeoracle` + `--user codeoracle` |
| 8 | No Docker socket | never mount `/var/run/docker.sock` |
| 9 | No host mounts | only a read-only mount of the per-run staging copy: `-v <stage>:/sandbox:ro` |

## Additional hardening (active in run.py)

- **Writable scratch is ephemeral and container-local:**
  - anonymous volume at `/home/codeoracle` (initialized from the image, so the
    pre-populated Maven repo is present; holds `~/.m2`, `~/build` artifacts,
    and `coverage.json`), auto-removed with `--rm`;
  - small tmpfs at `/tmp` (`--tmpfs /tmp:size=64m`) for transient OS/JVM writes.
- **Privilege hardening:** `--cap-drop ALL`, `--security-opt no-new-privileges`,
  `--pids-limit 128` (fork-bomb protection).
- **Source is immutable** inside the sandbox: the staging copy is mounted
  `:ro`; generated tests are added to the staging copy *before* the run, never
  written by the container back to the repo.
- **Offline Maven:** the image pre-populates the Maven local repository (JUnit 4,
  Surefire/compiler plugins, JaCoCo agent + report); runtime uses `mvn -o`
  (offline). Network is never available at runtime.
- **No secrets, ever:** the container gets only the staging copy; no `--env`
  passthrough, no API keys, no host env.

## Non-negotiables

- Never execute uploaded code with the host network, host user, or host mounts.
- If a sandbox constraint cannot be satisfied in an environment, the test run
  must **FAIL CLOSED** (report an error), never run unconstrained.
- Escape tests: a busy-loop fixture must be killed by the timeout; a
  memory-gobbling fixture must be killed by the memory limit. Both are
  surfaced as failed runs (exit 124 / 137).

## Escape-test fixtures

`backend/tests/fixtures/escape/`:
- `python/busy_loop/` — a test that never returns (timeout enforcement).
- `python/memory_hog/` — a test that allocates without bound (OOM enforcement).

Run via the runner, e.g.:

```bash
python run.py --language python --source ../tests/fixtures/escape/python/busy_loop \
  --tests ../tests/fixtures/escape/python/busy_loop/tests --timeout 15
python run.py --language python --source ../tests/fixtures/escape/python/memory_hog \
  --tests ../tests/fixtures/escape/python/memory_hog/tests --timeout 120
```
