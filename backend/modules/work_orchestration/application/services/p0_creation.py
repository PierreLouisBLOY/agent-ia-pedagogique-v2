"""One P0 lifecycle, reusing the R6 commands; no provider, SQL or storage access."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from secrets import token_hex

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
    ReviseP0Candidate,
    ReviseSavedP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    identifier,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.ports.outbound.p0_confirmed_recovery import (
    P0ConfirmedGenerationRecoveryPort,
)
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.pedagogical_design.ports.outbound.p0_generation_controls import (
    P0GenerationControlsPort,
)
from backend.modules.quality_evaluation.contracts.dto.p0_review_report import (
    validate_p0_review_fields,
)
from backend.modules.quality_evaluation.ports.outbound.p0_review import P0ReviewPort
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.application.services.p0_agentic import (
    effort_plan,
    evidence_pack,
    quality_status,
)
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_P0_CONTRACT,
    SavedProduction,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping


class P0CreationService:
    def __init__(self, reference: Callable[[Mapping[str, object]], Mapping[str, object]],
                 *, generation: P0GenerationPort | None = None, review: P0ReviewPort | None = None,
                 institutional_resolver: Callable[[Mapping[str, object], Mapping[str, object]], Mapping[str, object]] | None = None,
                 exact_stmg_required: bool = False, exact_institutional_required: bool = False) -> None:
        self.reference = reference
        self.generation = generation
        self.review = review
        self.institutional_resolver = institutional_resolver
        self.exact_stmg_required = exact_stmg_required
        self.exact_institutional_required = exact_institutional_required
        self.prepared: dict[str, Mapping[str, object]] = {}
        self.records: dict[str, P0Production] = {}
        self.evidence: dict[str, dict[str, str]] = {}
        self.commands: dict[str, tuple[str, dict[str, object]]] = {}
        self.plans: dict[str, dict[str, object]] = {}
        self.packs: dict[str, dict[str, object]] = {}
        self.reports: dict[str, dict[str, object]] = {}
        self.validations: dict[str, dict[str, object]] = {}
        self.review_consumed: set[str] = set()
        self.correction_consumed: set[str] = set()
        self.saved_reader: Callable[[str, str], SavedProduction] | None = None
        self.resumed: dict[str, SavedProduction] = {}
        self.local_reopened: set[str] = set()
        self.publish_generated: Callable[[str, str, str], Mapping[str, object]] | None = None
        self.generation_controls: dict[str, dict[str, object]] = {}

    def execute(self, operation: str, body: Mapping[str, object]) -> dict[str, object]:
        fields = {
            "prepare": {"command_id", "context", "reference"},
            "generate": {"command_id", "preparation_ref", "preparation_sha256"},
            "revise": {"command_id", "production_ref", "version_ref", "bundle_sha256", "edits"},
            "validate": {"command_id", "production_ref", "version_ref", "bundle_sha256"},
            "review": {"command_id", "production_ref", "version_ref", "bundle_sha256"},
            "correct": {"command_id", "production_ref", "version_ref", "bundle_sha256", "review_sha256", "edits"},
        }
        if operation not in fields:
            raise ValueError("P0_REQUEST_REJECTED")
        data = object_data(body, fields[operation])
        command = data["command_id"]
        if not isinstance(command, str) or len(command) != 32 or any(c not in "0123456789abcdef" for c in command):
            raise ValueError("P0_COMMAND_ID")
        identity = fingerprint({"operation": operation, "body": data})
        prior = self.commands.get(command)
        if prior:
            if prior[0] != identity:
                raise ValueError("P0_IDEMPOTENCY_CONFLICT")
            return object_data(as_plain(prior[1]))
        if len(self.commands) >= 256:
            raise ValueError("P0_SESSION_FULL")
        # Consumed before any boundary invocation. An uncertain outcome cannot replay.
        self.commands[command] = (identity, {"state": "OUTCOME_UNKNOWN", "retry": 0})
        try:
            result = getattr(self, "_" + operation)(data)
        except ValueError as error:
            self.commands[command] = (identity, {"state": "REFUSED", "code": str(error)})
            raise
        except Exception:
            # Never expose infrastructure exception text or retry a dispatch.
            raise ValueError("P0_OUTCOME_UNKNOWN") from None
        self.commands[command] = (identity, result)
        return object_data(as_plain(result))

    def _prepare(self, data: dict[str, object]) -> dict[str, object]:
        if len(self.prepared) >= 64:
            raise ValueError("P0_SESSION_FULL")
        context = P0Context(object_data(data["context"]))
        selection = object_data(data["reference"])
        if context.institutional is not None:
            if self.institutional_resolver is None:
                raise ValueError("P0_INSTITUTIONAL_RESOLVER_REQUIRED")
            resolved = object_data(self.institutional_resolver(context.institutional, selection))
            if object_data(resolved.get("reference_scope", {})).get("status") == "CONTENT_GAP":
                # Do not hand unscoped contextual content to planning/retrieval agents.
                raise ValueError("P0_INSTITUTIONAL_SOURCE_CONTEXT_GAP")
            confirmed = context.as_dict()
            confirmed["institutional_resolution"] = resolved
            context = P0Context(confirmed)
        elif self.exact_institutional_required or (self.exact_stmg_required and str(context.data["level"]).endswith("STMG")):
            raise ValueError("P0_INSTITUTIONAL_CONTEXT_REQUIRED")
        loaded = self.reference(selection)
        reference = object_data(loaded["reference"])
        if context.data.get("institutional_resolution") is not None:
            scope = object_data(object_data(context.data["institutional_resolution"]).get("reference_scope", {}))
            if scope and any(scope.get(key) != reference.get(target) for key, target in (
                    ("object_ref", "source_ref"), ("passage_ref", "locator"), ("version_or_checksum", "checksum_or_version"))):
                raise ValueError("P0_INSTITUTIONAL_REFERENCE_CHANGED")
        excerpt = loaded["excerpt"]
        if not isinstance(excerpt, str) or not excerpt:
            raise ValueError("P0_EVIDENCE_INSUFFICIENT")
        ref = "prep:" + token_hex(16)
        request = {
            "contract_id": "R6-P0-DISPATCH-1.0", "context": context.as_dict(),
            "context_sha256": context.sha256, "references": [reference],
            "evidence": {str(reference["evidence_id"]): excerpt},
            "production_ref": "prod:" + token_hex(16), "version_ref": "ver:" + token_hex(16),
            "lineage": {"source_run_id": "run:" + token_hex(16), "source_step_id": "step:" + token_hex(16),
                "evidence_set_ref": "evidence:" + token_hex(16), "source_request_id": "req:" + token_hex(16),
                "conversation_id": "conv:" + token_hex(16), "context_sha256": context.sha256,
                "parent_version_ref": None},
        }
        plan = effort_plan(context)
        pack = evidence_pack(context, request["references"], object_data(request["evidence"]))
        self.prepared[ref] = freeze_safe_mapping(request)
        self.plans[str(request["version_ref"])], self.packs[str(request["version_ref"])] = plan, pack
        return {"state": "PREPARATION_READY", "authorization": "REQUIRED",
                "preparation_ref": ref, "preparation_sha256": fingerprint(request),
                "context": context.as_dict(), "references": [reference], "provider_attempts": 0,
                "agentic": {"plan": plan, "evidence_pack": pack, "quality": quality_status(plan)}}

    def _generate(self, data: dict[str, object]) -> dict[str, object]:
        request = self.prepared.get(str(data["preparation_ref"]))
        if request is None or fingerprint(request) != data["preparation_sha256"]:
            raise ValueError("P0_PREPARATION_CHANGED")
        context = P0Context(object_data(request["context"]))
        if context.institutional is not None or self.exact_institutional_required or (self.exact_stmg_required and str(context.data["level"]).endswith("STMG")):
            context.require_institutional_dispatch()
        if self.generation is None or not self.generation.authorize(request=request):
            return {"state": "AUTHORIZATION_REQUIRED", "provider_attempts": 0}
        # Remove the preparation before the single permitted dispatch, including failure.
        del self.prepared[str(data["preparation_ref"])]
        output = self.generation.generate(request=request)
        return self._receive_generated(request, output, recovered=False)

    def recover_confirmed_generation(self, request: Mapping[str, object]) -> Mapping[str, object]:
        """Read a captured effect; never authorize, reserve or dispatch it again."""
        if not isinstance(self.generation, P0ConfirmedGenerationRecoveryPort):
            raise ValueError("P0_CONFIRMED_RECOVERY_UNAVAILABLE")
        if self.publish_generated is None or self.saved_reader is None:
            raise ValueError("P0_CONFIRMED_RECOVERY_PUBLICATION_REQUIRED")
        output = self.generation.recover_confirmed(request=request)
        result = self._receive_generated(request, output, recovered=True)
        version = str(request["version_ref"])
        record = self.saved_reader(str(request["production_ref"]), version)
        candidate = self.records[version]
        if record.p0_bundle is None or record.p0_bundle.sha256 != candidate.sha256:
            raise ValueError("P0_CONFIRMED_RECOVERY_PUBLICATION_BINDING")
        self.resumed[version] = record
        self.local_reopened.add(version)
        result["agentic"] = self._memory(candidate)
        return result

    def _receive_generated(self, request: Mapping[str, object], output: Mapping[str, object],
                           *, recovered: bool) -> dict[str, object]:
        context = P0Context(object_data(request["context"]))
        if context.institutional is not None or self.exact_institutional_required:
            context.require_institutional_dispatch()
        evidence = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        candidate = CreateP0Candidate().execute(output, evidence=evidence)
        if context.institutional is not None and context.resource_type == "COURSE" and "course_chapter" not in candidate.data:
            from backend.modules.pedagogical_design.contracts.dto.course_policy import (
                validate_course_structure,
            )

            validate_course_structure(candidate.data["sections"])
        for key in ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage"):
            if as_plain(candidate.data[key]) != as_plain(request[key]):
                raise ValueError("P0_OUTPUT_BINDING")
        controls = None
        if isinstance(self.generation, P0GenerationControlsPort):
            controls = object_data(self.generation.control_evidence(request=request, bundle_sha256=candidate.sha256),
                {"contract_id", "production_ref", "version_ref", "context_sha256", "bundle_sha256",
                 "guard_disposition", "guard_warnings", "provided_evidence_refs", "declared_evidence_refs_used",
                 "source_usage_declaration", "source_status", "review_state"})
            if (any(controls[key] != value for key, value in (
                    ("contract_id", "P0-GENERATION-CONTROLS-1.0"),
                    ("production_ref", candidate.production_ref), ("version_ref", candidate.version_ref),
                    ("context_sha256", candidate.context.sha256), ("bundle_sha256", candidate.sha256),
                    ("source_usage_declaration", "NOT_IN_OUTPUT_SCHEMA"), ("source_status", "RESERVE"),
                    ("review_state", "NOT_RUN")))
                    or controls["guard_disposition"] not in {"ALLOW", "ALLOW_WITH_WARNINGS"}
                    or as_plain(controls["declared_evidence_refs_used"]) != []
                    or as_plain(controls["provided_evidence_refs"]) != list(evidence)):
                raise ValueError("P0_GENERATION_CONTROLS_BINDING")
            for warning in items(controls["guard_warnings"], 16):
                object_data(warning, {"code", "location"})
                if any(not isinstance(value, str) or not 1 <= len(value) <= 160
                       for value in warning.values()):
                    raise ValueError("P0_GENERATION_CONTROLS_BINDING")
            controls = object_data(as_plain(controls))
        prior = self.records.get(candidate.version_ref)
        if prior is not None and prior.sha256 != candidate.sha256:
            raise ValueError("P0_SAVED_VERSION_CONFLICT")
        if prior is None and len(self.records) >= 256:
            raise ValueError("P0_SESSION_FULL")
        self.records[candidate.version_ref] = candidate
        if controls is not None:
            self.generation_controls[candidate.version_ref] = controls
        self.evidence[candidate.version_ref] = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        self.plans[candidate.version_ref] = effort_plan(context, production=candidate.data)
        self.packs[candidate.version_ref] = evidence_pack(context, request["references"], evidence)
        self._validate({"production_ref": candidate.production_ref, "version_ref": candidate.version_ref})
        publication = None
        if self.publish_generated is not None:
            publication = object_data(self.publish_generated(candidate.production_ref,
                candidate.version_ref, candidate.sha256),
                {"state", "production_ref", "version_ref", "bundle_sha256", "record_sha256"})
            if (publication["state"] != "APPLICATION_SAVED"
                    or any(publication[key] != expected for key, expected in (
                        ("production_ref", candidate.production_ref),
                        ("version_ref", candidate.version_ref), ("bundle_sha256", candidate.sha256)))
                    or not isinstance(publication["record_sha256"], str)
                    or len(publication["record_sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in publication["record_sha256"])):
                raise ValueError("P0_GENERATED_PUBLICATION_BINDING")
        return {"state": "CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
                "provider_attempts": 0 if recovered else 1, "retry": 0,
                "recovery": "CONFIRMED_LOCAL_RESULT" if recovered else "NOT_PERFORMED",
                "promotion": "NOT_PERFORMED", "publication": publication, "agentic": self._memory(candidate)}

    def _memory(self, candidate: P0Production) -> dict[str, object]:
        plan = self.plans[candidate.version_ref]
        return {"version_ref": candidate.version_ref, "bundle_sha256": candidate.sha256, "plan": plan,
            "evidence_pack_sha256": fingerprint(self.packs[candidate.version_ref]),
            "validation": self.validations.get(candidate.version_ref),
            "review": self.reports.get(candidate.version_ref),
            "quality": self._local_quality(candidate, quality_status(plan,
                review=self.reports.get(candidate.version_ref), production=candidate.data)),
            "generation_controls": self.generation_controls.get(candidate.version_ref),
            "persistence": "APPLICATION_PUBLICATION_REQUIRED" if self.publish_generated else "EXPLICIT_APPLICATION_SAVE_REQUIRED"}

    def _version(self, data: Mapping[str, object]) -> P0Production:
        candidate = self.records.get(str(data.get("version_ref")))
        if candidate is None and self.saved_reader is not None:
            self._resume(data)
            candidate = self.records.get(str(data.get("version_ref")))
        if candidate is None or candidate.production_ref != data.get("production_ref"):
            raise ValueError("P0_NOT_FOUND")
        if data.get("bundle_sha256", candidate.sha256) != candidate.sha256:
            raise ValueError("P0_VERSION_CHANGED")
        return candidate

    def _resume(self, data: Mapping[str, object]) -> None:
        production = identifier(data.get("production_ref"), "prod")
        version = identifier(data.get("version_ref"), "ver")
        if self.saved_reader is None:
            raise ValueError("P0_NOT_FOUND")
        staged: dict[str, SavedProduction] = {}
        next_version: str | None = version
        while next_version is not None:
            if next_version in staged or len(staged) >= 33:
                raise ValueError("P0_SAVED_LINEAGE")
            record = self.saved_reader(production, next_version)
            candidate = record.p0_bundle
            if (record.data["origin"] != "LOCAL_APPLICATION" or candidate is None
                    or record.production_ref != production or record.version_ref != next_version):
                raise ValueError("P0_SAVED_SOURCE_REJECTED")
            if next_version == version and data.get("bundle_sha256", candidate.sha256) != candidate.sha256:
                raise ValueError("P0_VERSION_CHANGED")
            prior = self.records.get(next_version)
            if prior is not None and prior.sha256 != candidate.sha256:
                raise ValueError("P0_SAVED_VERSION_CONFLICT")
            prior_record = self.resumed.get(next_version)
            if prior_record is not None and prior_record.sha256 != record.sha256:
                raise ValueError("P0_SAVED_VERSION_CONFLICT")
            staged[next_version] = record
            parent = object_data(candidate.data["lineage"])["parent_version_ref"]
            next_version = str(parent) if parent is not None else None
        if len(set(self.records) | set(staged)) > 256:
            raise ValueError("P0_SESSION_FULL")
        from backend.modules.work_orchestration.application.queries.verify_saved_p0_lineage import (
            verify_saved_parent,
        )

        for record in staged.values():
            assert record.p0_bundle is not None
            parent_ref = object_data(record.p0_bundle.data["lineage"])["parent_version_ref"]
            if parent_ref is not None:
                verify_saved_parent(record, staged[str(parent_ref)])
        # Nothing is admitted until the entire chain and identity are verified.
        for key, record in staged.items():
            candidate = record.p0_bundle
            assert candidate is not None
            if key not in self.records:
                self.records[key] = candidate
                self.resumed[key] = record
                self.plans[key] = effort_plan(candidate.context, production=candidate.data)
                self.packs[key] = {}
                self.evidence[key] = {}
                for field, destination in (("reviews", self.reports), ("validations", self.validations)):
                    reports = items(record.data[field], 32)
                    if reports:
                        destination[key] = object_data(as_plain(reports[-1]))
                self.local_reopened.add(key)

    def _local_quality(self, candidate: P0Production, quality: dict[str, object]) -> dict[str, object]:
        if candidate.version_ref in self.local_reopened:
            return {**quality, "sources": "RESERVE",
                    "source_reason": "HISTORICAL_EVIDENCE_NOT_REVALIDATED"}
        if self._root(candidate).version_ref in self.generation_controls:
            return {**quality, "sources": "RESERVE", "source_reason": "SOURCE_USAGE_NOT_DECLARED"}
        return quality

    def read(self, production: str, version: str, *, teacher: bool = False) -> dict[str, object]:
        candidate = self._version({"production_ref": production, "version_ref": version})
        if teacher:
            result: dict[str, object] = {"production_ref": production, "version_ref": version, "bundle_sha256": candidate.sha256,
                    "corrections": as_plain(candidate.data["corrections"]),
                    "marking": as_plain(candidate.data["marking"])}
            if "course_chapter" in candidate.data:
                result["course_chapter"] = candidate.teacher_projection()["course_chapter"]
            if "media_plan" in candidate.data:
                result["media_assets"] = candidate.teacher_projection()["media_assets"]
            return result
        return object_data(as_plain(P0ProductionReadView.from_bundle(candidate).data))

    def publish_local_child(self, parent_record: SavedProduction, child_record: SavedProduction) -> None:
        """Admit one verified local media child, without restoring source authority."""
        parent = self._version({"production_ref": parent_record.production_ref,
            "version_ref": parent_record.version_ref,
            "bundle_sha256": parent_record.p0_bundle.sha256 if parent_record.p0_bundle else ""})
        if self.saved_source(parent.production_ref, parent.version_ref).sha256 != parent_record.sha256:
            raise ValueError("P0_SAVED_VERSION_CONFLICT")
        child = child_record.p0_bundle
        if child is None or child_record.data["origin"] != "LOCAL_APPLICATION":
            raise ValueError("P0_SAVED_SOURCE_REJECTED")
        ReviseSavedP0Candidate().execute(parent, child.mutable_copy())
        if child.version_ref in self.records or len(self.records) >= 256:
            raise ValueError("P0_SAVED_VERSION_CONFLICT")
        plan = effort_plan(child.context, production=child.data)
        self.records[child.version_ref] = child
        self.resumed[child.version_ref] = child_record
        self.plans[child.version_ref] = plan
        self.packs[child.version_ref] = {}
        self.evidence[child.version_ref] = {}
        self.local_reopened.add(child.version_ref)
        validations = items(child_record.data["validations"], 32)
        if validations:
            self.validations[child.version_ref] = object_data(as_plain(validations[-1]))

    def _revise(self, data: dict[str, object]) -> dict[str, object]:
        parent = self._version(data)
        edits = object_data(data["edits"])
        if not edits or set(edits) - {"title", "sections", "questions", "corrections", "marking", "course_edits"}:
            raise ValueError("P0_EDITS_REJECTED")
        output = parent.mutable_copy()
        if "course_chapter" in output:
            from backend.modules.pedagogical_design.application.commands.edit_saved_course import (
                apply_course_edits,
            )
            output = apply_course_edits(output, edits)
        else:
            if "course_edits" in edits:
                raise ValueError("P0_COURSE_EDITS_REQUIRED")
            output.update(edits)
        output["version_ref"] = "ver:" + token_hex(16)
        output["lineage"] = {**object_data(output["lineage"]), "parent_version_ref": parent.version_ref}
        from backend.modules.pedagogical_design.contracts.dto.production_media import (
            rebind_unchanged_media,
        )

        output = rebind_unchanged_media(parent.data, output)
        reopened = parent.version_ref in self.local_reopened
        child = (ReviseSavedP0Candidate().execute(parent, output) if reopened else
                 ReviseP0Candidate().execute(parent, output, evidence=self.evidence[parent.version_ref]))
        self.records[child.version_ref] = child
        self.evidence[child.version_ref] = dict(self.evidence[parent.version_ref])
        self.plans[child.version_ref] = effort_plan(P0Context(object_data(child.data["context"])), production=child.data)
        self.packs[child.version_ref] = dict(self.packs[parent.version_ref])
        if reopened:
            self.local_reopened.add(child.version_ref)
        return {"state": "CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(child).data),
                "provider_attempts": 0, "promotion": "NOT_PERFORMED",
                "quality": self._local_quality(child, quality_status(self.plans[child.version_ref], production=child.data))}

    def _validate(self, data: dict[str, object]) -> dict[str, object]:
        candidate = self._version(data)
        parent = self.records.get(str(object_data(candidate.data["lineage"])["parent_version_ref"]))
        report = ValidateP0Command().execute(candidate, parent=parent)
        self.validations[candidate.version_ref] = report
        return {**report, "quality": self._local_quality(candidate, quality_status(self.plans[candidate.version_ref], review=self.reports.get(candidate.version_ref), production=candidate.data))}

    def _review(self, data: dict[str, object]) -> dict[str, object]:
        candidate = self._version(data)
        if candidate.version_ref in self.local_reopened:
            raise ValueError("P0_REOPENED_REVIEW_REQUIRES_FRESH_EVIDENCE")
        context = P0Context(object_data(candidate.data["context"]))
        if context.institutional is not None or self.exact_institutional_required or (self.exact_stmg_required and str(context.data["level"]).endswith("STMG")):
            context.require_institutional_dispatch()
        root = self._root(candidate)
        if root.version_ref in self.review_consumed:
            raise ValueError("P0_REVIEW_ALREADY_CONSUMED")
        validation = self._validate(data)
        lineage = object_data(candidate.data["lineage"])
        operation = OperationIdentity("op:" + str(data["command_id"]), "step:" + str(data["command_id"]),
                                      str(lineage["source_step_id"]), str(lineage["conversation_id"]))
        request = freeze_safe_mapping({"contract_id": "P0-INDEPENDENT-REVIEW-REQUEST-1.1",
            "operation_identity": operation.as_dict(),
            "production": candidate.mutable_copy(), "bundle_sha256": candidate.sha256,
            "plan": self.plans[candidate.version_ref], "evidence_pack": self.packs[candidate.version_ref],
            "validation": validation})
        if len(encoded(request)) > 128 * 1024:
            raise ValueError("P0_REVIEW_REQUEST_SIZE")
        if self.review is None or not self.review.authorize(request=request):
            return {"state": "AUTHORIZATION_REQUIRED", "provider_attempts": 0, "quality": quality_status(self.plans[candidate.version_ref], production=candidate.data)}
        self.review_consumed.add(root.version_ref)
        report = object_data(as_plain(self.review.review(request=request)))
        validate_p0_review_fields(report)
        expected = {"production_ref": candidate.production_ref, "version_ref": candidate.version_ref, "bundle_sha256": candidate.sha256}
        used = report["evidence_refs_used"]
        coverage = report["coverage"]
        if (not isinstance(used, (list, tuple)) or not all(isinstance(r, str) for r in used)
                or not isinstance(coverage, (list, tuple)) or not all(isinstance(d, str) for d in coverage)
                or len(used) != len(set(used)) or len(coverage) != len(set(coverage))
                or set(coverage) - {"REV-ACC", "REV-COV", "REV-PED", "REV-INS", "REV-STR", "REV-SRC", "REV-CON", "REV-FMT", "REV-RSK"}
                or not set(used) <= set(self.evidence[candidate.version_ref])
                or report["instruction_coverage"] not in {"FULL", "PARTIAL"}
                or (report["instruction_coverage"] == "FULL" and "REV-INS" not in coverage)):
            raise ValueError("P0_REVIEW_BINDING")
        if (any(report.get(k) != v for k, v in expected.items())
                or report.get("status") not in {"completed", "incomplete"}
                or report.get("overall_assessment") not in {"acceptable", "acceptable_with_reservations", "correction_required", "unusable", "incomplete"}
                or type(report.get("correction_required")) is not bool):
            raise ValueError("P0_REVIEW_BINDING")
        # Port output is still technical; exact reports never promote the production.
        if len(encoded(report)) > 32768 or report.get("promotion") != "NOT_PERFORMED":
            raise ValueError("P0_REVIEW_OUTPUT")
        self.reports[candidate.version_ref] = object_data(as_plain(freeze_safe_mapping(report)))
        return {"state": "REVIEWED", "review_sha256": fingerprint(report), "report": report,
            "provider_attempts": 1, "retry": 0, "quality": quality_status(self.plans[candidate.version_ref], review=report, production=candidate.data)}

    def _correct(self, data: dict[str, object]) -> dict[str, object]:
        parent = self._version(data)
        if parent.version_ref in self.local_reopened:
            raise ValueError("P0_REOPENED_REVIEW_REQUIRES_FRESH_EVIDENCE")
        report = self.reports.get(parent.version_ref)
        if not report or fingerprint(report) != data["review_sha256"] or not report["correction_required"]:
            raise ValueError("P0_CORRECTION_REVIEW_REQUIRED")
        root = self._root(parent)
        if root.version_ref in self.correction_consumed:
            raise ValueError("P0_CORRECTION_ALREADY_CONSUMED")
        self.correction_consumed.add(root.version_ref)
        child = self._revise(data)
        view = object_data(child["view"])
        validation = self._validate(view)
        return {**child, "correction_mode": "EXPLICIT_LOCAL_EDITS", "revalidation": validation,
                "quality": quality_status(self.plans[str(view["version_ref"])], production=self.records[str(view["version_ref"])].data)}

    def _root(self, candidate: P0Production) -> P0Production:
        while object_data(candidate.data["lineage"])["parent_version_ref"] in self.records:
            candidate = self.records[str(object_data(candidate.data["lineage"])["parent_version_ref"])]
        return candidate

    def saved_source(self, production: str, version: str) -> SavedProduction:
        candidate = self._version({"production_ref": production, "version_ref": version})
        if version in self.resumed:
            return self.resumed[version]
        if version in self.local_reopened:
            parent_version = str(object_data(candidate.data["lineage"])["parent_version_ref"])
            parent_record = self.saved_source(production, parent_version)
            raw_reservations = parent_record.data["reservations"]
            if not isinstance(raw_reservations, (list, tuple)):
                raise ValueError("P0_SAVED_RESERVATIONS_INVALID")
            reservations = list(raw_reservations)
            if "HISTORICAL_EVIDENCE_NOT_REVALIDATED" not in reservations:
                if len(reservations) == 16:
                    raise ValueError("P0_SAVED_RESERVATIONS_FULL")
                reservations.append("HISTORICAL_EVIDENCE_NOT_REVALIDATED")
            return SavedProduction({"contract_id": SAVED_P0_CONTRACT,
                "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
                "bundle": candidate.mutable_copy(), "reviews": [],
                "validations": [self.validations[version]] if version in self.validations else [],
                "origin": "LOCAL_APPLICATION", "provenance": {
                    **object_data(parent_record.data["provenance"]),
                    "PLAN_SHA256": fingerprint(self.plans[version]),
                    "LOCAL_PARENT_RECORD_SHA256": parent_record.sha256},
                "reservations": reservations})
        controls = self.generation_controls.get(self._root(candidate).version_ref)
        return SavedProduction({"contract_id": SAVED_P0_CONTRACT,
            "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
            "bundle": candidate.mutable_copy(), "reviews": [self.reports[version]] if version in self.reports else [],
            "validations": [self.validations[version]] if version in self.validations else [],
            "origin": "LOCAL_APPLICATION", "provenance": {"PLAN_SHA256": fingerprint(self.plans[version]),
                "EVIDENCE_PACK_SHA256": fingerprint(self.packs[version]),
                **({"GENERATION_CONTROL_SHA256": fingerprint(controls)} if controls else {})},
            "reservations": ["SOURCE_USAGE_NOT_DECLARED"] if controls else []})
