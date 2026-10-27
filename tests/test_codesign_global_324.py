"""Real native plans/agents/Application, synthetic ports; never a live profile."""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

import pytest

from backend.adapters.outbound.evidence.p0_active_application import (
    ApplicationEvidenceSearch,
    CoDesignEvidenceSources,
)
from backend.adapters.outbound.evidence.p0_prepared_snapshot import PreparedEvidenceSnapshot
from backend.adapters.outbound.generation.openai.p0_content import bind_p0_content
from backend.adapters.outbound.generation.p0_codesign_agents import CoDesignGenerator
from backend.adapters.outbound.generation.p0_codesign_runtime import NativeCoDesign
from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.agents.evidence.evidence_agent import EvidenceAgent
from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    RetrievalCoordinationPolicy,
)
from backend.agent_runtime.agents.evidence.retrieval_coordinator import RetrievalCoordinator
from backend.agent_runtime.agents.evidence.retrieval_model import RetrievalChannel
from backend.agent_runtime.agents.generation import GenerationPortResult, GenerationPortResultStatus
from backend.agent_runtime.agents.review import ReviewPortResult, ReviewPortResultStatus
from backend.agent_runtime.contracts import BudgetSpec
from backend.agent_runtime.runtime.execution.prelaunch import (
    PreLaunchDecision,
    PreLaunchDisposition,
)
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0_PROVENANCE_LABEL
from backend.modules.resource_library.application.dto.output.local_search_view import (
    LocalSearchItem,
    LocalSearchView,
    SearchOpenStatus,
)
from backend.modules.resource_library.ports.outbound.local_search import AdmittedLocalPassage
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService

LEVELS = ("FIRST_STMG", "FINAL_STMG", "BTS_CG_YEAR_1", "BTS_CG_YEAR_2")
FAMILIES = ("COURSE", "EXERCISE", "ASSESSMENT", "OPEN_QUESTIONS", "QCM", "QUIZ")


def simple(family="EXERCISE", level="FIRST_STMG"):
    qset = family in {"OPEN_QUESTIONS", "QCM", "QUIZ"}
    context = P0Context(
        {
            "contract_id": "R6-P0-CONTEXT-1.0",
            "resource_type": "QUESTION_SET" if qset else family,
            "question_mode": family if qset else None,
            "level": level,
            "discipline": "Gestion",
            "topics": ["Perception"],
            "objectives": ["Distinguer un fait d'une interprétation"],
            "difficulty": "STANDARD",
            "language": "fr",
            "duration_minutes": 30 if family == "ASSESSMENT" else None,
            "total_points": 20 if family == "ASSESSMENT" else None,
        }
    )
    text = "Une perception est une interprétation d'informations."
    ref = {
        "evidence_id": "evidence:" + "b" * 32,
        "source_ref": "notion:perception",
        "locator": "chunk:perception",
        "checksum_or_version": "1" * 64,
        "excerpt_sha256": sha256(text.encode()).hexdigest(),
        "provenance_label": P0_PROVENANCE_LABEL,
    }
    dispatch = {
        "contract_id": "R6-P0-DISPATCH-1.0",
        "context": context.as_dict(),
        "context_sha256": context.sha256,
        "production_ref": "prod:" + "b" * 32,
        "version_ref": "ver:" + "b" * 32,
        "references": [ref],
        "evidence": {ref["evidence_id"]: text},
        "lineage": {
            "source_run_id": "run:" + "b" * 32,
            "source_step_id": "step:" + "b" * 32,
            "evidence_set_ref": ref["evidence_id"],
            "source_request_id": "req:" + "b" * 32,
            "conversation_id": "conv:" + "b" * 32,
            "context_sha256": context.sha256,
            "parent_version_ref": None,
        },
    }
    content = {
        "title": "Perception",
        "sections": [
            {
                "section_id": "S1",
                "heading": "Situation",
                "text": "Situation fictive : un message est interprété.",
            }
        ],
        "questions": []
        if family == "COURSE"
        else [
            {
                "question_id": "Q1",
                "prompt": "Distinguez un fait.",
                "options": ["Le message", "Le jugement"] if family in {"QCM", "QUIZ"} else [],
            }
        ],
        "corrections": []
        if family == "COURSE"
        else [
            {
                "question_id": "Q1",
                "expected_answer": "Le message",
                "rationale": "C'est le fait observé.",
            }
        ],
        "marking": [{"question_id": "Q1", "points": "20.00", "criteria": ["Distinction justifiée"]}]
        if family == "ASSESSMENT"
        else [],
        "limitations": [
            "CANDIDATE — qualification synthétique ; acceptation enseignante non effectuée."
        ],
    }
    return dispatch, content


