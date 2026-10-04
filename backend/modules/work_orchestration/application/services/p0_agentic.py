"""Application-owned effort/working-memory projections, without agent authority."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    items,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

PLAN_CONTRACT = "P0-AGENTIC-PLAN-1.0"
PACK_CONTRACT = "P0-EVIDENCE-PACK-1.0"


def effort_plan(context: P0Context) -> dict[str, object]:
    data = context.as_dict()
    topics = data["topics"]
    assert isinstance(topics, list)
    quantitative = any(word in " ".join(topics).casefold() for word in (
        "calcul", "bfr", "frng", "trésorerie", "coût", "seuil", "amortissement", "lettrage", "proportion"))
    if data["resource_type"] == "ASSESSMENT" or quantitative:
        effort = "HAUT_RISQUE_PEDAGOGIQUE"
    elif data["difficulty"] == "ADVANCED" or len(topics) > 2:
        effort = "COMPLEXE"
    elif data["difficulty"] == "INTRODUCTORY" and data["resource_type"] == "COURSE" and len(topics) == 1:
        effort = "SIMPLE"
    else:
        effort = "STANDARD"
    return {"contract_id": PLAN_CONTRACT, "intent": "PREPARE_PEDAGOGICAL_PRODUCTION",
        "context_sha256": context.sha256, "level": data["level"],
        "family": data["question_mode"] or data["resource_type"], "duration_minutes": data["duration_minutes"],
        "difficulty": data["difficulty"], "total_points": data["total_points"], "topics": topics,
        "objectives": data["objectives"], "effort": effort, "quantitative_review_required": quantitative,
        "retrieval": {"max_passages": {"SIMPLE": 1, "STANDARD": 3, "COMPLEXE": 6, "HAUT_RISQUE_PEDAGOGIQUE": 8}[effort],
                      "mode": "EXACT_APPLICATION_SELECTION", "automatic_expansion": False},
        "review_required": effort != "SIMPLE", "validations": ["SCHEMA", "DEPENDENCIES", "REFERENCE_HASHES", "LINEAGE"]
            + (["INDEPENDENT_CALCULATION_ORACLE_REQUIRED"] if quantitative else []),
        "subtasks": [{"role": "AG-01", "task": "PLAN"}, {"role": "AG-02", "task": "BOUNDED_EVIDENCE"},
                     {"role": "AG-03", "task": "STRUCTURED_PRODUCTION"}, {"role": "AG-04", "task": "INDEPENDENT_REVIEW"}],
        "budget": {"generation_max": 1, "review_max": 1, "targeted_correction_max": 1,
                   "retry": 0, "fallback": "NONE", "authority": "OWNER_GATE_REQUIRED"},
        "ambiguities": [], "implementation": "DETERMINISTIC_APPLICATION_PLAN", "authority": "NONE"}


def evidence_pack(context: P0Context, references: object, evidence: Mapping[str, object]) -> dict[str, object]:
    refs = items(references, 8)
    if not refs or set(evidence) != {str(r["evidence_id"]) for r in refs}:
        raise ValueError("P0_EVIDENCE_PACK_SCOPE")
    passages: list[dict[str, object]] = []
    for reference in refs:
        text = evidence[str(reference["evidence_id"])]
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise ValueError("P0_EVIDENCE_PACK_SIZE")
        if hashlib.sha256(text.encode()).hexdigest() != reference["excerpt_sha256"]:
            raise ValueError("P0_EVIDENCE_PACK_HASH")
        passages.append({**object_data(as_plain(reference)), "text": text})
    pack = {"contract_id": PACK_CONTRACT, "context_sha256": context.sha256, "level": context.as_dict()["level"],
        "notion_refs": [], "passages": passages, "scope": "SELECTED_PASSAGES_ONLY",
        "date": None, "date_status": "NOT_AVAILABLE_IN_REFERENCE_CONTRACT", "authority": "NONE",
        "limits": ["No official authority inferred", "Selection does not establish full topic coverage"],
        "content_gaps": ["SEMANTIC_COVERAGE_NOT_YET_REVIEWED"], "source_status": "SOURCES_OK",
        "source_status_scope": "IDENTITY_AND_HASH_INTEGRITY_ONLY"}
    if len(encoded(pack)) > 32 * 1024:
        raise ValueError("P0_EVIDENCE_PACK_SIZE")
    return object_data(as_plain(freeze_safe_mapping(pack)))


def quality_status(plan: Mapping[str, object], *, review: Mapping[str, object] | None = None) -> dict[str, object]:
    # Structural success is neither an arithmetic proof nor semantic coverage.
    return {"sources": "SOURCES_OK", "source_scope": "SELECTED_REFERENCE_HASHES",
        "calculations": "ECHEC" if plan["quantitative_review_required"] else "NON_APPLICABLE",
        "calculation_reason": "INDEPENDENT_ORACLE_NOT_EXECUTED" if plan["quantitative_review_required"] else "NO_QUANTITATIVE_TOPIC_DECLARED",
        "instruction": "CONSIGNE_COUVERTE" if review and review.get("instruction_coverage") == "FULL" else "PARTIELLE",
        "review": "REVUE_OK" if review and review.get("status") == "completed" and review.get("overall_assessment") == "acceptable"
            and not review.get("limitations") else "RESERVE", "human_review": "HUMAN_REVIEW_REQUIRED"}
