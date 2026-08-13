"""Refactor proposal service (T-17): AST + graph -> LLM -> proposed code + WHY list."""

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
from app.db.models.repository import Repository
from app.llm import get_llm_gateway
from app.llm.prompts.breaking_change import BREAKING_CHANGE_SYSTEM, BREAKING_CHANGE_USER
from app.llm.prompts.refactor import REFACTOR_SYSTEM, REFACTOR_USER
from app.llm.security import secure_system_prompt
from app.schemas.refactor import BreakingChange, BreakingChangesResult, RefactorProposal
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


def _extract_arg_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    args = node.args
    # Get normal positional/keyword args
    arg_names = [a.arg for a in args.args]
    
    # Get positional only args (python 3.8+)
    posonly_names = [a.arg for a in getattr(args, "posonlyargs", [])]
    
    # Get keyword only args
    kwonly_names = [a.arg for a in args.kwonlyargs]
    
    # All argument names
    all_args = posonly_names + arg_names + kwonly_names
    if args.vararg:
        all_args.append(args.vararg.arg)
    if args.kwarg:
        all_args.append(args.kwarg.arg)

    # Required arguments (those without default values)
    num_defaults = len(args.defaults)
    normal_and_posonly = posonly_names + arg_names
    if num_defaults == 0:
        required_args = list(normal_and_posonly)
    else:
        required_args = list(normal_and_posonly[:-num_defaults])

    # Keyword only required args (where kw_defaults is None)
    for kw, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        if default is None:
            required_args.append(kw.arg)

    return {
        "name": node.name,
        "all_args": all_args,
        "required_args": required_args,
        "kwonly_args": kwonly_names,
        "vararg": args.vararg.arg if args.vararg else None,
        "kwarg": args.kwarg.arg if args.kwarg else None,
    }


def parse_python_signature(code: str, target_name: str | None = None) -> dict[str, Any] | None:
    """Parse python code and return function argument info."""
    try:
        tree = ast.parse(code)
        fallback_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if target_name and node.name == target_name:
                    return _extract_arg_info(node)
                if fallback_node is None:
                    fallback_node = node
        if fallback_node:
            return _extract_arg_info(fallback_node)
    except Exception:
        pass
    return None


def parse_java_signature(code: str, target_name: str | None = None) -> dict[str, Any] | None:
    """Parse Java method signature using regex."""
    try:
        # Clean comments
        clean_code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        clean_code = re.sub(r"//.*", "", clean_code)
        clean_code = clean_code.strip()
        
        # Match methodName(params) throws Exc1, Exc2 { / ;
        matches = list(re.finditer(r"(\w+)\s*\(([^)]*)\)\s*(?:throws\s+([^{;]+))?", clean_code))
        if not matches:
            return None
        
        target_match = None
        if target_name:
            for m in matches:
                if m.group(1) == target_name:
                    target_match = m
                    break
        if not target_match:
            target_match = matches[0]
            
        method_name = target_match.group(1)
        params_str = target_match.group(2).strip()
        throws_str = target_match.group(3)
        
        params = []
        if params_str:
            raw_params = params_str.split(",")
            for p in raw_params:
                p = p.strip()
                if p:
                    parts = p.split()
                    if len(parts) >= 2:
                        params.append({"type": parts[-2], "name": parts[-1]})
                    else:
                        params.append({"type": parts[0], "name": parts[0]})
                        
        exceptions = []
        if throws_str:
            exceptions = [e.strip() for e in throws_str.split(",") if e.strip()]
            
        return {
            "name": method_name,
            "params": params,
            "exceptions": exceptions,
        }
    except Exception:
        pass
    return None


