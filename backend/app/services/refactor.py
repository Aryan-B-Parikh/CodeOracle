"""Refactor proposal service (T-17): AST + graph -> LLM -> proposed code + WHY list."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.repository import Repository
from app.llm import get_llm_gateway
from app.llm.prompts.refactor import REFACTOR_SYSTEM, REFACTOR_USER
from app.llm.security import secure_system_prompt
from app.schemas.refactor import RefactorProposal
from app.services.analysis import repository_root

logger = logging.getLogger(__name__)


def _read_entity_source(repository: Repository, entity: Entity) -> str:
    """Read the source lines for an entity from disk; return empty string on miss."""
    if not entity.file:
        return ""
    try:
        root = repository_root(repository)
    except (FileNotFoundError, ValueError):
        return ""

    candidate = root / entity.file.path
    if not candidate.exists():
        for rel in (Path(entity.file.path).name, entity.file.path.lstrip("/\\")):
            alt = root / rel
            if alt.exists():
                candidate = alt
                break
        else:
            return ""

    try:
        lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, entity.line_start - 1)
        end = min(len(lines), entity.line_end)
        return "\n".join(lines[start:end])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read source for %s: %s", entity.name, exc)
        return ""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM response, safely type-checking the result."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def propose_refactor(
    db: Session,
    repository: Repository,
    entity_id: uuid.UUID,
) -> RefactorProposal:
    """Generate a refactor proposal for a single entity using AST facts + LLM."""
    entity = db.get(Entity, entity_id)
    if entity is None or entity.repository_id != repository.id:
        raise ValueError(f"entity {entity_id} not found in repository {repository.id}")

    original_source = _read_entity_source(repository, entity)

    callers: list[str] = []
    call_rows = db.query(Call).filter(Call.callee_id == entity_id).limit(20).all()
    for call in call_rows:
        if call.caller_id is None:
            continue
        caller_entity = db.get(Entity, call.caller_id)
        if caller_entity and caller_entity.file:
            callers.append(
                f"{caller_entity.name} ({caller_entity.file.path}:"
                f"{caller_entity.line_start})"
            )

    static_facts = (
        f"name={entity.name}, type={entity.type}, "
        f"complexity={entity.complexity}, "
        f"signature={entity.signature or 'unknown'}, "
        f"docstring='{entity.docstring or 'none'}'"
    )

    user_prompt = REFACTOR_USER.format(
        entity=entity.name,
        source=original_source or "(source unavailable — propose based on signature)",
        static_facts=static_facts,
        callers=", ".join(callers) if callers else "none",
    )
    system_prompt = secure_system_prompt(REFACTOR_SYSTEM)

    rationale: list[str] = []
    proposed_code = original_source
    behavioral_diffs: list[str] = []

    try:
        resp = get_llm_gateway().complete(prompt=user_prompt, system=system_prompt)
        parsed = _parse_llm_json(resp.content)
        if parsed:
            rationale = [str(r) for r in parsed.get("rationale", [])]
            proposed_code = str(parsed.get("proposed", original_source))
            behavioral_diffs = [
                str(d) for d in parsed.get("behavioral_differences", [])
            ]
        else:
            content = resp.content.strip()
            if content:
                rationale = ["LLM response was not valid JSON; raw proposal included."]
                proposed_code = content
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM refactor call failed for %s: %s", entity.name, exc)
        rationale = [
            "LLM unavailable — structural refactor suggested based on static analysis.",
            f"Entity has CCN complexity={entity.complexity}; consider extracting sub-functions.",
        ]
        if original_source and '"""' not in original_source:
            lines = original_source.splitlines()
            if lines:
                indent = "    " if lines[0].startswith("    ") else ""
                docstring_line = f'{indent}    """TODO: document {entity.name}."""'
                proposed_code = "\n".join([lines[0], docstring_line] + lines[1:])

    return RefactorProposal(
        proposal_id=uuid.uuid4(),
        entity_id=entity.id,
        entity_name=entity.name,
        file_path=entity.file.path if entity.file else "",
        original=original_source,
        proposed=proposed_code,
        rationale=rationale,
        behavioral_differences=behavioral_diffs,
        original_checksum=_sha256(original_source),
    )
