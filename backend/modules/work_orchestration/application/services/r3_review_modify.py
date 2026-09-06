"""R3 Application ownership: exact targets, CAP-A01 and atomic publication."""
from collections.abc import Callable, Mapping
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
)
from backend.modules.validation_control.application.commands.validate_assessment import (
    ValidateAssessmentCommand,
)
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    AssessmentValidation,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import (
    R3Command,
    R3JobRequest,
    R3Rejected,
)
from backend.modules.work_orchestration.ports.outbound.r3_job import R3JobPort
from backend.modules.work_orchestration.ports.outbound.r3_store import R3Store


class R3ReviewModifyService:
    def __init__(self, *, conversation_id: str, store: R3Store, jobs: R3JobPort,
                 ensure_session: Callable[[], object], clock: Callable[[], datetime],
                 new_id: Callable[[str], str]) -> None:
        self._id, self._store, self._jobs = conversation_id, store, jobs
        self._ensure, self._clock, self._new_id = ensure_session, clock, new_id
        self._active: tuple[R3Command, R3JobRequest, ProductionReadView] | None = None

    def _production(self, production_ref: str, version_ref: str) -> ProductionReadView:
        self._ensure()
        view = self._store.read_version(conversation_id=self._id, production_ref=production_ref, version_ref=version_ref)
        if view is None:
            raise R3Rejected("PRODUCTION_VERSION_NOT_FOUND")
        return view

    def _validation(self, view: ProductionReadView, bundle: AssessmentBundle | None, *,
                    parent: AssessmentBundle | None = None) -> AssessmentValidation:
        if parent is None and bundle is not None:
            ref = object_data(bundle.data["lineage"]).get("parent_version_ref")
            if ref is not None:
                parent = self._store.r3_bundle(view.production_ref, str(ref))
        subject = {"content": view.data["content"], "sections": view.data["sections"]}
        return ValidateAssessmentCommand().execute(bundle, production_ref=view.production_ref,
            version_ref=view.version_ref, subject_sha256=fingerprint(subject),
            validation_ref=self._new_id("validation"), evaluated_at=self._clock().isoformat(),
            references=tuple(items(view.data["references"], 3)), parent=parent)

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
        if command.operation == "modifications" and self._validation(view, bundle).overall_status == "FAIL":
            raise R3Rejected("ASSESSMENT_VALIDATION_FAILED")
        operation_ref = self._new_id("op")
        if command.operation == "validations":
            result = self._validation(view, bundle)
            self._store.r3_reserve(command, operation_ref)
            self._store.r3_complete(operation_ref, {"state": "SUCCEEDED", "validation": result.as_dict()},
                                    validation=result)
            return self._store.r3_report(operation_ref)
        revision = None
        if command.operation != "reviews":
            revision = AssessmentRevisionRequest(HARDEN if command.operation == "modifications" else PREPARE,
                view.production_ref, view.version_ref, subject, object_data(view.data["pedagogical_context"]),
                tuple(items(view.data["references"], 3)), bundle if command.operation == "modifications" else None)
        job = R3JobRequest(operation_ref, command.operation, revision, bundle,
                          tuple(cast(tuple[str, ...], command.body.get("dimensions", ()))))
        self._jobs.authorize(job)
        reserved = self._store.r3_reserve(command, operation_ref)
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
        if result.state != "SUCCEEDED" or result.payload is None:
            self._store.r3_complete(request.operation_ref, {"state": result.state})
            return
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
                                                       version_ref=version, lineage=lineage)
            data = object_data(as_plain(original.data))
            subject = object_data(bundle.data["subject"])
            data.update(version_ref=version, content=subject["content"], sections=subject["sections"])
            candidate = ProductionReadView(original.production_ref, version, self._id, data)
            validation = self._validation(candidate, bundle, parent=base)
            if validation.overall_status == "FAIL":
                raise R3Rejected("ASSESSMENT_VALIDATION_FAILED")
            self._store.r3_complete(request.operation_ref, {"state": "SUCCEEDED",
                "bundle_sha256": bundle.sha256, "review_status": "REVIEW_NOT_RUN",
                "validation_status": validation.overall_status},
                production=candidate if base else None, bundle=bundle, validation=validation)
        except Exception:
            self._store.r3_complete(request.operation_ref, {"state": "FAILED_OUTPUT",
                                                          "error_code": "ASSESSMENT_PUBLICATION_REJECTED"})

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
        self._jobs.close()
        if self._active is not None:
            self._store.r3_complete(self._active[1].operation_ref, {"state": "UNKNOWN"})
            self._active = None
        self._store.r3_clear()
