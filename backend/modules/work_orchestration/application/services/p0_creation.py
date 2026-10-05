"""One P0 lifecycle, reusing the R6 commands; no provider, SQL or storage access."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from secrets import token_hex

from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
    ReviseP0Candidate,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.quality_evaluation.ports.outbound.p0_review import P0ReviewPort
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.application.services.p0_agentic import (
    effort_plan,
    evidence_pack,
    quality_status,
)
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
                 exact_stmg_required: bool = False) -> None:
        self.reference = reference
        self.generation = generation
        self.review = review
        self.institutional_resolver = institutional_resolver
        self.exact_stmg_required = exact_stmg_required
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
            confirmed = context.as_dict()
            confirmed["institutional_resolution"] = resolved
            context = P0Context(confirmed)
        elif self.exact_stmg_required and str(context.data["level"]).endswith("STMG"):
            raise ValueError("P0_INSTITUTIONAL_CONTEXT_REQUIRED")
        loaded = self.reference(selection)
        reference = object_data(loaded["reference"])
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
        if context.institutional is not None or self.exact_stmg_required:
            context.require_institutional_dispatch()
        if self.generation is None or not self.generation.authorize(request=request):
            return {"state": "AUTHORIZATION_REQUIRED", "provider_attempts": 0}
        # Remove the preparation before the single permitted dispatch, including failure.
        del self.prepared[str(data["preparation_ref"])]
        output = self.generation.generate(request=request)
        evidence = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        candidate = CreateP0Candidate().execute(output, evidence=evidence)
        if context.institutional is not None and context.resource_type == "COURSE":
            from backend.modules.pedagogical_design.contracts.dto.course_policy import (
                validate_course_structure,
            )

            validate_course_structure(candidate.data["sections"])
        for key in ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage"):
            if as_plain(candidate.data[key]) != as_plain(request[key]):
                raise ValueError("P0_OUTPUT_BINDING")
        self.records[candidate.version_ref] = candidate
        self.evidence[candidate.version_ref] = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        self._validate({"production_ref": candidate.production_ref, "version_ref": candidate.version_ref})
        return {"state": "CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
                "provider_attempts": 1, "retry": 0, "promotion": "NOT_PERFORMED",
                "agentic": self._memory(candidate)}

    def _memory(self, candidate: P0Production) -> dict[str, object]:
        plan = self.plans[candidate.version_ref]
        return {"version_ref": candidate.version_ref, "bundle_sha256": candidate.sha256, "plan": plan,
            "evidence_pack_sha256": fingerprint(self.packs[candidate.version_ref]),
            "validation": self.validations.get(candidate.version_ref),
            "review": self.reports.get(candidate.version_ref),
            "quality": quality_status(plan, review=self.reports.get(candidate.version_ref)),
            "persistence": "EXPLICIT_APPLICATION_SAVE_REQUIRED"}

    def _version(self, data: Mapping[str, object]) -> P0Production:
        candidate = self.records.get(str(data.get("version_ref")))
        if candidate is None or candidate.production_ref != data.get("production_ref"):
            raise ValueError("P0_NOT_FOUND")
        if data.get("bundle_sha256", candidate.sha256) != candidate.sha256:
            raise ValueError("P0_VERSION_CHANGED")
        return candidate

    def read(self, production: str, version: str, *, teacher: bool = False) -> dict[str, object]:
        candidate = self._version({"production_ref": production, "version_ref": version})
        if teacher:
            return {"version_ref": version, "bundle_sha256": candidate.sha256,
                    "corrections": as_plain(candidate.data["corrections"]),
                    "marking": as_plain(candidate.data["marking"])}
        return object_data(as_plain(P0ProductionReadView.from_bundle(candidate).data))

    def _revise(self, data: dict[str, object]) -> dict[str, object]:
        parent = self._version(data)
        edits = object_data(data["edits"])
        if not edits or set(edits) - {"title", "sections", "questions", "corrections", "marking"}:
            raise ValueError("P0_EDITS_REJECTED")
        output = parent.mutable_copy()
        output.update(edits)
        output["version_ref"] = "ver:" + token_hex(16)
        output["lineage"] = {**object_data(output["lineage"]), "parent_version_ref": parent.version_ref}
        child = ReviseP0Candidate().execute(parent, output, evidence=self.evidence[parent.version_ref])
        self.records[child.version_ref] = child
        self.evidence[child.version_ref] = dict(self.evidence[parent.version_ref])
        self.plans[child.version_ref] = effort_plan(P0Context(object_data(child.data["context"])))
        self.packs[child.version_ref] = dict(self.packs[parent.version_ref])
        return {"state": "CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(child).data),
                "provider_attempts": 0, "promotion": "NOT_PERFORMED"}

    def _validate(self, data: dict[str, object]) -> dict[str, object]:
        candidate = self._version(data)
        parent = self.records.get(str(object_data(candidate.data["lineage"])["parent_version_ref"]))
        report = ValidateP0Command().execute(candidate, parent=parent)
        self.validations[candidate.version_ref] = report
        return {**report, "quality": quality_status(self.plans[candidate.version_ref], review=self.reports.get(candidate.version_ref))}

    def _review(self, data: dict[str, object]) -> dict[str, object]:
        candidate = self._version(data)
        context = P0Context(object_data(candidate.data["context"]))
        if context.institutional is not None or self.exact_stmg_required:
            context.require_institutional_dispatch()
        root = self._root(candidate)
        if root.version_ref in self.review_consumed:
            raise ValueError("P0_REVIEW_ALREADY_CONSUMED")
        validation = self._validate(data)
        request = freeze_safe_mapping({"contract_id": "P0-INDEPENDENT-REVIEW-REQUEST-1.0",
            "production": candidate.mutable_copy(), "bundle_sha256": candidate.sha256,
            "plan": self.plans[candidate.version_ref], "evidence_pack": self.packs[candidate.version_ref],
            "validation": validation})
        if len(encoded(request)) > 128 * 1024:
            raise ValueError("P0_REVIEW_REQUEST_SIZE")
        if self.review is None or not self.review.authorize(request=request):
            return {"state": "AUTHORIZATION_REQUIRED", "provider_attempts": 0, "quality": quality_status(self.plans[candidate.version_ref])}
        self.review_consumed.add(root.version_ref)
        report = object_data(as_plain(self.review.review(request=request)), {
            "contract_id", "status", "production_ref", "version_ref", "bundle_sha256", "overall_assessment",
            "correction_required", "coverage", "instruction_coverage", "findings", "limitations",
            "evidence_refs_used", "created_at", "promotion"})
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
        if (report.get("contract_id") != "P0-REVIEW-1.0" or any(report.get(k) != v for k, v in expected.items())
                or report.get("status") not in {"completed", "incomplete"}
                or report.get("overall_assessment") not in {"acceptable", "acceptable_with_reservations", "correction_required", "unusable", "incomplete"}
                or type(report.get("correction_required")) is not bool):
            raise ValueError("P0_REVIEW_BINDING")
        # Port output is still technical; exact reports never promote the production.
        if len(encoded(report)) > 32768 or report.get("promotion") != "NOT_PERFORMED":
            raise ValueError("P0_REVIEW_OUTPUT")
        self.reports[candidate.version_ref] = object_data(as_plain(freeze_safe_mapping(report)))
        return {"state": "REVIEWED", "review_sha256": fingerprint(report), "report": report,
            "provider_attempts": 1, "retry": 0, "quality": quality_status(self.plans[candidate.version_ref], review=report)}

    def _correct(self, data: dict[str, object]) -> dict[str, object]:
        parent = self._version(data)
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
                "quality": quality_status(self.plans[str(view["version_ref"])])}

    def _root(self, candidate: P0Production) -> P0Production:
        while object_data(candidate.data["lineage"])["parent_version_ref"] in self.records:
            candidate = self.records[str(object_data(candidate.data["lineage"])["parent_version_ref"])]
        return candidate

    def saved_source(self, production: str, version: str) -> SavedProduction:
        candidate = self._version({"production_ref": production, "version_ref": version})
        return SavedProduction({"contract_id": SAVED_P0_CONTRACT,
            "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
            "bundle": candidate.mutable_copy(), "reviews": [self.reports[version]] if version in self.reports else [],
            "validations": [self.validations[version]] if version in self.validations else [],
            "origin": "LOCAL_APPLICATION", "provenance": {"PLAN_SHA256": fingerprint(self.plans[version]),
                "EVIDENCE_PACK_SHA256": fingerprint(self.packs[version])}, "reservations": []})
