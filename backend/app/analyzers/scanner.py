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

UNSUPPORTED_BY_SUFFIX = {
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".dart": "Dart",
    ".scala": "Scala",
}

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
    unsupported_languages: dict[str, int]
    unknown_count: int
    language_counts: dict[str, int]
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
    unsupported_languages: dict[str, int] = {}
    unknown = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _is_ignored(rel.parts):
            continue
        language = detect_language(path)
        if language is None:
            unsupported_name = UNSUPPORTED_BY_SUFFIX.get(path.suffix.lower())
            if unsupported_name is not None:
                unsupported_languages[unsupported_name] = (
                    unsupported_languages.get(unsupported_name, 0) + 1
                )
            else:
                unknown += 1
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

    language_counts: dict[str, int] = {}
    for file in detected:
        language_counts[file.language] = language_counts.get(file.language, 0) + 1
    for name, count in unsupported_languages.items():
        language_counts[name] = count
    if unknown:
        language_counts["other"] = unknown
    unsupported_count = sum(unsupported_languages.values()) + unknown

    warnings: list[str] = []
    if not detected and unsupported_count == 0:
        warnings.append("repository contains no files to analyze")
    if unsupported_languages:
        names = ", ".join(sorted(unsupported_languages))
        warnings.append(
            f"{sum(unsupported_languages.values())} unsupported file(s) across {names}"
        )
    if unknown:
        warnings.append(f"{unknown} file(s) with unrecognized extensions")
    if not any(f.language in SUPPORTED_LANGUAGES for f in detected):
        warnings.append("no supported languages detected (python/java required)")

    return ScanResult(
        files=detected,
        unsupported_count=unsupported_count,
        unsupported_languages=unsupported_languages,
        unknown_count=unknown,
        language_counts=language_counts,
        warnings=warnings,
    )