class Search:
    def search_local(self, *, request, correlation_id):
        row = AdmittedLocalPassage(
            "notion:perception",
            "NOTION",
            "chunk:perception",
            "1" * 64,
            "Une perception est une interprétation d'informations.",
            False,
        )
        return ApplicationOutcome(
            outcome_status=OutcomeStatus.SUCCESS,
            success=True,
            correlation_id=correlation_id,
            data=LocalSearchView(
                (LocalSearchItem(1, row, None, SearchOpenStatus.NOT_RESOURCE),), False, False
            ),
        )


class Generation:
    def __init__(self, content):
        self.content, self.calls = content, []

    def generate(self, *, request):
        self.calls.append(request)
        proposed = deepcopy(self.content)
        proposed["title"] = (
            "Perception : justifier les interprétations"
            if request.operation.value == "CORRECT"
            else "Perception : distinguer les faits et les interprétations"
        )
        details = (
            {
                "addressed_findings": tuple(request.constraints["finding_ids"]),
                "unresolved_findings": (),
                "change_summary": "Clarification synthétique du contenu, sans changement de contexte.",
            }
            if request.operation.value == "CORRECT"
            else {}
        )
        return GenerationPortResult(
            request.source_step_id,
            request.operation,
            GenerationPortResultStatus.SUCCEEDED,
            structured_payload=proposed,
            evidence_refs_used=request.evidence_refs,
            operation_details=details,
        )


class Review:
    def __init__(self, correction=False):
        self.calls, self.correction = [], correction

    def review(self, *, request):
        self.calls.append(request)
        needs = self.correction and len(self.calls) == 1
        findings = (
            (
                {
                    "finding_id": "finding-1",
                    "dimension": "REV-PED",
                    "severity": "minor",
                    "description": "Préciser le titre",
                    "target_locator": {"kind": "json_path", "path": ["title"]},
                    "rationale": "Une clarification locale est utile.",
                    "correction_required": True,
                    "evidence_refs": [],
                    "confidence": {},
                    "suggested_action": {},
                },
            )
            if needs
            else ()
        )
        return ReviewPortResult(
            request.source_step_id,
            request.operation,
            ReviewPortResultStatus.SUCCEEDED,
            structured_payload={
                "overall_assessment": "correction_required" if needs else "acceptable",
                "correction_required": needs,
                "coverage": [d.value for d in request.review_dimensions],
                "confidence": {},
            },
            technical_findings=findings,
            evidence_refs_used=request.evidence_refs,
        )


class Guard:
    def __init__(self, allow=True):
        self.allow = allow

    def check(self, **kwargs):
        return (
            PreLaunchDecision(PreLaunchDisposition.ALLOW)
            if self.allow
            else PreLaunchDecision(PreLaunchDisposition.DENY, "SYNTHETIC_DENY")
        )


