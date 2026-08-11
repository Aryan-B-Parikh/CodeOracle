# Sandbox Security Policy

Uploaded code is **untrusted**. Every test run must satisfy all of the
constraints below. They are enforced at the Docker CLI level by
`backend/sandbox/run.py` and `backend/sandbox/stage.py`. The single source of
truth for limit values is `backend/sandbox/policy.py` — implementation detail,
not documentation-only.

## Resource policy (explicit limits)

| Limit | Value | Enforcement (fail closed) |
|---|---|---|
| CPU | 1.0 | `--cpus 1.0` |
| Memory | 512 MB, no swap | `--memory 512m --memory-swap 512m` |
| Process count | 128 | `--pids-limit 128` (fork-bomb protection) |
| `/tmp` scratch | 64 MB | `--tmpfs /tmp:size=64m` |
| Runtime | 300 s default (configurable) | host timeout + `docker kill <name>` |
| **Staged source (extracted repo)** | 50 MB | `stage.py` rejects before `docker run` |
| **Generated tests** | 10 MB | `stage.py` rejects before `docker run` |
| **stdout** | 1 MB | bounded reader; container killed on overflow |
| **stderr** | 1 MB | bounded reader; container killed on overflow |

Exit codes: `124` timeout · `125` resource limit (staging, stdout, stderr) ·
`137` OOM kill.

## Mandatory constraints

| # | Constraint | Enforcement |
|---|---|---|
| 1 | No network | `--network none` |
| 2 | Limited CPU | `--cpus=1.0` |
| 3 | Limited memory | `--memory=512m --memory-swap=512m` (no swap escape) |
| 4 | Hard timeout | host-side timeout + `docker kill <name>` on expiry |
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
- **Bounded output:** stdout/stderr are read through capped readers; if a test
  exceeds the limit the container is killed and the run reports
  `stdout/stderr limit exceeded` (exit 125). The host never buffers unbounded
  output.
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
  memory-gobbling fixture must be killed by the memory limit; a stdout/stderr
  flood must be killed by the output limit. All are surfaced as failed runs
  with their exit code (124 / 137 / 125).

## Escape-test fixtures

`backend/tests/fixtures/escape/`:
- `python/busy_loop/` — a test that never returns (timeout enforcement).
- `python/memory_hog/` — a test that allocates without bound (OOM enforcement).
- `python/stdout_flood/` — a test that writes 2 MB to stdout (output limit).
- `python/stderr_flood/` — a test that writes 2 MB to stderr (output limit).

Run via the runner, e.g.:

```bash
python run.py --language python --source ../tests/fixtures/escape/python/busy_loop \
  --tests ../tests/fixtures/escape/python/busy_loop/tests --timeout 15
python run.py --language python --source ../tests/fixtures/escape/python/memory_hog \
  --tests ../tests/fixtures/escape/python/memory_hog/tests --timeout 120
python run.py --language python --source ../tests/fixtures/escape/python/stdout_flood \
  --tests ../tests/fixtures/escape/python/stdout_flood/tests --timeout 60
```
