"""Runner for the CodeOracle test sandbox.

Builds a hardened `docker run` (every flag maps to a constraint in
security-policy.md / policy.py), executes the tests of a staged repository, and
returns a canonical result containing line/branch coverage as JSON. Output is
captured through bounded readers so a hostile test cannot exhaust host memory.

Usage:
    python run.py --language python --source <repo-or-project-dir> [--tests <dir>]
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import policy
import stage
from stage import StageLimitError

IMAGE = "codeoracle/sandbox:latest"
LOG_LIMIT = 8000
_CHUNK = 65536

PYTHON_CMD = (
    "cd /home/codeoracle && "
    "pytest -s /sandbox/tests -p no:cacheprovider --cov /sandbox/src --cov-branch "
    "--cov-report=json:/home/codeoracle/coverage.json --cov-report=term "
    "&& cat /home/codeoracle/coverage.json"
)
JAVA_CMD = (
    "cp -r /sandbox /home/codeoracle/project && "
    "cd /home/codeoracle/project && "
    "mvn -o -q test jacoco:report && "
    "(python3 /opt/parse_jacoco.py /home/codeoracle/project/target/site/jacoco/jacoco.xml "
    "2>/dev/null || echo '{\"lineCoverage\": 0.0, \"branchCoverage\": 0.0, \"uncoveredLines\": []}')"
)


class _BoundedReader(threading.Thread):
    """Reads a pipe, retaining at most `limit` bytes, killing on overflow."""

    def __init__(self, stream, limit: int, on_exceed=None):
        super().__init__(daemon=True)
        self._stream = stream
        self._limit = limit
        self._on_exceed = on_exceed
        self.data = ""
        self.exceeded = False

    def run(self) -> None:
        while True:
            chunk = self._stream.read(_CHUNK)
            if not chunk:
                return
            if self.exceeded:
                continue
            remaining = self._limit - len(self.data)
            if remaining <= 0:
                self._exceed()
                continue
            self.data += chunk[:remaining]
            if len(chunk) > remaining:
                self._exceed()

    def _exceed(self) -> None:
        self.exceeded = True
        if self._on_exceed is not None:
            self._on_exceed()


def build_command(staging_dir: Path, language: str, name: str, image: str) -> list[str]:
    command = ["sh", "-c", PYTHON_CMD if language == "python" else JAVA_CMD]
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--cpus",
        str(policy.MAX_CPU),
        "--memory",
        policy.MAX_MEMORY,
        "--memory-swap",
        policy.MAX_MEMORY,
        "--pids-limit",
        str(policy.MAX_PIDS),
        "--read-only",
        "--tmpfs",
        policy.MAX_TMPFS,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "codeoracle",
        "--workdir",
        "/sandbox",
        "-v",
        f"{staging_dir}:/sandbox:ro",
        "-v",
        "/home/codeoracle",
        image,
        *command,
    ]


def _kill_container(name: str) -> None:
    subprocess.run(["docker", "kill", name], capture_output=True, text=True)


def _normalize_python_coverage(data: dict) -> dict:
    totals = data.get("totals", {})
    uncovered: list[dict] = []
    for name, file_data in data.get("files", {}).items():
        if not name:
            continue
        rel = name.replace("/sandbox/src/", "")
        for line in file_data.get("missing_lines", []):
            uncovered.append({"file": rel, "line": line})
    return {
        "lineCoverage": round(float(totals.get("percent_covered", 0.0)), 2),
        "branchCoverage": round(float(totals.get("percent_branches_covered", 0.0)), 2),
        "uncoveredLines": uncovered,
    }


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def extract_coverage(stdout: str) -> dict | None:
    for line in reversed(stdout.splitlines()):
        cleaned = _ANSI.sub("", line).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        if "lineCoverage" in data:
            return data
        if isinstance(data.get("totals"), dict):
            return _normalize_python_coverage(data)
    return None


def run(staging_dir: Path, language: str, timeout: int, image: str) -> dict:
    name = f"codeoracle-sandbox-{uuid.uuid4().hex[:8]}"
    command = build_command(staging_dir, language, name, image)
    started = time.monotonic()

    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    out_reader = _BoundedReader(
        proc.stdout, policy.MAX_STDOUT_BYTES, on_exceed=lambda: _kill_container(name)
    )
    err_reader = _BoundedReader(
        proc.stderr, policy.MAX_STDERR_BYTES, on_exceed=lambda: _kill_container(name)
    )
    out_reader.start()
    err_reader.start()

    timed_out = False
    reason = "completed"
    try:
        exit_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_container(name)
        proc.kill()
        exit_code = policy.EXIT_TIMEOUT
        timed_out = True
        reason = "timeout"
    out_reader.join(timeout=5)
    err_reader.join(timeout=5)

    if not timed_out and (out_reader.exceeded or err_reader.exceeded):
        exit_code = policy.EXIT_RESOURCE_LIMIT
        reason = "stdout limit exceeded" if out_reader.exceeded else "stderr limit exceeded"

    stdout = out_reader.data
    stderr = err_reader.data
    coverage = extract_coverage(stdout)
    log = (stdout + "\n--- stderr ---\n" + stderr)[-LOG_LIMIT:]
    return {
        "exitCode": exit_code,
        "language": language,
        "timedOut": timed_out,
        "reason": reason,
        "durationSeconds": round(time.monotonic() - started, 1),
        "coverage": coverage,
        "log": log,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run tests in the CodeOracle sandbox.")
    parser.add_argument("--language", choices=["python", "java"], required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tests", type=Path, default=None)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--timeout", type=int, default=policy.DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="codeoracle-stage-") as tmp:
        staging_dir = Path(tmp)
        tests_dir = args.tests.resolve() if args.tests else None
        try:
            stage.stage(args.source.resolve(), args.language, tests_dir, staging_dir)
        except StageLimitError as exc:
            result = {
                "exitCode": policy.EXIT_RESOURCE_LIMIT,
                "language": args.language,
                "timedOut": False,
                "reason": str(exc),
                "coverage": None,
                "log": "",
            }
            print(json.dumps(result, indent=2))
            return 1
        result = run(staging_dir, args.language, args.timeout, args.image)

    print(json.dumps(result, indent=2))
    return 0 if result["exitCode"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
