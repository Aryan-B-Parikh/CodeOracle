"""Refactor Safety Score & Breaking-Change Detection service (T-18 & T-19)."""

from __future__ import annotations

import ast
import json
import logging
import re

from sqlalchemy.orm import Session

from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.refactor_proposal import RefactorProposalRecord
from app.db.models.repository import Repository
from app.db.models.test_run import TestRun
from app.llm import get_llm_gateway
from app.llm.prompts.breaking_change import (
    BREAKING_CHANGE_SYSTEM,
    BREAKING_CHANGE_USER,
)
from app.llm.security import secure_system_prompt
from app.schemas.safety import BreakingChangeItem, SafetyScoreData

logger = logging.getLogger(__name__)


def _extract_python_params(code: str) -> list[str] | None:
    """Parse Python function code and extract parameter names if valid syntax."""
    try:
        parsed = ast.parse(code)
        for node in ast.walk(parsed):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return [arg.arg for arg in node.args.args if arg.arg not in ("self", "cls")]
    except Exception:
        pass
    return None


def detect_breaking_changes(
    db: Session,
    repository: Repository,
    entity: Entity,
    proposed_code: str,
    original_code: str,
) -> list[BreakingChangeItem]:
    """Detect breaking changes between original and proposed code (T-18).

    Combines AST parameter/signature inspection with LLM static fact verification
    and maps callers to `file:line` locations.
    """
    affected_callers: list[str] = []
    call_rows = (
        db.query(Call)
        .filter(Call.callee_id == entity.id)
        .limit(20)
        .all()
    )
    for call in call_rows:
        if call.caller_id is None:
            continue
        caller_entity = db.get(Entity, call.caller_id)
        if caller_entity and caller_entity.file:
            affected_callers.append(
                f"{caller_entity.file.path}:{caller_entity.line_start}"
            )

    breaking_changes: list[BreakingChangeItem] = []

    # --- AST Parameter Analysis ---
    lang = (entity.language or (entity.file.language if entity.file else "")).lower()
    if lang == "python":
        orig_params = _extract_python_params(original_code)
        prop_params = _extract_python_params(proposed_code)

        if orig_params is not None and prop_params is not None:
            if len(orig_params) != len(prop_params):
                breaking_changes.append(
                    BreakingChangeItem(
                        entity=entity.name,
                        impact="HIGH",
                        reason=(
                            f"Parameter count changed from {len(orig_params)} "
                            f"({orig_params}) to {len(prop_params)} ({prop_params})."
                        ),
                        affected_callers=affected_callers,
                    )
                )
            else:
                removed = set(orig_params) - set(prop_params)
                if removed:
                    breaking_changes.append(
                        BreakingChangeItem(
                            entity=entity.name,
                            impact="HIGH",
                            reason=f"Parameters removed or renamed: {sorted(removed)}.",
                            affected_callers=affected_callers,
                        )
                    )

    # --- LLM Verification ---
    callers_summary = ", ".join(affected_callers) if affected_callers else "none"
    user_prompt = BREAKING_CHANGE_USER.format(
        entity=entity.name,
        original_code=original_code or "(unavailable)",
        proposed_code=proposed_code or "(unavailable)",
        callers=callers_summary,
    )
    system_prompt = secure_system_prompt(BREAKING_CHANGE_SYSTEM)

    try:
        llm = get_llm_gateway()
        resp = llm.complete(prompt=user_prompt, system=system_prompt)
        cleaned = re.sub(r"```(?:json)?\s*", "", resp.content)
        cleaned = cleaned.replace("```", "").strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            items = parsed.get("breaking_changes", [])
            for item in items:
                if isinstance(item, dict):
                    impact = str(item.get("impact", "MEDIUM")).upper()
                    if impact not in ("HIGH", "MEDIUM", "LOW"):
                        impact = "MEDIUM"
                    reason = str(item.get("reason", "Potential API incompatibility"))
                    # Avoid duplicate AST findings
                    if not any(b.reason == reason for b in breaking_changes):
                        breaking_changes.append(
                            BreakingChangeItem(
                                entity=str(item.get("entity", entity.name)),
                                impact=impact,  # type: ignore[arg-type]
                                reason=reason,
                                affected_callers=affected_callers,
                            )
                        )
    except Exception as exc:
        logger.warning("LLM breaking change detection exception: %s", exc)

    return breaking_changes


