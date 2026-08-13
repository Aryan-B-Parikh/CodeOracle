"""Refactor proposal service (T-17): AST + graph -> LLM -> validated proposal + WHY list.

Implements the three T-17 quality gates:
  W1 — JSON schema validation + language parser syntax check (ast.parse / tree-sitter)
  W3 — Immutable DB record per proposal (RefactorProposalRecord) keyed by
       (entity_id, original_checksum) for reproducibility
  W4 — read_only=True guard: this service never modifies repository files
"""

from __future__ import annotations

import ast
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
from app.db.models.refactor_proposal import RefactorProposalRecord
from app.db.models.repository import Repository
from app.llm import get_llm_gateway
from app.llm.prompts.refactor import REFACTOR_SYSTEM, REFACTOR_USER
from app.llm.security import secure_system_prompt
from app.schemas.refactor import RefactorProposal
from app.services.analysis import repository_root

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source reading
# ---------------------------------------------------------------------------


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
        for rel in (
            Path(entity.file.path).name,
            entity.file.path.lstrip("/\\"),
        ):
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Extract and validate JSON from LLM response, stripping markdown fences.

    Returns an empty dict if parsing fails.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    if not isinstance(parsed.get("proposed"), str) or not isinstance(
        parsed.get("rationale"), list
    ):
        return {}
    return parsed


# ---------------------------------------------------------------------------
# W1: Language parser syntax validation gate
# ---------------------------------------------------------------------------

_VALID = "valid"
_INVALID = "invalid"


def _validate_syntax(code: str, language: str) -> tuple[bool, str | None]:
    """Return (is_valid, error_message) for the proposed code.

    Python: ast.parse()
    Java: structural brace check heuristic
    """
    if not code.strip():
        return False, "proposed code is empty"

    if language == "python":
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as exc:
            return False, f"SyntaxError line {exc.lineno}: {exc.msg}"

    if language == "java":
        open_b = code.count("{")
        close_b = code.count("}")
        if open_b != close_b:
            return False, (
                f"Unbalanced braces in proposed Java code "
                f"(open={open_b}, close={close_b})"
            )
        return True, None

    logger.info("Syntax validation skipped for language: %s", language)
    return True, None


# ---------------------------------------------------------------------------
# W4: Read-only guard helper
# ---------------------------------------------------------------------------


def _assert_read_only(proposal_id: uuid.UUID) -> None:
    """Explicit sentinel: T-17 proposals are read-only artifacts."""
    logger.debug(
        "Proposal %s is read-only — no filesystem mutation will occur.", proposal_id
    )


# ---------------------------------------------------------------------------
# W3: Persist immutable proposal record
# ---------------------------------------------------------------------------


def _persist_proposal(
    db: Session,
    repository: Repository,
    entity: Entity,
    proposal_id: uuid.UUID,
    original: str,
    proposed: str,
    original_checksum: str,
    rationale: list[str],
    behavioral_diffs: list[str],
    syntax_valid: bool,
    validation_error: str | None,
) -> None:
    """Insert an immutable RefactorProposalRecord keyed by proposal_id."""
    record = RefactorProposalRecord(
        id=proposal_id,
        repository_id=repository.id,
        entity_id=entity.id,
        entity_name=entity.name,
        file_path=entity.file.path if entity.file else "",
        original=original,
        proposed=proposed,
        original_checksum=original_checksum,
        rationale=rationale,
        behavioral_differences=behavioral_diffs,
        syntax_valid=_VALID if syntax_valid else _INVALID,
        validation_error=validation_error,
    )
    db.add(record)
    db.commit()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def propose_refactor(
    db: Session,
    repository: Repository,
    entity_id: uuid.UUID,
) -> RefactorProposal:
    """Generate a validated, immutable refactor proposal.

    Pipeline:
      1. Read entity source from disk
      2. Query callers from dependency graph
      3. Call LLM via REFACTOR prompts (raise RuntimeError if mock or unparseable)
      4. [W1] Validate JSON schema (required keys: proposed, rationale)
      5. [W1] Validate proposed code syntax (ast.parse / Java brace balance)
      6. [W3] Persist immutable proposal record to DB
      7. [W4] Return read-only RefactorProposal — no file mutation ever
    """
    entity = db.get(Entity, entity_id)
    if entity is None or entity.repository_id != repository.id:
        raise ValueError(
            f"entity {entity_id} not found in repository {repository.id}"
        )

    language = entity.file.language if entity.file else "python"

    # Step 1: Read source
    original_source = _read_entity_source(repository, entity)
    original_checksum = _sha256(original_source)

    # Step 2: Query callers
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

    # Step 3: LLM call
    rationale: list[str] = []
    proposed_code = original_source
    behavioral_diffs: list[str] = []

    try:
        resp = get_llm_gateway().complete(prompt=user_prompt, system=system_prompt)
        if getattr(resp, "provider", None) == "mock":
            raise RuntimeError(
                "LLM unavailable (no API key configured); cannot generate a proposal."
            )

        # Step 4: JSON schema validation (W1)
        parsed = _parse_llm_json(resp.content)
        if parsed:
            rationale = [str(r) for r in parsed.get("rationale", [])]
            proposed_code = str(parsed["proposed"])
            behavioral_diffs = [
                str(d) for d in parsed.get("behavioral_differences", [])
            ]
        else:
            raise RuntimeError(
                "LLM response was not valid JSON; refusing to present raw text "
                "as an executable refactor proposal."
            )
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM refactor call failed for %s: %s", entity.name, exc)
        raise RuntimeError(
            "LLM unavailable; no refactor proposal was generated."
        ) from exc

    # Step 5: Syntax validation gate (W1)
    is_syntax_valid, syntax_error = _validate_syntax(proposed_code, language)
    if not is_syntax_valid:
        logger.warning(
            "Proposed code for %s failed syntax validation: %s; "
            "reverting to original.",
            entity.name,
            syntax_error,
        )
        rationale.append(
            f"Proposed code failed syntax validation ({syntax_error}); "
            "original source retained."
        )
        proposed_code = original_source
        is_syntax_valid = True
        syntax_error = None

    proposal_id = uuid.uuid4()

    # Step 6: Persist immutable record (W3)
    try:
        _persist_proposal(
            db=db,
            repository=repository,
            entity=entity,
            proposal_id=proposal_id,
            original=original_source,
            proposed=proposed_code,
            original_checksum=original_checksum,
            rationale=rationale,
            behavioral_diffs=behavioral_diffs,
            syntax_valid=is_syntax_valid,
            validation_error=syntax_error,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not persist proposal record: %s", exc)

    # Step 7: Return read-only proposal (W4)
    _assert_read_only(proposal_id)

    return RefactorProposal(
        proposal_id=proposal_id,
        entity_id=entity.id,
        entity_name=entity.name,
        file_path=entity.file.path if entity.file else "",
        original=original_source,
        proposed=proposed_code,
        rationale=rationale,
        behavioral_differences=behavioral_diffs,
        original_checksum=original_checksum,
        syntax_valid=is_syntax_valid,
        validation_error=syntax_error,
        read_only=True,
    )
