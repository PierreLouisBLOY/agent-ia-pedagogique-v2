"""R3 Application ownership: exact targets, CAP-A01 and atomic publication."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast

from backend.modules.pedagogical_design.application.commands.revise_assessment import (
    ReviseAssessmentCommand,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    as_plain,
    encoded,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    HARDEN,
    PREPARE,
    AssessmentRevisionRequest,
    EditorialCorrectionPlan,
)
from backend.modules.validation_control.application.commands.validate_assessment import (
    ValidateAssessmentCommand,
)
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    TARGETED_CHECK_REASON_CODES,
    AssessmentValidation,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialAuthorizationEvidence,
    EditorialValidationScope,
    build_editorial_scope,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import (
    R3Command,
    R3JobRequest,
    R3Rejected,
)
from backend.modules.work_orchestration.ports.outbound.r3_job import R3JobPort
from backend.modules.work_orchestration.ports.outbound.r3_store import R3Store

DIAGNOSTIC_STAGES = frozenset({
    "UNKNOWN", "LOCAL_POSTPROCESS_ENTRY", "PARSED_OUTPUT_MAPPING",
    "SUPPLEMENTS_DOMAIN_CONSTRUCTION", "BUNDLE_ASSEMBLY", "CANDIDATE_VIEW",
    "DETERMINISTIC_VALIDATION_CAP_A01", "VERSION_BINDING",
    "STORE_CAS_OR_IDEMPOTENCY", "ATOMIC_PUBLICATION", "POST_PROCESS_RECEIPT",
})
DIAGNOSTIC_CODES = frozenset({
    "NONE", "UNCLASSIFIED_LOCAL_FAILURE", "ASSESSMENT_FIELDS", "ASSESSMENT_SCHEMA",
    "ASSESSMENT_REFERENCE", "ASSESSMENT_CONTRACT", "ASSESSMENT_SECTIONS",
    "ASSESSMENT_SUBJECT_HASH", "ASSESSMENT_SIZE", "ASSESSMENT_LIMITATIONS",
    "ASSESSMENT_VALIDATION_FAILED", "ASSESSMENT_PUBLICATION_REJECTED",
    "REVISION_CONFLICT", "SESSION_CAPACITY_REACHED", "IDEMPOTENCY_CONFLICT",
    "GENERATION_IN_PROGRESS", "DEPENDENCY_CHANGE_REQUIRES_APPROVAL",
})
_DIAGNOSTIC_REASONS = frozenset({
    *TARGETED_CHECK_REASON_CODES,
    "CHECK_SATISFIED", "ASSESSMENT_BUNDLE_MISSING", "SEMANTIC_HUMAN_REVIEW_REQUIRED",
    *(f"A{i:02}_REJECTED" for i in range(1, 17)),
    *(f"A{i:02}_INVALID_OR_NON_EVALUABLE" for i in range(1, 17)),
})


def _failure_code(error: Exception) -> str:
    # Only exact known exception types and literal allowlisted args; never stringify.
    if type(error) in (ValueError, R3Rejected) and len(error.args) == 1:
        value = error.args[0]
        if type(value) is str and value in DIAGNOSTIC_CODES - {"NONE"}:
            return value
    return "UNCLASSIFIED_LOCAL_FAILURE"


@dataclass
class _ProcessingDiagnostic:
    operation_ref: str | None = None
    last_stage: str = "UNKNOWN"
    transitions: list[str] = field(default_factory=list)
    trace_complete: bool = True
    failure_stage: str = "UNKNOWN"
    failure_code: str = "NONE"
    cap_execution: str = "UNKNOWN"
    cap_overall: str = "UNKNOWN"
    checks: tuple[tuple[str, str, str], ...] = ()
    publication_state: str = "UNKNOWN"
    receipt_state: str = "UNKNOWN"
    receipt_failure_code: str = "NONE"

    def mark(self, stage: str) -> None:
        if type(stage) is not str or stage not in DIAGNOSTIC_STAGES:
            return
        self.last_stage = stage
        if not self.transitions or self.transitions[-1] != stage:
            if len(self.transitions) < 64:
                self.transitions.append(stage)
            else:
                self.trace_complete = False

    def failed(self, error: Exception) -> None:
        self.failure_code = _failure_code(error)
        self.failure_stage = self.last_stage
        if self.last_stage == "ATOMIC_PUBLICATION":
            # Categorize a closed store rejection; last_stage retains the actual call boundary.
            if self.failure_code in {"REVISION_CONFLICT", "IDEMPOTENCY_CONFLICT",
                                      "GENERATION_IN_PROGRESS", "SESSION_CAPACITY_REACHED"}:
                self.failure_stage = "STORE_CAS_OR_IDEMPOTENCY"
            elif self.failure_code == "ASSESSMENT_REFERENCE":
                self.failure_stage = "VERSION_BINDING"
            self.publication_state = "UNKNOWN"  # Exception alone does not prove rollback.

    def validated(self, result: AssessmentValidation) -> None:
        # No locators, expected/observed text, bundle or pedagogical content.
        if (tuple(c.check_id for c in result.checks) != tuple(f"A{i:02}" for i in range(1, 17))
                or any(type(c.status) is not str or c.status not in {"PASS", "WARNING", "FAIL"}
                       or type(c.reason_code) is not str
                       or c.reason_code not in _DIAGNOSTIC_REASONS for c in result.checks)):
            return
        self.cap_execution, self.cap_overall = "COMPLETED", result.overall_status
        self.checks = tuple((c.check_id, c.status, c.reason_code) for c in result.checks)

    def snapshot(self) -> dict[str, object]:
        return {
            "schema": "R3-LOCAL-PROCESSING-DIAGNOSTIC-1.0",
            "operation_ref": self.operation_ref, "last_stage": self.last_stage,
            "stage_transitions": list(self.transitions), "trace_complete": self.trace_complete,
            "failure_stage": self.failure_stage, "failure_code": self.failure_code,
            "cap_execution": self.cap_execution, "cap_overall": self.cap_overall,
            "checks": [{"check_id": i, "status": s, "reason_code": r} for i, s, r in self.checks],
            "publication_state": self.publication_state, "receipt_state": self.receipt_state,
            "receipt_failure_code": self.receipt_failure_code,
        }


class R3ReviewModifyService:
    def __init__(self, *, conversation_id: str, store: R3Store, jobs: R3JobPort,
                 ensure_session: Callable[[], object], clock: Callable[[], datetime],
                 new_id: Callable[[str], str],
                 editorial_plan: EditorialCorrectionPlan | None = None,
                 editorial_evidence: EditorialAuthorizationEvidence | None = None,
                 editorial_authenticate: Callable[[EditorialAuthorizationEvidence], bool] | None = None,
                 editorial_baseline: str | None = None, editorial_contract_sha256: str | None = None,
                 calculate_locators: Callable[[str, str, tuple[str, ...]], tuple[dict[str, object], ...]] | None = None,
                 restored_editorial_scope: EditorialValidationScope | None = None,
                 restored_authenticate: Callable[[EditorialValidationScope], bool] | None = None) -> None:
        self._id, self._store, self._jobs = conversation_id, store, jobs
        self._ensure, self._clock, self._new_id = ensure_session, clock, new_id
        self._active: tuple[R3Command, R3JobRequest, ProductionReadView] | None = None
        self._diagnostics: dict[str, _ProcessingDiagnostic] = {}
        self._editorial_plan, self._editorial_evidence = editorial_plan, editorial_evidence
        self._editorial_open = True
        self._calculate_locators = calculate_locators
        self._restored_scope = restored_editorial_scope
        self._restored_authenticate = restored_authenticate

        def authorized(evidence: EditorialAuthorizationEvidence) -> bool:
            try:
                return (self._editorial_open and evidence is self._editorial_evidence
                        and evidence.plan is self._editorial_plan
                        and evidence.baseline_commit == editorial_baseline
                        and evidence.contract_sha256 == editorial_contract_sha256
                        and evidence.conversation_id == self._id
                        and editorial_authenticate is not None
                        and editorial_authenticate(evidence) is True)
            except Exception:
                return False
        self._editorial_authorized = authorized

    def diagnostic(self, operation_ref: str) -> dict[str, object]:
        """Private composition readback only; never added to HTTP/business receipts."""
        return self._diagnostics.get(operation_ref, _ProcessingDiagnostic()).snapshot()

    def _trace(self, operation_ref: str) -> _ProcessingDiagnostic:
        trace = self._diagnostics.get(operation_ref)
        if trace is None:
            trace = _ProcessingDiagnostic(operation_ref)
            if len(self._diagnostics) >= 64:
                self._diagnostics.pop(next(iter(self._diagnostics)))
            self._diagnostics[operation_ref] = trace
        return trace

    def _production(self, production_ref: str, version_ref: str) -> ProductionReadView:
        self._ensure()
        view = self._store.read_version(conversation_id=self._id, production_ref=production_ref, version_ref=version_ref)
        if view is None:
            raise R3Rejected("PRODUCTION_VERSION_NOT_FOUND")
        return view

    def _validation(self, view: ProductionReadView, bundle: AssessmentBundle | None, *,
                    parent: AssessmentBundle | None = None,
                    editorial_scope: EditorialValidationScope | None = None) -> AssessmentValidation:
        if parent is None and bundle is not None:
            ref = object_data(bundle.data["lineage"]).get("parent_version_ref")
            if ref is not None:
                parent = self._store.r3_bundle(view.production_ref, str(ref))
        if (editorial_scope is None and bundle is not None
                and object_data(bundle.data["lineage"]).get("source_capability") is None):
            editorial_scope = self._store.r3_editorial_scope(view.production_ref, view.version_ref)
        if editorial_scope is not None:
            restored = False
            try:
                restored = (self._editorial_open and editorial_scope is self._restored_scope
                    and self._restored_authenticate is not None
                    and self._restored_authenticate(editorial_scope) is True)
            except Exception:
                restored = False
            if not restored and not self._editorial_authorized(editorial_scope.evidence):
                editorial_scope = None
        subject = {"content": view.data["content"], "sections": view.data["sections"]}
        return ValidateAssessmentCommand().execute(bundle, production_ref=view.production_ref,
            version_ref=view.version_ref, subject_sha256=fingerprint(subject),
            validation_ref=self._new_id("validation"), evaluated_at=self._clock().isoformat(),
            references=tuple(items(view.data["references"], 3)), parent=parent,
            editorial_scope=editorial_scope)

    def execute(self, command: R3Command) -> dict[str, object]:
        self._ensure()
        if command.body["conversation_id"] != self._id:
            raise R3Rejected("CONVERSATION_NOT_FOUND")
        replay = self._store.r3_receipt(command)
        if replay is not None:
            return replay
        view = self._production(str(command.body["production_ref"]), command.version_ref)
        session = self._store.read(self._id)
        if session is None or session.view.get("confirmed_context_sha256") != view.data["context_sha256"]:
            raise R3Rejected("CONTEXT_NOT_CONFIRMED")
        bundle = self._store.r3_bundle(view.production_ref, view.version_ref)
        subject = {"content": view.data["content"], "sections": view.data["sections"]}
        if command.operation == "assessment-preparations":
            if bundle is not None:
                raise R3Rejected("ASSESSMENT_ALREADY_PRESENT")
            if command.body["subject_sha256"] != fingerprint(subject):
                raise R3Rejected("ASSESSMENT_REFERENCE")
        else:
            expected = command.body.get("base_bundle_sha256", command.body.get("bundle_sha256"))
            if expected != (bundle.sha256 if bundle else None):
                raise R3Rejected("ASSESSMENT_REFERENCE")
            if command.operation != "validations" and bundle is None:
                raise R3Rejected("ASSESSMENT_BUNDLE_MISSING")
        editorial = (command.operation == "modifications"
                     and command.body["operation"] == EditorialCorrectionPlan.OPERATION)
        if editorial:
            plan, evidence = self._editorial_plan, self._editorial_evidence
            if (plan is None or evidence is None or bundle is None
                    or self._calculate_locators is None or not self._editorial_authorized(evidence)):
                raise R3Rejected("R3_NOT_AUTHORIZED")
            if (command.body["plan_sha256"] != plan.sha256
                    or command.body["review_sha256"] != plan.data["review_sha256"]):
                raise R3Rejected("ASSESSMENT_REFERENCE")
            plan.validate_parent(bundle)
            review = self._store.r3_report(str(evidence.review.get("review_ref")), review=True)
            if encoded(review) != encoded(evidence.review):
                raise R3Rejected("ASSESSMENT_REFERENCE")
        if command.operation == "modifications" and self._validation(view, bundle).overall_status == "FAIL":
            raise R3Rejected("ASSESSMENT_VALIDATION_FAILED")
        operation_ref = self._new_id("op")
        if command.operation == "validations":
            result = self._validation(view, bundle)
            self._store.r3_reserve(command, operation_ref)
            self._store.r3_complete(operation_ref, {"state": "SUCCEEDED", "validation": result.as_dict()},
                                    validation=result)
            return self._store.r3_report(operation_ref)
        if editorial:
            # No job creation, authorize/start/poll or provider operation on this path.
            assert plan is not None and evidence is not None and bundle is not None
            assert self._calculate_locators is not None
            reserved = self._store.r3_reserve(command, operation_ref)
            if reserved["operation_ref"] != operation_ref:
                return reserved
            trace = self._trace(operation_ref)
            try:
                trace.mark("BUNDLE_ASSEMBLY")
                lineage: dict[str, object] = {
                    "operation_ref": operation_ref, "command_id": command.command_id,
                    "source_capability": None, "parent_version_ref": bundle.version_ref,
                    "parent_bundle_sha256": bundle.sha256, "instruction_sha256": plan.sha256,
                    "changed_locators": list(plan.PATHS), "dependency_changes": [],
                }
                child = ReviseAssessmentCommand().execute_editorial(plan, bundle,
                    version_ref=self._new_id("ver"), lineage=lineage,
                    calculate_locators=self._calculate_locators)
                scope = build_editorial_scope(evidence, bundle, child,
                    command_id=command.command_id, operation_ref=operation_ref,
                    authenticate=self._editorial_authorized, calculate_locators=self._calculate_locators)
                data = object_data(as_plain(view.data))
                data["version_ref"] = child.version_ref
                candidate = ProductionReadView(view.production_ref, child.version_ref, self._id, data)
                trace.mark("DETERMINISTIC_VALIDATION_CAP_A01")
                trace.cap_execution, trace.cap_overall = "STARTED", "UNKNOWN"
                validation = self._validation(candidate, child, parent=bundle, editorial_scope=scope)
                trace.validated(validation)
                if validation.overall_status == "FAIL":
                    raise R3Rejected("ASSESSMENT_VALIDATION_FAILED")
                trace.mark("ATOMIC_PUBLICATION")
                trace.publication_state = "STARTED"
                self._store.r3_complete(operation_ref, {"state": "SUCCEEDED",
                    "bundle_sha256": child.sha256, "review_status": "REVIEW_NOT_RUN",
                    "validation_status": validation.overall_status},
                    production=candidate, bundle=child, validation=validation, editorial_scope=scope)
                trace.publication_state = "PUBLISHED"
                trace.receipt_state = "WRITTEN"
            except Exception as error:
                trace.failed(error)
                # An exception after commit must never overwrite a completed effect.
                existing = self._store.r3_report(operation_ref)
                if existing["state"] == "RUNNING":
                    self._store.r3_complete(operation_ref, {"state": "FAILED_OUTPUT",
                        "error_code": "ASSESSMENT_PUBLICATION_REJECTED"})
                trace.receipt_state = "WRITTEN"
            return self._store.r3_report(operation_ref)
        revision = None
        if command.operation != "reviews":
            revision = AssessmentRevisionRequest(HARDEN if command.operation == "modifications" else PREPARE,
                view.production_ref, view.version_ref, subject, object_data(view.data["pedagogical_context"]),
                tuple(items(view.data["references"], 3)), bundle if command.operation == "modifications" else None)
        from backend.modules.work_orchestration.contracts.dto.operation_identity import (
            OperationIdentity,
        )

        job = R3JobRequest(operation_ref, command.operation, revision, bundle,
                          tuple(cast(tuple[str, ...], command.body.get("dimensions", ()))),
                          OperationIdentity(operation_ref, "step:" + operation_ref.split(":", 1)[1],
                                            None, self._id))
        self._jobs.authorize(job)
        trace = self._trace(operation_ref)
        trace.mark("STORE_CAS_OR_IDEMPOTENCY")
        try:
            reserved = self._store.r3_reserve(command, operation_ref)
        except Exception as error:
            trace.failed(error)
            raise
        if reserved["operation_ref"] != operation_ref:
            return reserved
        self._active = (command, job, view)
        try:
            self._jobs.start(job)
        except Exception:
            self._store.r3_complete(operation_ref, {"state": "FAILED_NO_EFFECT", "error_code": "JOB_UNAVAILABLE"})
            self._active = None
        return self._store.r3_report(operation_ref)

    def poll(self) -> None:
        if self._active is None:
            return
        command, request, original = self._active
        try:
            result = self._jobs.poll()
        except Exception:
            self._store.r3_complete(request.operation_ref, {"state": "UNKNOWN", "error_code": "JOB_UNAVAILABLE"})
            self._active = None
            return
        if result is None:
            return
        self._active = None
        if result.operation_ref != request.operation_ref:
            self._store.r3_complete(request.operation_ref, {"state": "UNKNOWN", "error_code": "APPLICATION_FAILURE"})
            return
        trace = self._trace(request.operation_ref)
        if result.state != "SUCCEEDED" or result.payload is None:
            # Upstream supplied no local output or failure-stage evidence.
            trace.cap_execution, trace.cap_overall = "NOT_RUN", "NOT_RUN"
            self._store.r3_complete(request.operation_ref, {"state": result.state})
            trace.mark("POST_PROCESS_RECEIPT")
            trace.receipt_state = "WRITTEN"
            return
        trace.mark("LOCAL_POSTPROCESS_ENTRY")
        trace.cap_execution, trace.cap_overall = "NOT_RUN", "NOT_RUN"
        trace.publication_state = "NOT_RUN"
        try:
            self._ensure()
            if request.operation == "reviews":
                self._publish_review(request, result.payload)
                return
            if request.revision is None:
                raise R3Rejected("APPLICATION_FAILURE")
            version = self._new_id("ver") if command.operation == "modifications" else original.version_ref
            base = request.revision.base
            lineage: dict[str, object] = {"operation_ref": request.operation_ref, "command_id": command.command_id,
                "source_capability": "CAP-G02", "parent_version_ref": base.version_ref if base else None,
                "parent_bundle_sha256": base.sha256 if base else None,
                "instruction_sha256": fingerprint({"instruction": command.body.get("instruction", PREPARE)}),
                "changed_locators": ["DOSSIER_3"] if base else [], "dependency_changes": []}
            bundle = ReviseAssessmentCommand().execute(request.revision, result.payload,
                version_ref=version, lineage=lineage, observe=trace.mark)
            trace.mark("CANDIDATE_VIEW")
            data = object_data(as_plain(original.data))
            subject = object_data(bundle.data["subject"])
            data.update(version_ref=version, content=subject["content"], sections=subject["sections"])
            candidate = ProductionReadView(original.production_ref, version, self._id, data)
            trace.mark("DETERMINISTIC_VALIDATION_CAP_A01")
            trace.cap_execution, trace.cap_overall = "STARTED", "UNKNOWN"
            validation = self._validation(candidate, bundle, parent=base)
            trace.validated(validation)
            if validation.overall_status == "FAIL":
                raise R3Rejected("ASSESSMENT_VALIDATION_FAILED")
            trace.mark("ATOMIC_PUBLICATION")
            trace.publication_state = "STARTED"
            self._store.r3_complete(request.operation_ref, {"state": "SUCCEEDED",
                "bundle_sha256": bundle.sha256, "review_status": "REVIEW_NOT_RUN",
                "validation_status": validation.overall_status},
                production=candidate if base else None, bundle=bundle, validation=validation)
            trace.publication_state = "PUBLISHED"
            trace.mark("POST_PROCESS_RECEIPT")
            trace.receipt_state = "WRITTEN"
        except Exception as error:
            trace.failed(error)
            dependency_refusal = (
                command.operation == "modifications" and request.revision is not None
                and request.revision.operation == HARDEN and trace.last_stage == "BUNDLE_ASSEMBLY"
                and type(error) is ValueError and len(error.args) == 1
                and type(error.args[0]) is str
                and error.args[0] == "DEPENDENCY_CHANGE_REQUIRES_APPROVAL")
            trace.mark("POST_PROCESS_RECEIPT")
            try:
                self._store.r3_complete(request.operation_ref, {"state": "FAILED_OUTPUT",
                    "error_code": ("DEPENDENCY_CHANGE_REQUIRES_APPROVAL" if dependency_refusal
                                   else "ASSESSMENT_PUBLICATION_REJECTED")})
                trace.receipt_state = "WRITTEN"
            except Exception as receipt_error:
                trace.receipt_state = "UNKNOWN"
                trace.receipt_failure_code = _failure_code(receipt_error)
                raise

    def _publish_review(self, request: R3JobRequest, payload: Mapping[str, object]) -> None:
        bundle = request.bundle
        data = object_data(payload, {"status", "production_ref", "version_ref", "subject_sha256",
            "bundle_sha256", "findings", "overall_assessment", "coverage", "limitations",
            "evidence_refs_used", "created_at"})
        if (bundle is None or data["status"] not in {"completed", "incomplete"}
                or (data["production_ref"], data["version_ref"], data["bundle_sha256"]) !=
                (bundle.production_ref, bundle.version_ref, bundle.sha256)
                or data["subject_sha256"] != bundle.data["subject_sha256"]):
            raise R3Rejected("ASSESSMENT_REFERENCE")
        if len(encoded(data)) > 32 * 1024 or len(items(data["findings"], 32)) > 32:
            raise R3Rejected("REQUEST_TOO_LARGE")
        data.update(review_ref="review:" + request.operation_ref.split(":")[1], operation_ref=request.operation_ref)
        self._store.r3_complete(request.operation_ref, {"state": "SUCCEEDED"}, review=data)

    def assessment(self, production_ref: str, version_ref: str) -> dict[str, object]:
        self._production(production_ref, version_ref)
        return self._store.r3_snapshot(production_ref, version_ref)

    def report(self, reference: str, *, review: bool = False) -> dict[str, object]:
        self._ensure()
        return self._store.r3_report(reference, review=review)

    def close(self) -> None:
        self._editorial_open = False
        self._restored_scope = self._restored_authenticate = None
        self._editorial_plan = self._editorial_evidence = None
        self._calculate_locators = None
        self._jobs.close()
        if self._active is not None:
            self._store.r3_complete(self._active[1].operation_ref, {"state": "UNKNOWN"})
            self._active = None
        self._store.r3_clear()
        self._diagnostics.clear()
