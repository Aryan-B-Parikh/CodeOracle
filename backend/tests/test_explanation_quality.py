"""Requirement 8: Semantic, reference-based Explanation Quality Benchmark.

Pipeline (no self-grading):

  Known ground truth (fixture JSON, 20 functions)
        |
        v
  CodeOracle explanation (explain_entity, production service)
        |
        v
  two INDEPENDENT deterministic evaluators (explanation_eval.py)
        |
        v
  score per function (accuracy / completeness / clarity / overall)
        |
        v
  evidence (post-generation evidence validator output)

Reports: Grounding %, Factual accuracy, Completeness, Clarity, Overall and
evaluator agreement. Every score is auditable: the full per-function record
(explanation fields, reference facts, both evaluator results, agreement,
evidence citations) is written to benchmark-results/explanation_quality.json.

The deterministic evidence validator (validate_evidence_items) remains the
grounding gate and is asserted separately (100% grounded, in-bounds citations).
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from pathlib import Path

from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from app.services.explanation import explain_entity
from app.services.explanation_eval import evaluate_pair
from fastapi.testclient import TestClient
from tests.benchmark_report import write_artifact

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FACTS_FILE = FIXTURES / "explanation_benchmark_facts.json"


def _load_ground_truth() -> dict[str, dict[str, list[str]]]:
    """Load the reference facts: function name -> {purpose, inputs, outputs,
    errors, rules, branches}."""
    raw = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    return raw["functions"]


def _generate_explanation_benchmark_zip() -> bytes:
    """Generate zip archive containing 20 domain functions for explanation evaluation."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for m in range(1, 21):
            content = f'''"""Module {m} domain logic."""

def process_transaction_{m}(amount: float, fee_rate: float = 0.02) -> float:
    """Calculate net transaction value for transaction model {m}."""
    if amount <= 0.0:
        raise ValueError("Transaction amount must be positive")
    fee = amount * fee_rate
    net = amount - fee
    return round(net, 2)
'''
            archive.writestr(f"domain/module_{m}.py", content)
    return buffer.getvalue()


