"""One P0 lifecycle, reusing the R6 commands; no provider, SQL or storage access."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from secrets import token_hex
from threading import Lock
from typing import cast

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
    validate_p0_review_binding,
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
from backend.modules.work_orchestration.contracts.dto.p0_codesign_trace import (
    DOCUMENTARY_CONTRACT,
    SAVED_CODESIGN_CONTRACT,
    variant_witness,
)
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_P0_CONTRACT,
    SavedProduction,
)
from backend.modules.work_orchestration.ports.outbound.p0_codesign import (
    P0CoDesignInterrupted,
    P0CoDesignPort,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping


class P0CreationService:
    def __init__(self, reference: Callable[[Mapping[str, object]], Mapping[str, object]],
                 *, generation: P0GenerationPort | None = None, review: P0ReviewPort | None = None,
                 institutional_resolver: Callable[[Mapping[str, object], Mapping[str, object]], Mapping[str, object]] | None = None,
                 focused_institutional_resolver: Callable[[Mapping[str, object], Mapping[str, object]], Mapping[str, object]] | None = None,
                 codesign: P0CoDesignPort | None = None,
                 exact_stmg_required: bool = False, exact_institutional_required: bool = False) -> None:
        self.reference = reference
        self.generation = generation
        self.review = review
        self.codesign = codesign
        self.codesign_consumed: set[str] = set()
        self.codesign_traces: dict[str, Mapping[str, object]] = {}
        self.codesign_versions: set[str] = set()
        self.codesign_lock = Lock()
        self.institutional_resolver = institutional_resolver
        self.focused_institutional_resolver = focused_institutional_resolver
        self.exact_stmg_required = exact_stmg_required
        self.exact_institutional_required = exact_institutional_required
        self.prepared: dict[str, Mapping[str, object]] = {}
        self.records: dict[str, P0Production] = {}
        self.evidence: dict[str, dict[str, str]] = {}
        self.commands: dict[str, tuple[str, dict[str, object]]] = {}
        self.command_lock = Lock()
        self.in_flight: set[str] = set()
        self.codesign_commands: set[str] = set()
        self.codesign_started: set[str] = set()
        from backend.modules.work_orchestration.ports.outbound.p0_finite_consent import (
            P0FiniteConsentPort,
        )
        self.finite_consent: P0FiniteConsentPort | None = None
        self.fresh_codesign_evidence: Callable[[P0Production], Mapping[str, str]] | None = None
        self.codesign_refreshed: set[str] = set()
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
            "local-propose": {"command_id", "preparation_ref", "preparation_sha256"},
            "prepare": {"command_id", "context", "reference"},
            "generate": {"command_id", "preparation_ref", "preparation_sha256"},
            "revise": {"command_id", "production_ref", "version_ref", "bundle_sha256", "edits"},
            "validate": {"command_id", "production_ref", "version_ref", "bundle_sha256"},
            "review": {"command_id", "production_ref", "version_ref", "bundle_sha256"},
            "correct": {"command_id", "production_ref", "version_ref", "bundle_sha256", "review_sha256", "edits"},
            "codesign": {"command_id", "production_ref", "version_ref", "bundle_sha256", "direction", "objective", "evidence_query"},
            "codesign-preview": {"command_id", "production_ref", "version_ref", "bundle_sha256", "direction", "objective", "evidence_query"},
            "codesign-consent": {"command_id", "production_ref", "version_ref", "bundle_sha256", "direction", "objective", "evidence_query", "preview_sha256", "transfer_accepted", "cost_bound_accepted"},
            "codesign-revoke": {"command_id", "preview_sha256"},
        }
        if operation not in fields:
            raise ValueError("P0_REQUEST_REJECTED")
        data = object_data(body, fields[operation])
        command = data["command_id"]
        if not isinstance(command, str) or len(command) != 32 or any(c not in "0123456789abcdef" for c in command):
            raise ValueError("P0_COMMAND_ID")
        identity = fingerprint({"operation": operation, "body": data})
        with self.command_lock:
            prior = self.commands.get(command)
            if prior:
                if prior[0] != identity:
                    raise ValueError("P0_IDEMPOTENCY_CONFLICT")
                if operation in {"codesign", "codesign-consent"} and command in self.in_flight:
                    return {"state": "LOCAL_COMMAND_RUNNING", "command_id": command, "retry": 0}
                return object_data(as_plain(prior[1]))
            if len(self.commands) >= 256:
                raise ValueError("P0_SESSION_FULL")
            # Consumed before any boundary invocation, without retaining this
            # observation lock while a provider/Application port is running.
            self.commands[command] = (identity, {"state": "OUTCOME_UNKNOWN", "retry": 0})
            self.in_flight.add(command)
            if operation in {"codesign", "codesign-consent"}:
                self.codesign_commands.add(command)
        try:
            result = getattr(self, "_" + operation.replace("-", "_"))(data)
        except ValueError as error:
            with self.command_lock:
                state = "LOCAL_RESULT_REJECTED" if command in self.codesign_started else "REFUSED"
                self.commands[command] = (identity, {"state": state, "code": str(error), "retry": 0})
                self.in_flight.discard(command)
            raise
        except Exception:
            with self.command_lock:
                self.in_flight.discard(command)
            # Never expose infrastructure exception text or retry a dispatch.
            raise ValueError("P0_OUTCOME_UNKNOWN") from None
        with self.command_lock:
            self.commands[command] = (identity, result)
            self.in_flight.discard(command)
        return object_data(as_plain(result))

    def read_codesign_command(self, command: str) -> Mapping[str, object] | None:
        with self.command_lock:
            if command not in self.codesign_commands:
                return None
            if command in self.in_flight:
                return {"command_id": command, "state": "LOCAL_COMMAND_RUNNING", "phase": "CO_DESIGN_NATIVE_CHAIN", "retry": 0}
            result = object_data(as_plain(self.commands[command][1]))
        return {"command_id": command, "state": "LOCAL_COMMAND_COMPLETED" if result.get("state") == "CODESIGN_CANDIDATE" else "LOCAL_COMMAND_STOPPED",
                "phase": "LOCAL_RESULT_RETAINED", "result": result, "retry": 0}

    def _local_propose(self, data: dict[str, object]) -> dict[str, object]:
        from backend.modules.pedagogical_design.application.commands.propose_local_reading import (
            ProposeLocalReading,
        )

        request = self.prepared.get(str(data["preparation_ref"]))
        if request is None or fingerprint(request) != data["preparation_sha256"]:
            raise ValueError("P0_PREPARATION_CHANGED")
        if len(self.records) >= 256:
            raise ValueError("P0_SESSION_FULL")
        candidate = ProposeLocalReading().execute(request)
        evidence = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        report = ValidateP0Command().execute(candidate)
        with self.command_lock:
            if self.prepared.get(str(data["preparation_ref"])) is not request:
                raise ValueError("P0_PREPARATION_CHANGED")
            del self.prepared[str(data["preparation_ref"])]
        self.records[candidate.version_ref] = candidate
        self.evidence[candidate.version_ref] = evidence
        self.validations[candidate.version_ref] = report
        # An immutable preparation creates at most one initial local version.
        return {"state": "CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
                "provider_attempts": 0, "promotion": "NOT_PERFORMED", "validation": report,
                "proposal_scope": "EXACT_EXCERPT_CRITICAL_READING_ONLY", "agentic": self._memory(candidate)}


    def _prepare(self, data: dict[str, object]) -> dict[str, object]:
        if len(self.prepared) >= 64:
            raise ValueError("P0_SESSION_FULL")
        context = P0Context(object_data(data["context"]))
        selection = object_data(data["reference"])
        if context.institutional is not None:
            if self.institutional_resolver is None:
                raise ValueError("P0_INSTITUTIONAL_RESOLVER_REQUIRED")
            resolver = self.institutional_resolver
            if context.data["contract_id"] in {"P0-CONTEXT-EXERCISE-1.1", "P0-CONTEXT-CASE-STUDY-1.0"}:
                focused = self.focused_institutional_resolver
                if focused is None:
                    raise ValueError("EXERCISE_FOCUS_RESOLVER_REQUIRED")
                resolver = focused
            resolved = object_data(resolver(context.institutional, selection))
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
        with self.command_lock:
            if self.prepared.get(str(data["preparation_ref"])) is not request:
                raise ValueError("P0_PREPARATION_CHANGED")
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
            if "exercise" in candidate.data:
                result["exercise"] = candidate.teacher_projection()["exercise"]
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
        report = ValidateP0Command().execute(child, parent=parent)
        self.records[child.version_ref] = child
        if not reopened:
            self.validations[child.version_ref] = report
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

    def _codesign(self, data: dict[str, object]) -> dict[str, object]:
        """One explicit, separately authorized chain; historical quotas unchanged."""
        parent = self._version(data)
        if data["direction"] not in {"V2_TO_AI", "AI_TO_V2"}:
            raise ValueError("P0_CODESIGN_DIRECTION")
        from backend.modules.pedagogical_design.application.services.codesign_media import (
            require_codesign_media_parent,
        )
        try:
            require_codesign_media_parent(parent)
        except ValueError as error:
            return {"state": "BLOCKED", "code": str(error), "provider_attempts": 0}
        objective = data["objective"]
        if not isinstance(objective, str) or not objective.strip() or len(objective) > 2000:
            raise ValueError("P0_CODESIGN_OBJECTIVE")
        query = data["evidence_query"]
        if query is None:
            topics = parent.context.data["topics"]
            assert isinstance(topics, (list, tuple))
            query = " ".join(str(topic) for topic in topics)
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError("P0_CODESIGN_SEARCH_QUERY_REQUIRED")
        root = self._root(parent)
        if root.version_ref in self.codesign_consumed:
            raise ValueError("P0_CODESIGN_ALREADY_CONSUMED")
        if (parent.version_ref in self.local_reopened and parent.version_ref not in self.codesign_refreshed) or not self.evidence.get(parent.version_ref):
            raise ValueError("P0_CODESIGN_FRESH_EVIDENCE_REQUIRED")
        if self.exact_institutional_required or parent.context.institutional is not None:
            parent.context.require_institutional_dispatch()
        request = freeze_safe_mapping({"contract_id": "P0-CODESIGN-REQUEST-1.0",
            "command_id": data["command_id"], "direction": data["direction"], "objective": objective,
            "evidence_query": query,
            "production": parent.mutable_copy(), "evidence": self.evidence[parent.version_ref],
            "evidence_pack": self.packs[parent.version_ref], "plan": self.plans[parent.version_ref]})
        if self.codesign is None or not self.codesign.authorize_chain(request=request):
            return {"state": "AUTHORIZATION_REQUIRED", "code": "P0_CODESIGN_MULTI_OPERATION_AUTHORITY_REQUIRED",
                    "provider_attempts": 0, "historical_create_grants": "UNCHANGED"}
        staged: dict[str, P0Production] = {}
        validations: dict[str, dict[str, object]] = {}

        def validate_variant(raw: Mapping[str, object]) -> Mapping[str, object]:
            child = P0Production(raw)
            previous = staged.get(str(object_data(child.data["lineage"])["parent_version_ref"]), parent)
            before_lineage, after_lineage = object_data(previous.data["lineage"]), object_data(child.data["lineage"])
            renewable = {"source_run_id", "source_step_id", "source_request_id", "parent_version_ref"}
            if (child.data["context"] != previous.data["context"] or child.data["references"] != previous.data["references"]
                    or {k:v for k,v in before_lineage.items() if k not in renewable}
                    != {k:v for k,v in after_lineage.items() if k not in renewable}):
                raise ValueError("P0_CODESIGN_VARIANT_BINDING")
            ReviseP0Candidate().execute(previous, raw, evidence=self.evidence[parent.version_ref])
            if child.version_ref in self.records:
                raise ValueError("P0_CODESIGN_VERSION_CONFLICT")
            old = staged.get(child.version_ref)
            if old is not None and old.sha256 != child.sha256:
                raise ValueError("P0_CODESIGN_VERSION_CONFLICT")
            report = ValidateP0Command().execute(child, parent=previous)
            staged[child.version_ref], validations[child.version_ref] = child, report
            return report

        # Consumed before any agent effect. UNKNOWN cannot replenish the chain.
        with self.codesign_lock:
            if root.version_ref in self.codesign_consumed:
                raise ValueError("P0_CODESIGN_ALREADY_CONSUMED")
            self.codesign_consumed.add(root.version_ref)
        with self.command_lock:
            self.codesign_started.add(str(data["command_id"]))
        def validate_review(report: Mapping[str, object]) -> None:
            child = staged.get(str(report.get("version_ref")))
            if child is None:
                raise ValueError("P0_CODESIGN_REVIEW_BINDING")
            validate_p0_review_binding(report, production_ref=child.production_ref, version_ref=child.version_ref,
                bundle_sha256=child.sha256, evidence_ids=set(self.evidence[parent.version_ref]))
        try:
            technical = self.codesign.run(request=request, validate_variant=validate_variant, validate_review=validate_review)
        except P0CoDesignInterrupted as interrupted:
            trace = freeze_safe_mapping(interrupted.trace)
            self.codesign_traces[parent.version_ref] = trace
            return {"state": interrupted.state, "trace": as_plain(trace), "retry": 0,
                    "code": "P0_CODESIGN_NATIVE_RUN_INCOMPLETE"}
        result = object_data(as_plain(technical),
            {"productions", "reports", "runs", "retrieval", "operations", "correction", "pedagogical_acceptance", "promotion"})
        proposed = items(result["productions"], 2)
        reports = items(result["reports"], 2)
        if (not proposed or len(proposed) != len(reports) or len(proposed) != len(staged)
                or result["pedagogical_acceptance"] != "NOT_PERFORMED" or result["promotion"] != "NOT_PERFORMED"):
            raise ValueError("P0_CODESIGN_RESULT")
        previous = parent
        for raw, report in zip(proposed, reports, strict=True):
            child = P0Production(raw)
            if staged.get(child.version_ref) != child or object_data(child.data["lineage"])["parent_version_ref"] != previous.version_ref:
                raise ValueError("P0_CODESIGN_LINEAGE")
            validate_p0_review_fields(report)
            used = report["evidence_refs_used"]
            if (any(report.get(key) != value for key, value in (
                    ("production_ref", child.production_ref), ("version_ref", child.version_ref),
                    ("bundle_sha256", child.sha256), ("promotion", "NOT_PERFORMED")))
                    or report["status"] != "completed"
                    or not isinstance(used, (list, tuple)) or any(not isinstance(ref, str) for ref in used)
                    or not set(used) <= set(self.evidence[parent.version_ref])):
                raise ValueError("P0_CODESIGN_REVIEW_BINDING")
            previous = child
        # Adopt only after every returned variant/report has passed Application.
        publications = []
        for raw, report in zip(proposed, reports, strict=True):
            child = P0Production(raw)
            version = child.version_ref
            self.records[version], self.validations[version], self.reports[version] = child, validations[version], report
            self.evidence[version] = dict(self.evidence[parent.version_ref])
            self.plans[version], self.packs[version] = effort_plan(child.context, production=child.data), dict(self.packs[parent.version_ref])
            self.codesign_traces[version] = freeze_safe_mapping(result)
            self.codesign_versions.add(version)
            if self.publish_generated is not None:
                try:
                    publication = object_data(self.publish_generated(child.production_ref, version, child.sha256))
                    if (publication.get("state") != "APPLICATION_SAVED"
                            or publication.get("record_sha256") != self.saved_source(child.production_ref, version).sha256):
                        raise ValueError("P0_CODESIGN_PUBLICATION_VERIFICATION")
                    if self.saved_reader is not None:
                        reopened = self.saved_reader(child.production_ref, version)
                        if reopened.sha256 != publication["record_sha256"]:
                            raise ValueError("P0_CODESIGN_PUBLICATION_VERIFICATION")
                    publications.append(publication)
                except Exception:
                    return {"state": "PUBLICATION_OUTCOME_UNKNOWN", "view": as_plain(P0ProductionReadView.from_bundle(child).data),
                            "publications_verified": publications, "trace": result, "retry": 0,
                            "code": "P0_CODESIGN_SAVE_REQUIRES_PASSIVE_VERIFICATION"}
        return {"state": "CODESIGN_CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(previous).data),
                "trace": result, "publications": publications, "retry": 0,
                "promotion": "NOT_PERFORMED", "pedagogical_acceptance": "NOT_PERFORMED"}

    def _codesign_preview(self, data: dict[str, object]) -> dict[str, object]:
        parent = self._version(data)
        if data["direction"] not in {"V2_TO_AI", "AI_TO_V2"} or not isinstance(data["objective"], str) or not data["objective"].strip() or len(data["objective"]) > 2000:
            raise ValueError("P0_CODESIGN_OBJECTIVE")
        from backend.modules.pedagogical_design.application.services.codesign_media import (
            require_codesign_media_parent,
        )
        try:
            require_codesign_media_parent(parent)
        except ValueError as error:
            return {"state": "BLOCKED", "code": str(error), "provider_attempts": 0}
        if self.finite_consent is not None:
            return dict(self.finite_consent.preview(self._finite_request(data)))
        return {"state": "DISARMED", "contract_id": "P0-CODESIGN-PREVIEW-1.0",
                "production_ref": parent.production_ref, "version_ref": parent.version_ref,
                "bundle_sha256": parent.sha256, "direction": data["direction"], "objective": data["objective"],
                "stages": ["AG02_ACTIVE_APPLICATION_SEARCH", "AG03_TRANSFORM" if data["direction"] == "V2_TO_AI" else "AG03_GENERATE",
                    "APPLICATION_VALIDATE", "AG04_REVIEW", "AT_MOST_ONE_AG03_CORRECTION", "FRESH_AG04_REVIEW", "R4_SAVE_REOPEN_EXPORT"],
                "maximum_semantic_operations": 4, "provider_attempts": 0, "authority": "NONE",
                "required_decision": "EXACT_MULTI_OPERATION_BINDING_AND_CUMULATIVE_BUDGET",
                "historical_create_permissions": "UNCHANGED", "cost_status": "NOT_QUALIFIED_FOR_THIS_CHAIN"}

    def _finite_request(self, data: Mapping[str, object]) -> Mapping[str, object]:
        parent = self._version(data)
        if self.fresh_codesign_evidence is None:
            raise ValueError("P0_CHAIN_FRESH_SOURCE_READER_REQUIRED")
        evidence = dict(self.fresh_codesign_evidence(parent))
        for reference in items(parent.data["references"], 8):
            value = evidence.get(str(reference["evidence_id"]))
            if not isinstance(value, str) or not value or fingerprint(value) == "":
                raise ValueError("P0_CHAIN_FRESH_EVIDENCE_REQUIRED")
            import hashlib
            if hashlib.sha256(value.encode()).hexdigest() != reference["excerpt_sha256"]:
                raise ValueError("P0_CHAIN_SOURCE_CHANGED")
        self.evidence[parent.version_ref] = evidence
        self.packs[parent.version_ref] = evidence_pack(parent.context, parent.data["references"], evidence)
        self.plans[parent.version_ref] = effort_plan(parent.context, production=parent.data)
        self.codesign_refreshed.add(parent.version_ref)
        query = data["evidence_query"]
        if query is None:
            query = " ".join(str(topic) for topic in cast(tuple[object, ...], parent.context.data["topics"]))
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError("P0_CODESIGN_SEARCH_QUERY_REQUIRED")
        return freeze_safe_mapping({"contract_id": "P0-CODESIGN-REQUEST-1.0", "command_id": data["command_id"],
            "direction": data["direction"], "objective": data["objective"], "evidence_query": query,
            "production": parent.mutable_copy(), "evidence": evidence, "evidence_pack": self.packs[parent.version_ref],
            "plan": self.plans[parent.version_ref]})

    def _codesign_consent(self, data: dict[str, object]) -> dict[str, object]:
        if self.finite_consent is None:
            raise ValueError("P0_CHAIN_CONSENT_NOT_BOUND")
        request = self._finite_request(data)
        core = {key: data[key] for key in ("command_id", "production_ref", "version_ref", "bundle_sha256", "direction", "objective", "evidence_query")}
        # Normalize only the query default already exposed in the exact preview.
        consent = {**data, "evidence_query": request["evidence_query"]}
        return dict(self.finite_consent.finalize(request=request, consent=consent, run=lambda: self._codesign(core)))

    def _codesign_revoke(self, data: dict[str, object]) -> dict[str, object]:
        if self.finite_consent is None or not isinstance(data["preview_sha256"], str):
            raise ValueError("P0_CHAIN_CONSENT_NOT_BOUND")
        return dict(self.finite_consent.revoke(data["preview_sha256"]))

    def _root(self, candidate: P0Production) -> P0Production:
        while object_data(candidate.data["lineage"])["parent_version_ref"] in self.records:
            candidate = self.records[str(object_data(candidate.data["lineage"])["parent_version_ref"])]
        return candidate

    def saved_source(self, production: str, version: str) -> SavedProduction:
        candidate = self._version({"production_ref": production, "version_ref": version})
        if version in self.resumed:
            return self.resumed[version]
        if version in self.codesign_versions:
            trace = self.codesign_traces[version]
            parent_ref = str(object_data(candidate.data["lineage"])["parent_version_ref"])
            parent_record = self.saved_source(production, parent_ref)
            if parent_record.p0_bundle is None:
                raise ValueError("P0_CODESIGN_PARENT_BUNDLE_REQUIRED")
            parent_sha = parent_record.p0_bundle.sha256
            inherited = parent_record.data["reservations"]
            if not isinstance(inherited, (list, tuple)):
                raise ValueError("P0_SAVED_RESERVATIONS_INVALID")
            reservations = list(inherited)
            for reserve in ("TEACHER_ACCEPTANCE_NOT_PERFORMED", "DOCUMENTARY_TRACE_RESTORES_NO_AUTHORITY"):
                if reserve not in reservations:
                    reservations.append(reserve)
            own = next((row for row in items(trace["operations"], 2) if row["bundle_sha256"] == candidate.sha256), None)
            if own is None:
                raise ValueError("P0_CODESIGN_OPERATION_REQUIRED")
            own_controls = object_data(own["controls"])
            if own_controls["guard_disposition"] != "ALLOW" or own_controls["warnings_json"] != "[]" or own_controls["uncertainties_json"] != "[]":
                warning = "Avertissements AG03 conservés dans la trace V2 ; relecture professeur requise."
                if warning not in reservations:
                    reservations.append(warning)
            if len(reservations) > 16:
                raise ValueError("P0_SAVED_RESERVATIONS_FULL")
            return SavedProduction({"contract_id": SAVED_CODESIGN_CONTRACT,
                "view": as_plain(P0ProductionReadView.from_bundle(candidate).data), "bundle": candidate.mutable_copy(),
                "reviews": [self.reports[version]], "validations": [self.validations[version]],
                "origin": "LOCAL_APPLICATION", "provenance": {"CO_DESIGN_TRACE_SHA256": fingerprint(trace)},
                "reservations": reservations,
                "codesign": {"contract_id": DOCUMENTARY_CONTRACT, "trace": as_plain(trace),
                    "parent_bundle_sha256": parent_sha, "parent_record_sha256": parent_record.sha256,
                    "witness_sha256": variant_witness(candidate, parent_sha, parent_record.sha256, trace)}})
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
