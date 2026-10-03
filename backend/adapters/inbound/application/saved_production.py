"""R4 Application boundary; transport passes intent, never storage or authority objects."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    GateDecision,
    GateDecisionValue,
    GateRequest,
)
from backend.agent_runtime.contracts.gates.gate_request import GateStatus
from backend.agent_runtime.gates.authority import GateAuthorityPolicy
from backend.agent_runtime.gates.engine import GateEngine
from backend.agent_runtime.gates.model import GateResolutionDisposition
from backend.modules.lifecycle_promotion.application.commands.promote_saved import (
    PromoteSavedCommand,
)
from backend.modules.lifecycle_promotion.contracts.dto.promotion import PromotionGate
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    identifier,
    object_data,
)
from backend.modules.work_orchestration.application.dto.input.read_production import (
    ReadProductionRequest,
)
from backend.modules.work_orchestration.application.queries.read_production import (
    ReadProductionQuery,
)
from backend.modules.work_orchestration.application.services.saved_production import (
    SavedProductionService,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


@dataclass
class _HumanDecision:
    value: GateDecision

    def receive(self, *, request: GateRequest) -> GateDecision | None:
        return self.value if self.value.request == request else None


class SavedProductionInbound:
    def __init__(self, service: SavedProductionService, reader: ReadProductionQuery,
                 exporter: ExportSavedCommand, *, source: Callable[[str, str], SavedProduction] | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.service = service
        self.reader = reader
        self.exporter = exporter
        self.source = source
        self.clock = clock
        self.pending: dict[str, GateRequest] = {}

    def admit_documentary(self, record: SavedProduction) -> dict[str, object]:
        """Offline import of a typed documentary projection, restoring no authority."""
        if type(record) is not SavedProduction or record.data["origin"] != "IMPORTED_DOCUMENTARY":
            raise ValueError("R4_DOCUMENTARY_IMPORT_REQUIRED")
        if record.data["reviews"] or record.data["validations"]:
            raise ValueError("R4_DOCUMENTARY_REPORT_ADMISSION_REQUIRED")
        return self.service.save(record)

    def execute(self, operation: str, production_ref: str = "", version_ref: str = "",
                *, body: Mapping[str, object] | None = None, kind: str = "",
                correlation: str) -> dict[str, object] | bytes:
        values = dict(body or {})
        if operation == "list":
            return {"versions": self.service.list_versions()}
        if operation == "save":
            if set(values) != {"production_ref", "version_ref"} or self.source is None:
                raise ValueError("R4_SOURCE_NOT_AVAILABLE")
            record = self.source(identifier(values["production_ref"], "prod"),
                                 identifier(values["version_ref"], "ver"))
            if record.data["origin"] != "LOCAL_APPLICATION":
                raise ValueError("R4_SOURCE_NOT_AVAILABLE")
            return self.service.save(record)
        record = self.service.store.load(production_ref, version_ref)
        # Read through the already delivered CAP-R02, not a parallel content query.
        read = self.reader.execute(ReadProductionRequest(production_ref, version_ref),
            conversation_id=record.view.conversation_id, correlation_id=CorrelationId(correlation))
        if not read.success or read.data is None or read.data.data != record.view.data:
            raise ValueError("R4_READ_FAILED")
        if operation == "open":
            return self.service.open(production_ref, version_ref)
        if operation in {"preview", "word"}:
            promoted = self.service.open(production_ref, version_ref)["status"] == "PROMOTED"
            if operation == "preview":
                return self.exporter.preview(record, kind, promoted=promoted).as_dict()
            return self.exporter.execute(record, kind, promoted=promoted)
        if operation == "validate":
            if set(values) != {"action_id", "record_sha256"}:
                raise ValueError("R4_REQUEST_REJECTED")
            return self.service.validate(production_ref, version_ref,
                identifier(values["action_id"], "action"), str(values["record_sha256"]))
        if operation == "gate":
            if record.data["origin"] != "LOCAL_APPLICATION":
                raise ValueError("R4_DOCUMENTARY_IMPORT_READ_ONLY")
            reports = [object_data(a["report"]) for a in self.service.store.actions(record)
                       if a.get("kind") == "CAP-A01"]
            if not reports:
                raise ValueError("R4_VALIDATION_REQUIRED")
            now = self.clock()
            self.pending = {key: req for key, req in self.pending.items()
                            if req.expires_at and req.expires_at.value > now}
            if len(self.pending) >= 32:
                raise ValueError("R4_GATE_LIMIT")
            gate_id = "gate:" + uuid4().hex
            actor = ActorRef(ActorKind.USER, "local-owner")
            request = GateRequest(ContractMeta(schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                run_id="r4-promotion", step_id=gate_id, parent_step_id=None,
                correlation_id=CorrelationId(correlation), created_at=Instant(now),
                actor=actor, status=GateStatus.PENDING), gate_id, "PROMOTION",
                "Promotion explicite de cette version ; A16 reste visible.",
                ({"choice": "PROMOTE_EXACT_VERSION"},), actor,
                {"record_sha256": record.sha256, "validation_ref": reports[-1]["validation_ref"]},
                Instant(now + timedelta(minutes=5)))
            self.pending[gate_id] = request
            return {"gate_id": gate_id, "record_sha256": record.sha256,
                    "validation_ref": reports[-1]["validation_ref"],
                    "expires_at": request.expires_at.value.isoformat() if request.expires_at else "",
                    "warning": request.reason}
        if operation == "promote":
            if set(values) != {"action_id", "record_sha256", "gate_id", "confirmation", "acknowledge_a16"}:
                raise ValueError("R4_REQUEST_REJECTED")
            action_id = identifier(values["action_id"], "action")
            gate: PromotionGate | None = None
            pending_request = self.pending.pop(str(values["gate_id"]), None)
            now = self.clock()
            if pending_request and pending_request.expires_at and values["confirmation"] == "PROMOTE_EXACT_VERSION" and values["acknowledge_a16"] is True and now < pending_request.expires_at.value:
                request = pending_request
                decision = GateDecision(replace(request.meta, created_at=Instant(now), status=GateStatus.APPROVED),
                    request.gate_id, GateDecisionValue.APPROVED, request.required_actor, Instant(now),
                    "decision:" + uuid4().hex, request, {"choice": "PROMOTE_EXACT_VERSION"})
                result = GateEngine(GateAuthorityPolicy(), _HumanDecision(decision)).evaluate(
                    request=request, now=Instant(now))
                if result.disposition is GateResolutionDisposition.APPROVED:
                    gate = PromotionGate(str(result.decision_ref), request.required_actor.actor_id,
                        str(request.context_summary["record_sha256"]),
                        str(request.context_summary["validation_ref"]), True, True,
                        request.meta.created_at.value, pending_request.expires_at.value)
            return PromoteSavedCommand(self.service.store).execute(production_ref=production_ref,
                version_ref=version_ref, action_id=action_id, expected_sha256=str(values["record_sha256"]),
                gate=gate, now=now)
        raise ValueError("R4_REQUEST_REJECTED")
