"""Entity impact analysis service (T-12)."""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.repository import Repository
from app.schemas.impact import (
    CalleeItem,
    CallerItem,
    ImpactData,
    ImpactEntitySummary,
)

logger = logging.getLogger(__name__)


def calculate_impact(
    db: Session,
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> ImpactData:
    """Calculate callers, callees, aggregated impact rating, and impact reason."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    entity = db.get(Entity, entity_id)
    if entity is None or entity.repository_id != repository_id:
        raise HTTPException(status_code=404, detail="entity not found")

    file_row = db.get(File, entity.file_id)
    rel_path = file_row.path if file_row else "unknown"

    # Query callers (calls targeting this entity)
    raw_callers = (
        db.query(Call)
        .filter(
            Call.repository_id == repository_id,
            or_(
                Call.callee_id == entity.id,
                Call.callee_name == entity.name,
                Call.callee_name.endswith(f".{entity.name}"),
            ),
        )
        .all()
    )

    callers_list: list[CallerItem] = []
    seen_callers: set[tuple[str, str, int]] = set()

    for call in raw_callers:
        caller_entity = (
            db.get(Entity, call.caller_id) if call.caller_id is not None else None
        )
        caller_name = (
            caller_entity.name
            if caller_entity
            else (entity.name if call.caller_id is None else "module")
        )
        caller_file = (
            caller_entity.file.path
            if (caller_entity and caller_entity.file)
            else rel_path
        )
        line_start = caller_entity.line_start if caller_entity else call.call_line
        line_end = caller_entity.line_end if caller_entity else call.call_line
        call_line = call.call_line or line_start

        key = (caller_name, caller_file, call_line)
        if key in seen_callers:
            continue
        seen_callers.add(key)

        callers_list.append(
            CallerItem(
                caller=caller_name,
                file=caller_file,
                line_start=line_start,
                line_end=line_end,
                call_line=call_line,
            )
        )

    # Query callees (calls made by this entity)
    raw_callees = (
        db.query(Call)
        .filter(Call.repository_id == repository_id, Call.caller_id == entity.id)
        .all()
    )

    callees_list: list[CalleeItem] = []
    seen_callees: set[tuple[str, str]] = set()

    for call in raw_callees:
        callee_entity = (
            db.get(Entity, call.callee_id) if call.callee_id is not None else None
        )
        callee_name = call.callee_name
        callee_file = (
            callee_entity.file.path
            if (callee_entity and callee_entity.file)
            else rel_path
        )
        line_start = callee_entity.line_start if callee_entity else 0
        line_end = callee_entity.line_end if callee_entity else 0

        key_callee = (callee_name, callee_file)
        if key_callee in seen_callees:
            continue
        seen_callees.add(key_callee)

        callees_list.append(
            CalleeItem(
                callee=callee_name,
                file=callee_file,
                line_start=line_start,
                line_end=line_end,
            )
        )

    distinct_modules = {c.file for c in callers_list}
    total_callers = len(callers_list)

    if (
        total_callers >= 3
        or len(distinct_modules) >= 2
        or (total_callers >= 1 and entity.complexity >= 10)
    ):
        impact_level = "HIGH"
        impact_reason = (
            f"{total_callers} callers across {len(distinct_modules)} modules depend "
            f"on this function's behavior and error semantics."
        )
    elif total_callers >= 1 or entity.complexity >= 5:
        impact_level = "MEDIUM"
        mod_text = "modules" if len(distinct_modules) != 1 else "module"
        impact_reason = (
            f"{total_callers} caller in {len(distinct_modules)} {mod_text} depends "
            f"on this function."
        )
    else:
        impact_level = "LOW"
        impact_reason = "No callers in this repository depend on this function; low impact risk."

    entity_summary = ImpactEntitySummary(
        name=entity.name,
        file=rel_path,
        line_start=entity.line_start,
        line_end=entity.line_end,
    )

    return ImpactData(
        entity=entity_summary,
        callers=callers_list,
        callees=callees_list,
        impact=impact_level,
        impact_reason=impact_reason,
    )
