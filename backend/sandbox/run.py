"""Runner for the CodeOracle test sandbox.

Builds a hardened `docker run` (every flag maps to a constraint in
security-policy.md), executes the tests of a staged repository, and returns a
canonical result containing line/branch coverage as JSON.

Usage:
    python run.py --language python --source <repo-or-project-dir> [--tests <dir>]
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import stage

IMAGE = "codeoracle/sandbox:latest"
DEFAULT_TIMEOUT = 300
MAX_CPU = 1.0
MAX_MEMORY = "512m"
MAX_PIDS = 128
LOG_LIMIT = 8000

PYTHON_CMD = (
    "cd /home/codeoracle && "
    "pytest /sandbox/tests -p no:cacheprovider --cov /sandbox/src --cov-branch "
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
        str(MAX_CPU),
        "--memory",
        MAX_MEMORY,
        "--memory-swap",
        MAX_MEMORY,
        "--pids-limit",
        str(MAX_PIDS),
        "--read-only",
        "--tmpfs",
        "/tmp:size=64m",
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
    try:
        result = subprocess.run(command, timeout=timeout, text=True, capture_output=True)
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        subprocess.run(["docker", "kill", name], capture_output=True, text=True)
        stdout = exc.stdout or ""
        stderr = "sandbox timeout exceeded (container killed)"
        exit_code = 124
        timed_out = True

    coverage = extract_coverage(stdout)
    log = (stdout + "\n--- stderr ---\n" + stderr)[-LOG_LIMIT:]
    return {
        "exitCode": exit_code,
        "language": language,
        "timedOut": timed_out,
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
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="codeoracle-stage-") as tmp:
        staging_dir = Path(tmp)
        tests_dir = args.tests.resolve() if args.tests else None
        stage.stage(args.source.resolve(), args.language, tests_dir, staging_dir)
        result = run(staging_dir, args.language, args.timeout, args.image)

    print(json.dumps(result, indent=2))
    return 0 if result["exitCode"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