def analyze_signature_changes(
    entity: Entity,
    original_code: str,
    proposed_code: str,
    affected_callers: list[str],
) -> list[BreakingChange]:
    """Fallback signature static analysis comparison."""
    changes: list[BreakingChange] = []
    if not original_code or not proposed_code:
        return changes
        
    language = (entity.language or "").lower()
    
    if "python" in language or (entity.file and entity.file.path.endswith(".py")):
        orig_sig = parse_python_signature(original_code, entity.name)
        prop_sig = parse_python_signature(proposed_code, entity.name)
        
        if orig_sig and prop_sig:
            # 1. Check for removed arguments
            removed_args = [arg for arg in orig_sig["all_args"] if arg not in prop_sig["all_args"]]
            for arg in removed_args:
                changes.append(
                    BreakingChange(
                        entity=entity.name,
                        impact="HIGH",
                        reason=f"Argument '{arg}' was removed from function signature.",
                        affected_callers=affected_callers,
                    )
                )
                
            # 2. Check for added required arguments
            added_required = [
                arg for arg in prop_sig["required_args"] 
                if arg not in orig_sig["all_args"]
            ]
            for arg in added_required:
                changes.append(
                    BreakingChange(
                        entity=entity.name,
                        impact="HIGH",
                        reason=f"Required argument '{arg}' was added to function signature.",
                        affected_callers=affected_callers,
                    )
                )
                
            # 3. Check for exception raising changes
            orig_exceptions = set(re.findall(r"raise\s+(\w+)", original_code))
            prop_exceptions = set(re.findall(r"raise\s+(\w+)", proposed_code))
            added_exceptions = prop_exceptions - orig_exceptions
            for exc in added_exceptions:
                changes.append(
                    BreakingChange(
                        entity=entity.name,
                        impact="MEDIUM",
                        reason=f"Function now raises exception '{exc}'.",
                        affected_callers=affected_callers,
                    )
                )
                
            # 4. Check return statement changes
            orig_returns = "return" in original_code
            prop_returns = "return" in proposed_code
            if orig_returns and not prop_returns:
                changes.append(
                    BreakingChange(
                        entity=entity.name,
                        impact="HIGH",
                        reason="Function no longer returns a value.",
                        affected_callers=affected_callers,
                    )
                )
                
            # 5. Check side effects (global variables)
            orig_globals = set(re.findall(r"\bglobal\s+(\w+)", original_code))
            prop_globals = set(re.findall(r"\bglobal\s+(\w+)", proposed_code))
            added_globals = prop_globals - orig_globals
            for g in added_globals:
                changes.append(
                    BreakingChange(
                        entity=entity.name,
                        impact="MEDIUM",
                        reason=f"Function now modifies global variable '{g}'.",
                        affected_callers=affected_callers,
                    )
                )

    elif "java" in language or (entity.file and entity.file.path.endswith(".java")):
        orig_sig = parse_java_signature(original_code, entity.name)
        prop_sig = parse_java_signature(proposed_code, entity.name)
        
        if orig_sig and prop_sig:
            # 1. Check parameter length
            if len(orig_sig["params"]) != len(prop_sig["params"]):
                count_orig = len(orig_sig["params"])
                count_prop = len(prop_sig["params"])
                changes.append(
                    BreakingChange(
                        entity=entity.name,
                        impact="HIGH",
                        reason=(
                            f"Method parameter count changed from"
                            f" {count_orig} to {count_prop}."
                        ),
                        affected_callers=affected_callers,
                    )
                )
            else:
                # Check if parameter types changed
                for i, (orig_p, prop_p) in enumerate(
                    zip(orig_sig["params"], prop_sig["params"], strict=True)
                ):
                    if orig_p["type"] != prop_p["type"]:
                        changes.append(
                            BreakingChange(
                                entity=entity.name,
                                impact="HIGH",
                                reason=(
                                    f"Parameter type at index {i} changed"
                                    f" from '{orig_p['type']}'"
                                    f" to '{prop_p['type']}'."
                                ),
                                affected_callers=affected_callers,
                            )
                        )
            
            # 2. Check exceptions thrown
            java_added_exceptions: list[str] = [
                e for e in prop_sig["exceptions"] if e not in orig_sig["exceptions"]
            ]
            for exc in java_added_exceptions:
                changes.append(
                    BreakingChange(
                        entity=entity.name,
                        impact="MEDIUM",
                        reason=f"Method now throws new exception '{exc}'.",
                        affected_callers=affected_callers,
                    )
                )
                
    return changes


def detect_breaking_changes(
    db: Session,
    entity: Entity,
    original_code: str,
    proposed_code: str,
) -> BreakingChangesResult:
    """Detect breaking changes between original and proposed code.

    Uses LLM completion first; falls back to signature static analysis.
    """
    callers_list: list[str] = []
    affected_callers: list[str] = []
    
    call_rows = db.query(Call).filter(Call.callee_id == entity.id).all()
    for call in call_rows:
        if call.caller_id is None:
            continue
        caller_entity = db.get(Entity, call.caller_id)
        if caller_entity and caller_entity.file:
            path_str = caller_entity.file.path
            line_str = f"{path_str}:{call.call_line}"
            if line_str not in affected_callers:
                affected_callers.append(line_str)
            callers_list.append(f"{caller_entity.name} ({line_str})")

    callers_str = "\n".join([f"- {c}" for c in callers_list]) if callers_list else "None"
    
    user_prompt = BREAKING_CHANGE_USER.format(
        entity=entity.name,
        original_code=original_code or "(source unavailable)",
        proposed_code=proposed_code or "(source unavailable)",
        callers=callers_str,
    )
    system_prompt = secure_system_prompt(BREAKING_CHANGE_SYSTEM)

    changes = []
    detected = False

    try:
        llm = get_llm_gateway()
        res = llm.complete_json(prompt=user_prompt, system=system_prompt)
        
        raw_changes = res.get("breaking_changes") or res.get("breakingChanges")
        if raw_changes and isinstance(raw_changes, list):
            for rc in raw_changes:
                if not isinstance(rc, dict):
                    continue
                ent_name = rc.get("entity") or rc.get("entity_name") or entity.name
                impact_str = str(rc.get("impact") or "LOW").upper()
                reason_str = str(rc.get("reason") or "Signature or behavior change detected.")
                callers = rc.get("affected_callers") or rc.get("affectedCallers") or []
                if not isinstance(callers, list):
                    callers = []
                
                normalized_callers = []
                for c in callers:
                    if isinstance(c, str):
                        normalized_callers.append(c)
                
                if impact_str in ("HIGH", "MEDIUM", "LOW"):
                    changes.append(
                        BreakingChange(
                            entity=ent_name,
                            impact=impact_str,
                            reason=reason_str,
                            affected_callers=normalized_callers or affected_callers,
                        )
                    )
            if changes:
                detected = True
    except Exception as exc:
        logger.warning("LLM breaking-change detection failed: %s", exc)

    if not changes:
        fallback_changes = analyze_signature_changes(
            entity=entity,
            original_code=original_code,
            proposed_code=proposed_code,
            affected_callers=affected_callers,
        )
        if fallback_changes:
            changes.extend(fallback_changes)
            detected = True

    return BreakingChangesResult(
        detected=detected,
        changes=changes,
    )


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

    breaking_changes = detect_breaking_changes(db, entity, original_source, proposed_code)

    return RefactorProposal(
        proposal_id=uuid.uuid4(),
        entity_id=entity.id,
        entity_name=entity.name,
        file_path=entity.file.path if entity.file else "",
        original=original_source,
        proposed=proposed_code,
        rationale=rationale,
        behavioral_differences=behavioral_diffs,
        breaking_changes=breaking_changes,
        original_checksum=_sha256(original_source),
    )
