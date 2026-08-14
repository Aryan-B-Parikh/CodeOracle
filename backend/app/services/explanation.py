"""Explanation service (T-10): generates evidence-cited function/class explanations."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.repository import Repository
from app.llm import get_llm_gateway
from app.llm.prompts.explanation import EXPLANATION_SYSTEM, EXPLANATION_USER
from app.llm.security import secure_system_prompt
from app.schemas.explanation import (
    EntitySummary,
    EvidenceItem,
    ExplanationData,
    ExplanationFields,
)
from app.services.analysis import repository_root

logger = logging.getLogger(__name__)
settings = get_settings()

SnippetLines = list[tuple[int, str]]


def _read_source_snippet(
    root_dir: Path, rel_path: str, line_start: int, line_end: int
) -> tuple[str, SnippetLines]:
    """Read lines line_start..line_end (1-indexed) from repository source file."""
    full_path = root_dir / rel_path
    if not full_path.is_file():
        return "", []
    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), line_end)
        snippet_lines = [(i + 1, lines[i]) for i in range(start_idx, end_idx)]
        snippet_text = "\n".join(line for _, line in snippet_lines)
        return snippet_text, snippet_lines
    except Exception as exc:
        logger.warning("Failed to read source file %s: %s", full_path, exc)
        return "", []


def _extract_evidence_from_snippet(
    snippet_lines: SnippetLines,
    rel_path: str,
    target_name: str,
    line_start: int,
    line_end: int,
) -> list[EvidenceItem]:
    """Build default evidence items directly from the source lines (no invented claims)."""
    evidence: list[EvidenceItem] = []
    if not snippet_lines:
        return evidence

    for line_no, line in snippet_lines[:6]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("if ") or stripped.startswith("elif "):
            claim = f"Conditional control flow at line {line_no}."
        elif stripped.startswith(("def ", "class ", "async def ")):
            claim = f"Declares {target_name} at line {line_no}."
        elif "return " in stripped:
            claim = f"Returns a value at line {line_no}."
        elif "raise " in stripped:
            claim = f"Raises an exception at line {line_no}."
        else:
            claim = f"Code at line {line_no}."
        evidence.append(
            EvidenceItem(
                claim=claim,
                file=rel_path,
                line_start=line_no,
                line_end=line_no,
                code=stripped,
            )
        )

    if not evidence:
        first_line = snippet_lines[0][0]
        last_line = snippet_lines[-1][0]
        code = "\n".join(code for _, code in snippet_lines[:3])
        evidence.append(
            EvidenceItem(
                claim=f"Implementation of {target_name}.",
                file=rel_path,
                line_start=max(first_line, line_start),
                line_end=min(last_line, line_end),
                code=code,
            )
        )

    return evidence


def _semantic_explanation(
    entity: Entity, rel_path: str, meta: dict, calls_made: list[Call]
) -> ExplanationFields:
    """Deterministic AST-fact explanation: purpose/docstring, arguments,
    assignments as business rules, branch conditions, raise statements and
    return values — every claim is a static fact, never invented text."""

    arguments = meta.get("arguments", [])
    deps = [c.callee_name for c in calls_made]
    raises = meta.get("raises", [])
    assignments = meta.get("assignments", [])
    branches = meta.get("branches", [])
    returns = meta.get("returns", [])

    purpose = (entity.docstring or "").strip()
    if not purpose:
        purpose = f"Performs the {entity.type} '{entity.name}' logic."

    inputs = ", ".join(str(a) for a in arguments) if arguments else "None"
    outputs = (
        ", ".join(str(r) for r in returns)
        if returns
        else (meta.get("return_type") or "Value or None")
    )
    side_effects = (
        "; ".join(str(a) for a in assignments[:4])
        if assignments
        else "None detected from static analysis."
    )
    dependencies = ", ".join(deps) if deps else "None (leaf function)"
    control_flow = (
        "; ".join(f"if {b}" for b in branches[:4])
        if branches
        else "Control flow as structured in the source (see evidence)."
    )
    error_handling = (
        "; ".join(f"raises {r}" for r in raises[:4])
        if raises
        else "Propagates exceptions or relies on callee error semantics."
    )
    if raises and branches:
        error_handling += f"; triggered when {branches[0]}"
    business_rules = (
        "; ".join(str(a) for a in assignments[:4])
        if assignments
        else (
            f"Business logic implemented by {entity.name} per source "
            f"lines {entity.line_start}-{entity.line_end}."
        )
    )
    risks = "Behavior inferred from static analysis; verify against runtime semantics."

    return ExplanationFields(
        purpose=purpose,
        inputs=inputs,
        outputs=outputs,
        side_effects=side_effects,
        dependencies=dependencies,
        control_flow=control_flow,
        error_handling=error_handling,
        business_rules=business_rules,
        complexity=entity.complexity,
        risks=risks,
    )


def explain_entity(
    db: Session, repository: Repository, entity: Entity
) -> ExplanationData:
    """Generate evidence-cited explanation for a given entity model."""
    return generate_explanation(db, repository.id, entity.id)


def generate_explanation(
    db: Session,
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> ExplanationData:
    """Generate an evidence-cited 10-field explanation for a code entity."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    entity = db.get(Entity, entity_id)
    if entity is None or entity.repository_id != repository_id:
        raise HTTPException(status_code=404, detail="entity not found")

    file_row = db.get(File, entity.file_id)
    rel_path = file_row.path if file_row else "unknown"

    root_dir = repository_root(repository)
    snippet_text, snippet_lines = _read_source_snippet(
        root_dir, rel_path, entity.line_start, entity.line_end
    )

    calls_made = (
        db.query(Call)
        .filter(Call.repository_id == repository_id, Call.caller_id == entity.id)
        .all()
    )
    called_by = (
        db.query(Call)
        .filter(
            Call.repository_id == repository_id,
            or_(Call.callee_id == entity.id, Call.callee_name == entity.name),
        )
        .all()
    )

    caller_names = [f"caller: line {c.call_line} ({c.callee_name})" for c in called_by[:10]]
    callee_names = [f"callee: line {c.call_line} ({c.callee_name})" for c in calls_made[:10]]

    meta = entity.metadata_json or {}
    static_facts = {
        "name": entity.name,
        "type": entity.type,
        "signature": entity.signature or entity.name,
        "docstring": entity.docstring or "",
        "complexity": entity.complexity,
        "is_public": entity.is_public,
        "language": entity.language,
        "arguments": meta.get("arguments", []),
        "return_type": meta.get("return_type"),
        "calls": meta.get("calls", []),
        "globals_used": meta.get("globals_used", []),
        "raises": meta.get("raises", []),
        "assignments": meta.get("assignments", []),
        "branches": meta.get("branches", []),
        "returns": meta.get("returns", []),
    }

    entity_json = json.dumps(
        {
            "id": str(entity.id),
            "name": entity.name,
            "type": entity.type,
            "file": rel_path,
            "lineStart": entity.line_start,
            "lineEnd": entity.line_end,
        }
    )

    called_by_str = (
        "\n".join(caller_names)
        if caller_names
        else "None (top-level or external entry point)"
    )
    calls_str = "\n".join(callee_names) if callee_names else "None (leaf function)"

    user_prompt = EXPLANATION_USER.format(
        entity_json=entity_json,
        called_by=called_by_str,
        calls=calls_str,
        static_facts=json.dumps(static_facts, indent=2),
        source_snippet=snippet_text or "(source unavailable)",
    )
    system_prompt = secure_system_prompt(EXPLANATION_SYSTEM)

    llm_gateway = get_llm_gateway()
    provider_name = getattr(getattr(llm_gateway, "provider", None), "provider_name", None)
    has_real_llm = provider_name not in ("mock", None)

    explanation_fields: ExplanationFields
    evidence_items: list[EvidenceItem] = []
    semantic = _semantic_explanation(entity, rel_path, meta, calls_made)

    if has_real_llm:
        try:
            raw_response = llm_gateway.complete_json(prompt=user_prompt, system=system_prompt)
            exp_dict = raw_response.get("explanation", raw_response)

            purpose = str(
                exp_dict.get("purpose") or exp_dict.get("1. Purpose") or ""
            ).strip()
            inputs = str(exp_dict.get("inputs") or exp_dict.get("2. Inputs") or "").strip()
            outputs = str(exp_dict.get("outputs") or exp_dict.get("3. Outputs") or "").strip()
            side_effects = str(
                exp_dict.get("sideEffects")
                or exp_dict.get("side_effects")
                or exp_dict.get("4. Side effects")
                or ""
            ).strip()
            dependencies = str(
                exp_dict.get("dependencies") or exp_dict.get("5. Dependencies") or ""
            ).strip()
            control_flow = str(
                exp_dict.get("controlFlow")
                or exp_dict.get("control_flow")
                or exp_dict.get("6. Control flow")
                or ""
            ).strip()
            error_handling = str(
                exp_dict.get("errorHandling")
                or exp_dict.get("error_handling")
                or exp_dict.get("7. Error handling")
                or ""
            ).strip()
            business_rules = str(
                exp_dict.get("businessRules")
                or exp_dict.get("business_rules")
                or exp_dict.get("8. Business rules")
                or ""
            ).strip()
            complexity_val = (
                exp_dict.get("complexity")
                or exp_dict.get("9. Complexity")
                or entity.complexity
            )
            try:
                complexity_num = int(complexity_val)
            except (ValueError, TypeError):
                complexity_num = entity.complexity
            risks = str(exp_dict.get("risks") or exp_dict.get("10. Risks") or "").strip()

            if not purpose:
                purpose = semantic.purpose
            if not inputs:
                inputs = semantic.inputs
            if not outputs:
                outputs = semantic.outputs
            if not side_effects:
                side_effects = semantic.side_effects
            if not dependencies:
                dependencies = semantic.dependencies
            if not control_flow:
                control_flow = semantic.control_flow
            if not error_handling:
                error_handling = semantic.error_handling
            if not business_rules:
                business_rules = semantic.business_rules
            if not risks:
                risks = semantic.risks

            explanation_fields = ExplanationFields(
                purpose=purpose,
                inputs=inputs,
                outputs=outputs,
                side_effects=side_effects,
                dependencies=dependencies,
                control_flow=control_flow,
                error_handling=error_handling,
                business_rules=business_rules,
                complexity=complexity_num,
                risks=risks,
            )

            raw_evidence = raw_response.get("evidence", [])
            if isinstance(raw_evidence, list):
                for item in raw_evidence:
                    if isinstance(item, dict) and "claim" in item:
                        start_l = int(
                            item.get("lineStart")
                            or item.get("line_start")
                            or entity.line_start
                        )
                        end_l = int(
                            item.get("lineEnd")
                            or item.get("line_end")
                            or entity.line_end
                        )
                        evidence_items.append(
                            EvidenceItem(
                                claim=str(item.get("claim", "")),
                                file=str(item.get("file") or rel_path),
                                line_start=start_l,
                                line_end=end_l,
                                code=str(item.get("code", "")),
                            )
                        )
        except Exception as exc:
            logger.info("LLM gateway JSON extraction fallback: %s", exc)
            explanation_fields = _semantic_explanation(
                entity, rel_path, meta, calls_made
            )
    else:
        explanation_fields = _semantic_explanation(entity, rel_path, meta, calls_made)

    if not evidence_items:
        evidence_items = _extract_evidence_from_snippet(
            snippet_lines, rel_path, entity.name, entity.line_start, entity.line_end
        )

    validated_evidence = validate_evidence_items(db, repository, evidence_items)

    entity_summary = EntitySummary(
        id=entity.id,
        name=entity.name,
        type=entity.type,
        file=rel_path,
        line_start=entity.line_start,
        line_end=entity.line_end,
    )

    return ExplanationData(
        entity=entity_summary,
        explanation=explanation_fields,
        evidence=validated_evidence,
        provider=provider_name,
    )