def calculate_safety_score(
    db: Session,
    repository: Repository,
    proposal_record: RefactorProposalRecord,
) -> SafetyScoreData:
    """Compute the 0-100 Refactor Safety Score (T-19).

    Sub-scores:
      1. api_compatibility: 100 - HIGH(-40) - MEDIUM(-20) - LOW(-5)
      2. test_compatibility: 100 if tests pass cleanly with >60% coverage
      3. dependency_impact: based on caller fan-in and graph complexity
      4. behavioral_risk: based on entity complexity and behavioral diffs
    """
    entity = proposal_record.entity or db.get(Entity, proposal_record.entity_id)

    # 1. Detect Breaking Changes & API Compatibility
    original_code = proposal_record.original
    proposed_code = proposal_record.proposed
    breaking_changes = detect_breaking_changes(
        db=db,
        repository=repository,
        entity=entity,
        proposed_code=proposed_code,
        original_code=original_code,
    )

    api_penalty = 0
    for bc in breaking_changes:
        if bc.impact == "HIGH":
            api_penalty += 40
        elif bc.impact == "MEDIUM":
            api_penalty += 20
        else:
            api_penalty += 5
    api_compatibility = max(0, 100 - api_penalty)

    # 2. Test Compatibility Sub-score
    latest_run = (
        db.query(TestRun)
        .filter(TestRun.repository_id == repository.id)
        .order_by(TestRun.created_at.desc())
        .first()
    )
    if latest_run is not None:
        if latest_run.status == "passed" and latest_run.target_reached:
            test_compatibility = 100
        elif latest_run.status == "passed":
            test_compatibility = 80
        else:
            test_compatibility = 40
    else:
        test_compatibility = 75  # Baseline assumption if no test run yet

    # 3. Dependency Impact Sub-score
    caller_count = (
        db.query(Call)
        .filter(Call.callee_id == proposal_record.entity_id)
        .count()
    )
    complexity = entity.complexity if entity else 1
    dep_penalty = min(60, caller_count * 12 + complexity * 2)
    dependency_impact = max(40, 100 - dep_penalty)

    # 4. Behavioral Risk Sub-score
    behavioral_diff_count = len(proposal_record.behavioral_differences or [])
    beh_penalty = min(70, complexity * 5 + behavioral_diff_count * 15)
    behavioral_risk = max(30, 100 - beh_penalty)

    # Calculate Total Weighted Score
    total = round(
        0.35 * api_compatibility
        + 0.25 * test_compatibility
        + 0.20 * dependency_impact
        + 0.20 * behavioral_risk
    )
    total = max(0, min(100, total))

    # Risk level classification
    if total >= 80:
        risk_level = "low"
    elif total >= 50:
        risk_level = "medium"
    else:
        risk_level = "high"

    # Generate Recommendations
    recommendations: list[str] = []
    if api_compatibility < 80:
        recommendations.append(
            "Review API signature changes to maintain backward compatibility with callers."
        )
    if dependency_impact < 70:
        recommendations.append(
            f"Entity has {caller_count} callers; verify dependent modules after refactor."
        )
    if behavioral_risk < 70:
        recommendations.append(
            "High complexity or behavioral changes detected; run full regression test suite."
        )
    if not recommendations:
        recommendations.append("Refactor proposal carries low risk; behavior is well-preserved.")

    return SafetyScoreData(
        proposal_id=proposal_record.id,
        total=total,
        api_compatibility=api_compatibility,
        test_compatibility=test_compatibility,
        dependency_impact=dependency_impact,
        behavioral_risk=behavioral_risk,
        risk_level=risk_level,  # type: ignore[arg-type]
        breaking_changes=breaking_changes,
        recommendations=recommendations,
    )
