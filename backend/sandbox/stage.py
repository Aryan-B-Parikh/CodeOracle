"""Build a per-run staging directory for the sandbox from a source repo.

Python layout:  <stage>/src/<modules...>  <stage>/tests/<tests...> (+ conftest)
Java layout:    <stage>/ is the Maven project root (pom.xml + src/...)

The container mounts <stage> read-only at /sandbox, so the original
repository is never touched.
"""

import shutil
from pathlib import Path

from policy import MAX_GENERATED_TESTS_BYTES, MAX_STAGED_SOURCE_BYTES

PYTHON_CONFTEST = "import sys\nsys.path.insert(0, '/sandbox/src')\n"


class StageLimitError(Exception):
    pass


def _total_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _enforce_limits(stage_dir: Path, tests_dir: Path | None) -> None:
    staged = _total_bytes(stage_dir)
    if staged > MAX_STAGED_SOURCE_BYTES:
        raise StageLimitError(
            f"staged source exceeds limit ({staged} > {MAX_STAGED_SOURCE_BYTES} bytes)"
        )
    if tests_dir is not None and tests_dir.is_dir():
        tests = _total_bytes(tests_dir)
        if tests > MAX_GENERATED_TESTS_BYTES:
            raise StageLimitError(
                f"generated tests exceed limit ({tests} > {MAX_GENERATED_TESTS_BYTES} bytes)"
            )


def _copy_python_source(source_dir: Path, stage: Path) -> None:
    src = stage / "src"
    for path in sorted(source_dir.rglob("*.py")):
        parts = path.relative_to(source_dir).parts
        if any(
            part.startswith(".") or part in {"__pycache__", "tests", "conftest.py"}
            for part in parts
        ):
            continue
        dest = src / path.relative_to(source_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)


def _copy_python_tests(source_dir: Path, tests_dir: Path | None, stage: Path) -> None:
    tests = stage / "tests"
    if tests_dir is not None and tests_dir.is_dir():
        shutil.copytree(
            tests_dir,
            tests,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    else:
        tests.mkdir(parents=True)
    conftest = tests / "conftest.py"
    if not conftest.exists():
        conftest.write_text(PYTHON_CONFTEST)


def _stage_python(source_dir: Path, tests_dir: Path | None, stage: Path) -> None:
    _copy_python_source(source_dir, stage)
    _copy_python_tests(source_dir, tests_dir, stage)


def _stage_java(source_dir: Path, tests_dir: Path | None, stage: Path) -> None:
    shutil.copytree(source_dir, stage, dirs_exist_ok=True)
    if tests_dir is not None and tests_dir.is_dir():
        test_root = stage / "src" / "test"
        for path in sorted(tests_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(tests_dir)
                dest = test_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)


def stage(source_dir: Path, language: str, tests_dir: Path | None, stage_dir: Path) -> None:
    if language == "python":
        _stage_python(source_dir, tests_dir, stage_dir)
    else:
        _stage_java(source_dir, tests_dir, stage_dir)
    _enforce_limits(stage_dir, tests_dir)