def composition(dispatch, content, *, authority=True, allow=True, correction=False):
    from backend.shared_kernel.correlation import CorrelationId

    active = ApplicationEvidenceSearch(Search(), CorrelationId("synthetic-324"))
    sources = CoDesignEvidenceSources(PreparedEvidenceSnapshot(dispatch, datetime.now(UTC)), active)
    channels = (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL)
    evidence = EvidenceAgent(
        RetrievalCoordinator(
            sources, RetrievalCoordinationPolicy(channels, channels, 8, 8, 60), sources
        ),
        sources,
    )
    generator, reviewer = Generation(content), Review(correction)
    runtime = NativeCoDesign(
        generator=CoDesignGenerator(generator),
        reviewer=P0ReviewAdapter(reviewer, authorize=lambda _: authority),
        evidence=evidence,
        guard=Guard(allow),
        envelope=BudgetSpec(max_retries=0, max_cost=Decimal("1.00")),
        chain_authorize=lambda _: authority,
        permission_scope_ref="scope:synthetic-324",
    )
    service = P0CreationService(lambda _: {}, codesign=runtime)
    service._receive_generated(
        dispatch, bind_p0_content(dispatch, content).mutable_copy(), recovered=False
    )
    return service, generator, reviewer


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("direction", ("V2_TO_AI", "AI_TO_V2"))
def test_all_legacy_families_native_chain(family, level, direction):
    dispatch, content = simple(family, level)
    service, generator, reviewer = composition(dispatch, content)
    parent = service.records[dispatch["version_ref"]]
    body = {
        "command_id": "a" * 32,
        "production_ref": parent.production_ref,
        "version_ref": parent.version_ref,
        "bundle_sha256": parent.sha256,
        "direction": direction,
        "evidence_query": None,
        "objective": "Clarifier la perception",
    }
    result = service.execute("codesign", body)
    assert result["state"] == "CODESIGN_CANDIDATE"
    assert result["view"]["title"] != parent.data["title"]
    assert service.records[parent.version_ref].sha256 == parent.sha256
    assert len(generator.calls) == len(reviewer.calls) == 1
    assert generator.calls[0].operation.value == (
        "TRANSFORM" if direction == "V2_TO_AI" else "GENERATE"
    )
    assert len(result["trace"]["retrieval"]) == 1
    assert result["trace"]["runs"][0]["workflow_kind"] == "WF-6"
    final = result["view"]
    record = service.saved_source(final["production_ref"], final["version_ref"])
    assert record.p0_bundle.data["lineage"]["parent_version_ref"] == parent.version_ref
    assert service.execute("codesign", body) == result
    assert len(generator.calls) == len(reviewer.calls) == 1


@pytest.mark.parametrize("authority,allow", ((False, True), (True, False)))
def test_missing_authority_or_guard_never_generates(authority, allow):
    dispatch, content = simple()
    service, generator, reviewer = composition(dispatch, content, authority=authority, allow=allow)
    parent = service.records[dispatch["version_ref"]]
    body = {
        "command_id": "a" * 32,
        "production_ref": parent.production_ref,
        "version_ref": parent.version_ref,
        "bundle_sha256": parent.sha256,
        "direction": "V2_TO_AI",
        "evidence_query": None,
        "objective": "Clarifier",
    }
    result = service.execute("codesign", body)
    assert result["state"] in {"AUTHORIZATION_REQUIRED", "BLOCKED"}
    assert generator.calls == reviewer.calls == []


def test_correction_uses_a_separate_native_run_and_fresh_review():
    dispatch, content = simple()
    service, generator, reviewer = composition(dispatch, content, correction=True)
    parent = service.records[dispatch["version_ref"]]
    result = service.execute(
        "codesign",
        {
            "command_id": "a" * 32,
            "production_ref": parent.production_ref,
            "version_ref": parent.version_ref,
            "bundle_sha256": parent.sha256,
            "direction": "V2_TO_AI",
            "evidence_query": None,
            "objective": "Clarifier",
        },
    )
    assert len(generator.calls) == len(reviewer.calls) == 2
    assert generator.calls[-1].operation.value == "CORRECT"
    first, second = result["trace"]["runs"]
    assert first["workflow_kind"] == "WF-6" and second["workflow_kind"] == "WF-7"
    assert first["run_id"] == second["parent_run_id"]
    assert reviewer.calls[0].target_production_ref != reviewer.calls[1].target_production_ref
    assert result["pedagogical_acceptance"] == "NOT_PERFORMED"
