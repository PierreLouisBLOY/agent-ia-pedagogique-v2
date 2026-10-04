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
    fingerprint,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
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
                 *, generation: P0GenerationPort | None = None) -> None:
        self.reference = reference
        self.generation = generation
        self.prepared: dict[str, Mapping[str, object]] = {}
        self.records: dict[str, P0Production] = {}
        self.evidence: dict[str, dict[str, str]] = {}
        self.commands: dict[str, tuple[str, dict[str, object]]] = {}

    def execute(self, operation: str, body: Mapping[str, object]) -> dict[str, object]:
        fields = {
            "prepare": {"command_id", "context", "reference"},
            "generate": {"command_id", "preparation_ref", "preparation_sha256"},
            "revise": {"command_id", "production_ref", "version_ref", "bundle_sha256", "edits"},
            "validate": {"command_id", "production_ref", "version_ref", "bundle_sha256"},
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
            return dict(prior[1])
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
        return dict(result)

    def _prepare(self, data: dict[str, object]) -> dict[str, object]:
        if len(self.prepared) >= 64:
            raise ValueError("P0_SESSION_FULL")
        context = P0Context(object_data(data["context"]))
        loaded = self.reference(object_data(data["reference"]))
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
        self.prepared[ref] = freeze_safe_mapping(request)
        return {"state": "PREPARATION_READY", "authorization": "REQUIRED",
                "preparation_ref": ref, "preparation_sha256": fingerprint(request),
                "context": context.as_dict(), "references": [reference], "provider_attempts": 0}

    def _generate(self, data: dict[str, object]) -> dict[str, object]:
        request = self.prepared.get(str(data["preparation_ref"]))
        if request is None or fingerprint(request) != data["preparation_sha256"]:
            raise ValueError("P0_PREPARATION_CHANGED")
        if self.generation is None or not self.generation.authorize(request=request):
            return {"state": "AUTHORIZATION_REQUIRED", "provider_attempts": 0}
        # Remove the preparation before the single permitted dispatch, including failure.
        del self.prepared[str(data["preparation_ref"])]
        output = self.generation.generate(request=request)
        evidence = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        candidate = CreateP0Candidate().execute(output, evidence=evidence)
        for key in ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage"):
            if as_plain(candidate.data[key]) != as_plain(request[key]):
                raise ValueError("P0_OUTPUT_BINDING")
        self.records[candidate.version_ref] = candidate
        self.evidence[candidate.version_ref] = {str(k): str(v) for k, v in object_data(request["evidence"]).items()}
        return {"state": "CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
                "provider_attempts": 1, "retry": 0, "promotion": "NOT_PERFORMED"}

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
        return {"state": "CANDIDATE", "view": as_plain(P0ProductionReadView.from_bundle(child).data),
                "provider_attempts": 0, "promotion": "NOT_PERFORMED"}

    def _validate(self, data: dict[str, object]) -> dict[str, object]:
        candidate = self._version(data)
        parent = self.records.get(str(object_data(candidate.data["lineage"])["parent_version_ref"]))
        return ValidateP0Command().execute(candidate, parent=parent)

    def saved_source(self, production: str, version: str) -> SavedProduction:
        candidate = self._version({"production_ref": production, "version_ref": version})
        return SavedProduction({"contract_id": SAVED_P0_CONTRACT,
            "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
            "bundle": candidate.mutable_copy(), "reviews": [], "validations": [],
            "origin": "LOCAL_APPLICATION", "provenance": {}, "reservations": []})
