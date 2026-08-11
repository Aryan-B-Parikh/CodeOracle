import json
from pathlib import Path

_cache: dict[str, list[dict]] = {}


def load(path: Path) -> list[dict]:
    key = str(path)
    if key in _cache:
        return _cache[key]
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    _cache[key] = data
    return data


def save(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2))
    _cache[str(path)] = records


def clear_cache() -> None:
    _cache.clear()