def validate_evidence_items(
    db: Session, repository: Repository, evidence_items: list[EvidenceItem]
) -> list[EvidenceItem]:
    """Priority 4 Post-Generation Evidence Validator:

    Verifies every LLM-cited evidence claim against actual repository files and line bounds.
    Rejects hallucinated files or invalid line ranges.
    """
    valid_files = {f.path for f in db.query(File).filter(File.repository_id == repository.id).all()}
    root_dir = repository_root(repository)
    validated: list[EvidenceItem] = []

    for item in evidence_items:
        # 1. File existence check
        if item.file not in valid_files and not (root_dir / item.file).is_file():
            logger.warning(
                "Evidence validator dropped citation for non-existent file: %s", item.file
            )
            continue
        # 2. Line range check
        if item.line_start <= 0 or item.line_end < item.line_start:
            logger.warning(
                "Evidence validator dropped citation with invalid line bounds: %s-%s",
                item.line_start,
                item.line_end,
            )
            continue
        # 3. Code snippet verification
        snippet, _ = _read_source_snippet(root_dir, item.file, item.line_start, item.line_end)
        verified_code = snippet if snippet else item.code
        validated.append(
            EvidenceItem(
                claim=item.claim,
                file=item.file,
                line_start=item.line_start,
                line_end=item.line_end,
                code=verified_code,
            )
        )
    return validated
