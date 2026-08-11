"""Builds the hardened `docker run` command for executing generated tests.

Every constraint in security-policy.md is enforced here as docker flags.
Callers provide a staging directory containing a copy of the repo plus the
generated tests; the container never touches the original repository.
"""

import subprocess
from pathlib import Path

IMAGE = "codeoracle/sandbox:latest"
DEFAULT_TIMEOUT = 300
MAX_CPU = 1.0
MAX_MEMORY = "512m"
SCRATCH = "/tmp:size=64m"


def build_command(staging_dir: Path, language: str) -> list[str]:
    if language == "python":
        command = [
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests",
            "--cov",
            "src",
            "--cov-report=json:/tmp/coverage.json",
            "--cov-report=term",
        ]
    else:
        command = [
            "mvn",
            "-q",
            "test",
            "-Dmaven.repo.local=/tmp/.m2",
            "org.jacoco:jacoco-maven-plugin:report",
        ]

    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        str(MAX_CPU),
        "--memory",
        MAX_MEMORY,
        "--memory-swap",
        MAX_MEMORY,
        "--read-only",
        "--tmpfs",
        SCRATCH,
        "--user",
        "codeoracle",
        "--workdir",
        "/sandbox",
        "-v",
        f"{staging_dir}:/sandbox:ro",
        IMAGE,
        *command,
    ]


def run(staging_dir: Path, language: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    command = build_command(staging_dir, language)
    try:
        result = subprocess.run(command, timeout=timeout, text=True, capture_output=True)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "sandbox timeout exceeded"
