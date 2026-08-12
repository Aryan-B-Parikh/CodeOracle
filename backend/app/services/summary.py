"""Summary service (T-11): architecture classification, issues, and repository overview."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models.analysis import Analysis
from app.db.models.file import File
from app.db.models.repository import Repository
from app.llm import get_llm_gateway
from app.llm.prompts.repository_summary import (
    REPOSITORY_SUMMARY_SYSTEM,
    REPOSITORY_SUMMARY_USER,
)
from app.llm.security import secure_system_prompt
from app.schemas.summary import (
    AnalysisSummaryPayload,
    ArchIssue,
    ArchLayer,
    HighRiskEntity,
    ModuleSummaryItem,
    RepositorySummaryData,
)
from app.services.graph import build_graph

logger = logging.getLogger(__name__)


def classify_architecture(files: list[File]) -> list[ArchLayer]:
    """Classify repository files into Presentation -> Business Logic -> Data Access layers."""
    presentation: list[str] = []
    business_logic: list[str] = []
    data_access: list[str] = []

    for f in files:
        p = f.path.replace("\\", "/")
        p_lower = p.lower()
        stem = Path(p).stem.lower()

        if "test" in p_lower or "conftest" in p_lower:
            continue

        if (
            stem in ("app", "main", "cli", "server", "views", "routes", "controller")
            or any(
                part in p_lower
                for part in ("api/", "routes/", "controllers/", "views/", "cli/")
            )
        ):
            presentation.append(f.path)
        elif (
            stem in ("database", "db", "dao", "models", "storage", "connection", "repository")
            or any(
                part in p_lower
                for part in ("db/", "models/", "dao/", "storage/", "repository/")
            )
        ):
            data_access.append(f.path)
        else:
            business_logic.append(f.path)

    layers: list[ArchLayer] = []
    if presentation:
        layers.append(ArchLayer(layer="Presentation", modules=sorted(presentation)))
    if business_logic:
        layers.append(ArchLayer(layer="Business Logic", modules=sorted(business_logic)))
    if data_access:
        layers.append(ArchLayer(layer="Data Access", modules=sorted(data_access)))

    return layers


def detect_architectural_issues(
    db: Session, repository: Repository
) -> list[ArchIssue]:
    """Derive architectural issues strictly from the knowledge graph and AST facts."""
    issues: list[ArchIssue] = []

    # 1. Circular dependencies
    graph_data = build_graph(db, repository)
    meta = graph_data.get("meta", {})
    circular_list = meta.get("circular_dependencies", []) if isinstance(meta, dict) else []
    for item in circular_list:
        if isinstance(item, dict):
            cycle = item.get("cycle", [])
            if isinstance(cycle, list) and len(cycle) >= 2:
                detail = " <-> ".join(str(c) for c in cycle)
                issues.append(
                    ArchIssue(
                        kind="circular_dependency",
                        detail=detail,
                        severity="high",
                    )
                )

    # 2. Global state usage
    global_vars: set[str] = set()
    for entity in repository.entities:
        if entity.metadata_json:
            g_used = entity.metadata_json.get("globals_used", [])
            for g in g_used:
                if isinstance(g, str) and not g.startswith("__"):
                    stem = Path(entity.file.path if entity.file else "module").stem
                    global_vars.add(f"{stem}.{g}")

    for g_var in sorted(global_vars)[:5]:
        issues.append(
            ArchIssue(
                kind="global_state",
                detail=g_var,
                severity="medium",
            )
        )

    # 3. High complexity / coupling
    for entity in repository.entities:
        if entity.complexity >= 8:
            mod_name = Path(entity.file.path if entity.file else "module").name
            detail = (
                f"{mod_name}.{entity.name} couples execution with high "
                f"complexity ({entity.complexity})"
            )
            issues.append(
                ArchIssue(
                    kind="coupling",
                    detail=detail,
                    severity="medium",
                )
            )
            if len(issues) >= 10:
                break

    return issues


def get_high_risk_entities(
    db: Session, repository: Repository
) -> list[HighRiskEntity]:
    """Extract top high-risk entities by complexity x degree from dependency graph."""
    graph_data = build_graph(db, repository)
    meta = graph_data.get("meta", {})
    high_risk_ids = set(meta.get("high_risk_node_ids", [])) if isinstance(meta, dict) else set()
    nodes_list = graph_data.get("nodes", [])
    nodes = nodes_list if isinstance(nodes_list, list) else []

    node_dict = {
        str(n["id"]): n
        for n in nodes
        if isinstance(n, dict) and n.get("type") in ("function", "method", "class")
    }

    edges_list = graph_data.get("edges", [])
    edges = edges_list if isinstance(edges_list, list) else []

    callers_count: dict[str, int] = {}
    for edge in edges:
        if isinstance(edge, dict) and edge.get("kind") == "call":
            target = str(edge.get("target"))
            callers_count[target] = callers_count.get(target, 0) + 1

    results: list[HighRiskEntity] = []
    for node_id in high_risk_ids:
        node_id_str = str(node_id)
        node = node_dict.get(node_id_str)
        if not node:
            continue
        complexity_val = node.get("complexity", 0)
        complexity_num = int(complexity_val) if isinstance(complexity_val, (int, float)) else 0
        file_val = str(node.get("file") or node_id_str.split("::")[0])
        label_val = str(node.get("label", node_id_str.split("::")[-1]))
        results.append(
            HighRiskEntity(
                name=label_val,
                file=file_val,
                complexity=complexity_num,
                callers=callers_count.get(node_id_str, 0),
            )
        )

    results.sort(key=lambda item: (-item.complexity, -item.callers, item.name))
    return results


def generate_repository_summary(
    db: Session, repository: Repository
) -> AnalysisSummaryPayload:
    """Generate repository overview, architecture classification, and issues."""
    layers = classify_architecture(repository.files)
    issues = detect_architectural_issues(db, repository)
    high_risk = get_high_risk_entities(db, repository)

    main_lang = (
        list(repository.languages.keys())[0] if repository.languages else "unknown"
    )
    module_names = [f.path for f in repository.files if "test" not in f.path.lower()]
    circular_str = (
        "\n".join(i.detail for i in issues if i.kind == "circular_dependency")
        or "None detected"
    )
    high_risk_str = (
        "\n".join(f"{h.name} ({h.file}, CCN={h.complexity})" for h in high_risk[:5])
        or "None"
    )
    global_str = (
        "\n".join(i.detail for i in issues if i.kind == "global_state") or "None"
    )

    graph_summary_str = (
        f"{len(module_names)} modules, {repository.entity_count} entities "
        f"across {len(layers)} architecture layers"
    )

    user_prompt = REPOSITORY_SUMMARY_USER.format(
        name=repository.name,
        language=main_lang,
        loc=repository.loc,
        entities=repository.entity_count,
        modules=", ".join(module_names),
        graph_summary=graph_summary_str,
        circular=circular_str,
        high_risk=high_risk_str,
        global_state=global_str,
    )
    system_prompt = secure_system_prompt(REPOSITORY_SUMMARY_SYSTEM)

    llm_gateway = get_llm_gateway()
    overview_text: str | None = None
    try:
        resp = llm_gateway.complete(prompt=user_prompt, system=system_prompt)
        overview_text = resp.content.strip()
    except Exception as exc:
        logger.info("LLM summary overview generation skipped/fallback: %s", exc)
        overview_text = (
            f"Repository {repository.name} consists of {repository.loc} LOC across "
            f"{len(repository.files)} files and {repository.entity_count} code entities."
        )

    summary_data = RepositorySummaryData(
        architecture=layers,
        issues=issues,
                overview=overview_text,
    )

    payload = AnalysisSummaryPayload(
        summary=summary_data,
        high_risk_entities=high_risk,
    )

    # Persist summary to the latest Analysis record (or create one)
    latest_analysis = (
        db.query(Analysis)
        .filter(Analysis.repository_id == repository.id)
        .order_by(Analysis.created_at.desc())
        .first()
    )
    if latest_analysis:
        latest_analysis.summary = payload.model_dump(by_alias=True)
    else:
        latest_analysis = Analysis(
            repository_id=repository.id,
            status="completed",
            summary=payload.model_dump(by_alias=True),
        )
        db.add(latest_analysis)
    db.commit()

    return payload


def generate_module_summaries(
    db: Session, repository: Repository
) -> list[ModuleSummaryItem]:
    """Generate per-module summaries for files in the repository."""
    items: list[ModuleSummaryItem] = []
    for file_row in repository.files:
        if "test" in file_row.path.lower() or "conftest" in file_row.path.lower():
            continue
        entity_names = [e.name for e in file_row.entities]
        summary_text = (
            f"Module {file_row.path} ({file_row.language}, {file_row.loc} LOC) contains "
            f"{len(entity_names)} entities: {', '.join(entity_names[:5])}."
        )
        items.append(
            ModuleSummaryItem(
                file=file_row.path,
                language=file_row.language,
                loc=file_row.loc,
                entity_count=len(file_row.entities),
                entities=entity_names,
                summary=summary_text,
            )
        )
    return items
