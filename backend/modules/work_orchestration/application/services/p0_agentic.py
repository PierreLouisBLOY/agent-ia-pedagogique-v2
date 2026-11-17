"""Application-owned effort/working-memory projections, without agent authority."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.program_authority import (
    alignment_axes,
    authority_layers,
)
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    AssessmentValidation,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

PLAN_CONTRACT = "P0-AGENTIC-PLAN-1.1"
PACK_CONTRACT = "P0-EVIDENCE-PACK-1.0"


def _normalized(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def _without_context_dates(text: str) -> str:
    normalized = _normalized(text)
    if re.search(r"\d\s*[+*=−]\s*[-+]?\d", normalized):
        return normalized
    # A date is contextual data, not an arithmetic operation or measured result.
    normalized = re.sub(r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b", "", normalized)
    normalized = re.sub(r"\b\d{1,2}\s+(?:janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+\d{4}\b", "", normalized)
    return re.sub(r"\b(?:en|depuis|annee|le)\s+(?:19|20)\d{2}\b", "", normalized)


def _quantitative_signal(text: str) -> bool:
    normalized = _without_context_dates(text)
    # Operations and measured outputs; keywords are a supplementary conservative signal.
    operation = re.search(r"\b(?:calcul\w*|determiner|trouver|estimer|deduire|evaluer|quel montant)\b", normalized)
    measure = re.search(r"\b(?:tva|taxe|van|valeur actu\w*|resultat net|benefice|recette\w*|depense\w*|taux|montant|pourcent\w*|chiffre d.affaires|charges|flux)\b", normalized)
    expression = re.search(r"\d[\d .,]*\s*[+*/=−-]\s*\d", normalized)
    units = re.search(r"\d[\d .,]*\s*(?:%|€|euros?\b|usd\b|keur\b)", normalized)
    keywords = re.search(r"\b(?:calcul\w*|bfr|frng|tresorerie|cout\w*|seuil|amortissement|lettrage|proportion\w*)\b", normalized)
    # Counting/comparing measured quantities is quantitative beyond financial units.
    quantity = re.search(r"\b(?:nombre|quantite\w*|effectif\w*|volume\w*|duree\w*|distance\w*|masse\w*|population\w*|capacite\w*)\b", normalized)
    comparison = re.search(r"\b(?:variation\w*|difference\w*|ecart\w*|augmentation\w*|diminution\w*|evolution\w*)\b", normalized)
    count_question = re.search(r"\bcombien\b", normalized)
    return bool((operation and (measure or quantity)) or (comparison and quantity)
        or count_question or expression or units or keywords
        or re.search(r"\b(?:total|totaux|somme|addition\w*|soustra\w*|multipl\w*|divis\w*|cumul\w*|moyenne\w*)\b", normalized))


def _declared_applicability(data: Mapping[str, object]) -> dict[str, str]:
    objectives = data.get("objectives", ())
    topics = data.get("topics", ())
    texts = [str(value) for values in (topics, objectives) if isinstance(values, (list, tuple)) for value in values]
    if any(_quantitative_signal(text) for text in texts):
        return {"status": "REQUIRED", "reason": "REQUESTED_QUANTITATIVE_OPERATION_OR_DATA"}
    qualitative = isinstance(objectives, (list, tuple)) and bool(objectives) and all(
        re.match(r"^(?:identifier|distinguer|decrire|expliquer|presenter|justifier|caracteriser)\b", _normalized(str(text)))
        for text in objectives)
    if qualitative:
        return {"status": "NOT_REQUIRED", "reason": "EXPLICIT_QUALITATIVE_OBJECTIVES"}
    return {"status": "UNDETERMINED", "reason": "APPLICABILITY_NOT_ESTABLISHED"}


def _production_requires_control(value: object, *, field: str = "") -> bool:
    if isinstance(value, Mapping):
        return any((key in {"calculations", "expression", "computed", "totals", "numeric_data", "calculation_steps"} and bool(item))
            or _production_requires_control(item, field=str(key))
            for key, item in value.items()
            if key not in {"context", "lineage", "references", "marking", "media_assets"} and not str(key).endswith(("_id", "_ref", "_sha256")))
    if isinstance(value, (tuple, list)):
        return any(_production_requires_control(item, field=field) for item in value)
    if isinstance(value, str):
        numeric_answer = field == "expected_answer" and re.search(
            r"(?<!\w)[-+]?\d+(?:[.,]\d+)?(?!\w)", _without_context_dates(value)) is not None
        return numeric_answer or _quantitative_signal(value)
    return type(value) in {int, float} and field in {
        "amount", "quantity", "rate", "result", "expected_answer", "unit_price", "subtotal", "total", "balance"}


def _production_has_unresolved_quantity(value: object, *, field: str = "") -> bool:
    if isinstance(value, Mapping):
        return any(_production_has_unresolved_quantity(item, field=str(key))
            for key, item in value.items()
            if key not in {"context", "lineage", "references", "marking", "media_assets"}
            and not str(key).endswith(("_id", "_ref", "_sha256")))
    if isinstance(value, (tuple, list)):
        return any(_production_has_unresolved_quantity(item, field=field) for item in value)
    if isinstance(value, str):
        # An isolated contextual year cannot establish a calculation; other
        # quantities without an operation cannot establish non-applicability.
        text = _without_context_dates(value)
        return re.search(r"(?<!\w)[-+]?\d+(?:[.,]\d+)?(?!\w)", text) is not None
    return type(value) in {int, float} and field in {"amount", "quantity", "rate", "result", "total"}


def effort_plan(context: P0Context, *, production: Mapping[str, object] | None = None) -> dict[str, object]:
    data = context.as_dict()
    topics = data["topics"]
    assert isinstance(topics, list)
    objectives = data["objectives"]
    assert isinstance(objectives, list)
    applicability = _declared_applicability(data)
    if production is not None and _production_requires_control(production):
        applicability = {"status": "REQUIRED", "reason": "PRODUCTION_QUANTITATIVE_OPERATION_OR_DATA"}
    elif production is not None and applicability["status"] != "REQUIRED" and _production_has_unresolved_quantity(production):
        applicability = {"status": "UNDETERMINED", "reason": "PRODUCTION_QUANTITY_OPERATION_UNRESOLVED"}
    quantitative = applicability["status"] == "REQUIRED"
    if data["resource_type"] == "ASSESSMENT" or quantitative:
        effort = "HAUT_RISQUE_PEDAGOGIQUE"
    elif data["difficulty"] == "ADVANCED" or len(topics) > 2:
        effort = "COMPLEXE"
    elif data["difficulty"] == "INTRODUCTORY" and data["resource_type"] == "COURSE" and len(topics) == 1:
        effort = "SIMPLE"
    else:
        effort = "STANDARD"
    plan: dict[str, object] = {"contract_id": PLAN_CONTRACT, "intent": "PREPARE_PEDAGOGICAL_PRODUCTION",
        "context_sha256": context.sha256, "level": data["level"],
        "family": data["question_mode"] or data["resource_type"], "duration_minutes": data["duration_minutes"],
        "difficulty": data["difficulty"], "total_points": data["total_points"], "topics": topics,
        "objectives": data["objectives"], "effort": effort, "quantitative_review_required": quantitative,
        "calculation_applicability": applicability,
        "retrieval": {"max_passages": {"SIMPLE": 1, "STANDARD": 3, "COMPLEXE": 6, "HAUT_RISQUE_PEDAGOGIQUE": 8}[effort],
                      "mode": "EXACT_APPLICATION_SELECTION", "automatic_expansion": False},
        "review_required": effort != "SIMPLE", "validations": ["SCHEMA", "DEPENDENCIES", "REFERENCE_HASHES", "LINEAGE"]
            + (["INDEPENDENT_CALCULATION_ORACLE_REQUIRED"] if quantitative else []),
        "subtasks": [{"role": "AG-01", "task": "PLAN"}, {"role": "AG-02", "task": "BOUNDED_EVIDENCE"},
                     {"role": "AG-03", "task": "STRUCTURED_PRODUCTION"}, {"role": "AG-04", "task": "INDEPENDENT_REVIEW"}],
        "budget": {"generation_max": 1, "review_max": 1, "targeted_correction_max": 1,
                   "retry": 0, "fallback": "NONE", "authority": "OWNER_GATE_REQUIRED"},
        "ambiguities": [], "implementation": "DETERMINISTIC_APPLICATION_PLAN", "authority": "NONE"}
    if context.institutional is not None:
        plan["institutional"] = data["institutional"]
        plan["institutional_resolution"] = data["institutional_resolution"]
        if data["resource_type"] == "COURSE":
            from backend.modules.pedagogical_design.contracts.dto.course_policy import (
                course_policy_for,
            )

            plan["course_policy"] = course_policy_for(context)
        plan["institutional_validation"] = "EXACT_PROGRAMME_ALIGNMENT"
        plan["review_axes"] = alignment_axes(data["institutional_resolution"])
    return plan


def evidence_pack(context: P0Context, references: object, evidence: Mapping[str, object]) -> dict[str, object]:
    refs = items(references, 8)
    identifiers = [str(reference["evidence_id"]) for reference in refs]
    # The declared effort controls retrieval before output exists. A generation
    # cannot silently expand the selected input pack beyond that Application plan.
    retrieval = object_data(effort_plan(context)["retrieval"])
    if (not refs or len(refs) > int(str(retrieval["max_passages"]))
            or len(identifiers) != len(set(identifiers))
            or set(evidence) != set(identifiers)):
        raise ValueError("P0_EVIDENCE_PACK_SCOPE")
    passages: list[dict[str, object]] = []
    for reference in refs:
        text = evidence[str(reference["evidence_id"])]
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise ValueError("P0_EVIDENCE_PACK_SIZE")
        if hashlib.sha256(text.encode()).hexdigest() != reference["excerpt_sha256"]:
            raise ValueError("P0_EVIDENCE_PACK_HASH")
        passages.append({**object_data(as_plain(reference)), "text": text})
    pack: dict[str, object] = {"contract_id": PACK_CONTRACT, "context_sha256": context.sha256, "level": context.as_dict()["level"],
        "notion_refs": [], "passages": passages, "scope": "SELECTED_PASSAGES_ONLY",
        "date": None, "date_status": "NOT_AVAILABLE_IN_REFERENCE_CONTRACT", "authority": "NONE",
        "limits": ["No official authority inferred", "Selection does not establish full topic coverage"],
        "content_gaps": ["SEMANTIC_COVERAGE_NOT_YET_REVIEWED"], "source_status": "SOURCES_OK",
        "source_status_scope": "IDENTITY_AND_HASH_INTEGRITY_ONLY"}
    if context.institutional is not None:
        resolution = object_data(context.data["institutional_resolution"])
        pack["institutional_selection"] = context.institutional
        pack["institutional_resolution"] = resolution
        pack["notion_refs"] = context.institutional["notion_refs"]
        pack["content_gaps"] = resolution["gaps"]
        pack["source_status"] = "SOURCES_INSUFFISANTES" if resolution["gaps"] else "SOURCES_OK"
        pack["source_status_scope"] = "EXACT_PROGRAMME_AND_SELECTED_REFERENCE"
        from backend.modules.pedagogical_context.contracts.dto.real_course_thread import (
            thread_from_context,
        )
        from backend.modules.pedagogical_design.contracts.dto.program_authority import (
            bounded_institutional_evidence,
        )
        from backend.modules.resource_library.contracts.dto.documentary_course_thread import (
            DOCUMENTARY_THREAD,
        )

        thread = thread_from_context(context.data)
        if thread is not None and thread.data["contract_id"] == DOCUMENTARY_THREAD:
            # Keep the complete, validated proof in immutable Application context.
            # Working memory commits it by hash and reuses the existing content-only view.
            pack["institutional_resolution"] = bounded_institutional_evidence(resolution)
            pack["documentary_selection"] = {**thread.summary(),
                "archive_sha256": thread.data["archive_sha256"], "snapshot_sha256": thread.data["snapshot_sha256"],
                "document_ids": [d["id"] for d in items(thread.data["documents"], 6)],
                "full_resolution_sha256": fingerprint(resolution)}
    if len(encoded(pack)) > 32 * 1024:
        raise ValueError("P0_EVIDENCE_PACK_SIZE")
    if context.institutional is not None:
        layers = authority_layers(context.data["institutional_resolution"], passages, context.data.get("local_progression"))
        if "documentary_selection" in pack and layers["institutional_evidence"]:
            # Admission was evaluated above on the full resolution, never on its projection.
            layers["institutional_evidence"] = [pack["institutional_resolution"]]
        pack.update(layers)
        if len(encoded(pack)) > 32 * 1024:
            raise ValueError("P0_EVIDENCE_PACK_SIZE")
    return object_data(as_plain(freeze_safe_mapping(pack)))


def quality_status(plan: Mapping[str, object], *, review: Mapping[str, object] | None = None,
                   production: Mapping[str, object] | None = None,
                   calculation_control: AssessmentValidation | None = None) -> dict[str, object]:
    if production is not None:
        if ("context_sha256" in plan and ("context_sha256" in production or "production_ref" in production)
                and plan["context_sha256"] != production.get("context_sha256")):
            raise ValueError("P0_QUALITY_CONTEXT_BINDING")
        if review is not None and (
                review.get("production_ref"), review.get("version_ref"), review.get("bundle_sha256")) != (
                production.get("production_ref"), production.get("version_ref"), fingerprint(production)):
            raise ValueError("P0_QUALITY_REVIEW_BINDING")
    # Structural success is neither an arithmetic proof nor semantic coverage.
    resolution = plan.get("institutional_resolution")
    gap = resolution is not None and object_data(resolution)["status"] != "RESOLVED_ADMITTED"
    required = bool(plan["quantitative_review_required"]) or (production is not None and _production_requires_control(production))
    applicability = plan.get("calculation_applicability", {})
    justified = isinstance(applicability, Mapping) and applicability.get("status") == "NOT_REQUIRED" and applicability.get("reason") == "EXPLICIT_QUALITATIVE_OBJECTIVES"
    if production is not None and _production_has_unresolved_quantity(production):
        justified = False
    calculations = "ECHEC" if required else "NON_APPLICABLE" if justified else "A_DETERMINER"
    reason = "INDEPENDENT_ORACLE_NOT_EXECUTED" if required else "EXPLICIT_QUALITATIVE_OBJECTIVES" if justified else "APPLICABILITY_NOT_ESTABLISHED"
    if calculation_control is not None:
        if (type(calculation_control) is not AssessmentValidation or production is None
                or (production.get("production_ref"), production.get("version_ref"), fingerprint(production))
                != (calculation_control.production_ref, calculation_control.version_ref, calculation_control.bundle_sha256)):
            raise ValueError("CALCULATION_CONTROL_BINDING")
        passed = calculation_control.overall_status == "PASS" and calculation_control.checks[14].status == "PASS"
        calculations = "CALCULS_VERIFIES" if passed else "ECHEC"
        reason = "R3_A15_BOUND_ORACLE_EXECUTED" if passed else "INDEPENDENT_ORACLE_REJECTED"
    return {"sources": "SOURCES_INSUFFISANTES" if gap else "SOURCES_OK", "source_scope": "SELECTED_REFERENCE_HASHES",
        "calculations": calculations, "calculation_reason": reason,
        "instruction": "CONSIGNE_COUVERTE" if review and review.get("instruction_coverage") == "FULL" else "PARTIELLE",
        "review": "REVUE_OK" if review and review.get("status") == "completed" and review.get("overall_assessment") == "acceptable"
            and review.get("correction_required") is False
            and not review.get("limitations") and not review.get("uncertainties")
            else "RESERVE", "human_review": "HUMAN_REVIEW_REQUIRED"}
