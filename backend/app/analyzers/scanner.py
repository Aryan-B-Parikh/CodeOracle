"""Pure file classification and language detection (no I/O beyond reading files).

Ground truth for T-03: which files exist, what language they are, their size,
and their content hash. No parsing or LLM here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyw": "python",
    ".java": "java",
}

SUPPORTED_LANGUAGES = ("python", "java")

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

MAX_SCAN_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True)
class DetectedFile:
    path: str
    language: str
    loc: int
    sha256: str


@dataclass(frozen=True)
class ScanResult:
    files: list[DetectedFile]
    unsupported_count: int
    warnings: list[str]


def detect_language(path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_loc(text: str) -> int:
    return len(text.splitlines())


def _is_ignored(parts: tuple[str, ...]) -> bool:
    return any(part in IGNORED_DIRS for part in parts)


def scan_directory(root: Path) -> ScanResult:
    detected: list[DetectedFile] = []
    unsupported = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _is_ignored(rel.parts):
            continue
        language = detect_language(path)
        if language is None:
            unsupported += 1
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        detected.append(
            DetectedFile(
                path=str(rel).replace("\\", "/"),
                language=language,
                loc=_count_loc(text),
                sha256=_file_sha256(path),
            )
        )

    warnings: list[str] = []
    if not detected and unsupported == 0:
        warnings.append("repository contains no files to analyze")
    if unsupported > 0:
        warnings.append(f"{unsupported} unsupported file(s) classified as 'other'")
    if not any(f.language in SUPPORTED_LANGUAGES for f in detected):
        warnings.append("no supported languages detected (python/java required)")

    return ScanResult(files=detected, unsupported_count=unsupported, warnings=warnings)