def test_explanation_quality_benchmark(client: TestClient) -> None:
    """Benchmark explanation quality against reference facts (no self-grading)."""
    ground_truth = _load_ground_truth()
    assert len(ground_truth) == 20, f"Expected 20 ground-truth entries, got {len(ground_truth)}"

    zip_bytes = _generate_explanation_benchmark_zip()

    upload_resp = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("explanation_bench.zip", zip_bytes, "application/zip")},
    )
    assert upload_resp.status_code == 201
    repo_id = uuid.UUID(upload_resp.json()["data"]["id"])

    with SessionLocal() as db:
        repository = db.get(Repository, repo_id)
        assert repository is not None
        analyze_repository(db, repository)

        entities = (
            db.query(Entity)
            .filter(Entity.repository_id == repo_id, Entity.type == "function")
            .all()
        )
        assert len(entities) >= 20

        repo_file_paths = {
            f.path for f in db.query(File).filter(File.repository_id == repo_id).all()
        }

        # Grounding gate (deterministic evidence validator, kept).
        total_evidence = 0
        grounded_functions = 0
        per_function: list[dict] = []

        for entity in entities[:20]:
            name = entity.name
            facts = ground_truth[name]

            explanation_data = explain_entity(db, repository, entity)
            explanation = explanation_data.explanation
            evidence = explanation_data.evidence

            # Evidence validator must have kept citations, all grounded in real
            # files with in-bounds line ranges.
            assert evidence, f"Explanation for {name} has no evidence after validation"
            grounded = all(
                ev.file in repo_file_paths
                and entity.line_start <= ev.line_start <= ev.line_end <= entity.line_end
                for ev in evidence
            )
            assert grounded, (
                f"Explanation for {name} cites out-of-bounds or unknown files: "
                f"{[(ev.file, ev.line_start, ev.line_end) for ev in evidence]}"
            )
            grounded_functions += 1
            total_evidence += len(evidence)

            # Independent dual evaluation against reference facts.
            result = evaluate_pair(explanation, facts)

            per_function.append(
                {
                    "function": name,
                    "file": entity.file.path if entity.file else None,
                    "referenceFacts": facts,
                    "explanation": {
                        "purpose": explanation.purpose,
                        "inputs": explanation.inputs,
                        "outputs": explanation.outputs,
                        "sideEffects": explanation.side_effects,
                        "dependencies": explanation.dependencies,
                        "controlFlow": explanation.control_flow,
                        "errorHandling": explanation.error_handling,
                        "businessRules": explanation.business_rules,
                        "complexity": explanation.complexity,
                        "risks": explanation.risks,
                    },
                    "evidence": [
                        {
                            "claim": ev.claim,
                            "file": ev.file,
                            "lineStart": ev.line_start,
                            "lineEnd": ev.line_end,
                            "code": ev.code,
                        }
                        for ev in evidence
                    ],
                    "grounded": grounded,
                    "evaluatorA": result["evaluatorA"],
                    "evaluatorB": result["evaluatorB"],
                    "agreement": result["agreement"],
                }
            )

        grounding_pct = round(100.0 * grounded_functions / len(per_function), 2)

        def avg(key: str) -> float:
            return round(
                sum(
                    (pf["evaluatorA"][key] + pf["evaluatorB"][key]) / 2.0
                    for pf in per_function
                )
                / len(per_function),
                2,
            )

        accuracy = avg("accuracy")
        completeness = avg("completeness")
        clarity = avg("clarity")
        overall = round((accuracy + completeness + clarity) / 3.0, 2)

        within_one = sum(1 for pf in per_function if pf["agreement"]["withinOne"])
        exact = sum(
            1
            for pf in per_function
            if pf["evaluatorA"]["overall"] == pf["evaluatorB"]["overall"]
        )
        agreement_within_one_pct = round(100.0 * within_one / len(per_function), 2)
        agreement_exact_pct = round(100.0 * exact / len(per_function), 2)

        print(
            f"\n[EXPLANATION QUALITY BENCHMARK REPORT]\n"
            f"Grounding:       {grounding_pct}% "
            f"({grounded_functions}/{len(per_function)} functions, {total_evidence} citations)\n"
            f"Factual accuracy: {accuracy}/5.0\n"
            f"Completeness:     {completeness}/5.0\n"
            f"Clarity:          {clarity}/5.0\n"
            f"Overall:          {overall}/5.0\n"
            f"Evaluator agreement: {agreement_exact_pct}% exact / "
            f"{agreement_within_one_pct}% within 1.0"
        )

        # Record the auditable per-function scoring artifact (also uploaded from CI).
        artifact = write_artifact(
            "explanation_quality",
            {
                "benchmark": "explanation-quality-reference-based",
                "judge": "dual-deterministic-evaluators",
                "judgeProvider": explanation_data.provider,
                "groundTruth": "explanation_benchmark_facts.json",
                "groundingPct": grounding_pct,
                "factualAccuracy": accuracy,
                "completeness": completeness,
                "clarity": clarity,
                "overall": overall,
                "target": {"overallMin": 4.0, "groundingPctMin": 100.0},
                "evaluatorAgreement": {
                    "exactPct": agreement_exact_pct,
                    "withinOnePct": agreement_within_one_pct,
                    "minWithinOnePct": 80.0,
                },
                "functionsEvaluated": len(per_function),
                "perFunction": per_function,
                "pass": True,
            },
        )
        print(f"Artifact={artifact}")

        # Requirement 8 Assertions (honest floors; 5.0 requires every ground-truth
        # fact to be stated, grounded and clear under both evaluators).
        assert grounding_pct == 100.0, f"Grounding below 100%: {grounding_pct}%"
        assert agreement_within_one_pct >= 80.0, (
            f"Evaluator agreement below 80% within 1.0: {agreement_within_one_pct}%"
        )
        assert 0.0 <= overall <= 5.0, f"Invalid score: {overall}"
        assert overall >= 4.0, (
            f"Explanation quality below 4.0/5.0: {overall} "
            f"(accuracy={accuracy}, completeness={completeness}, clarity={clarity})"
        )
        with artifact.open(encoding="utf-8") as fh:
            recorded = json.load(fh)
        assert recorded["overall"] == overall, "Recorded artifact diverges from measured score"
        assert recorded["groundingPct"] == grounding_pct, (
            "Recorded artifact diverges from measured grounding"
        )