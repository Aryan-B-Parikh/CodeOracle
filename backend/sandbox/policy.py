"""Explicit sandbox resource policy.

Single source of truth for every limit the sandbox enforces. Values are
mirrored in `security-policy.md`; the runner (`run.py`) and stager
(`stage.py`) import them so the policy cannot drift from the code.
"""

MAX_CPU = 1.0
MAX_MEMORY = "512m"
MAX_PIDS = 128
MAX_TMPFS = "/tmp:size=64m"

MAX_STAGED_SOURCE_BYTES = 50 * 1024 * 1024
MAX_GENERATED_TESTS_BYTES = 10 * 1024 * 1024
MAX_STDOUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 1024 * 1024

DEFAULT_TIMEOUT = 300

EXIT_TIMEOUT = 124
EXIT_RESOURCE_LIMIT = 125
EXIT_OOM = 137
