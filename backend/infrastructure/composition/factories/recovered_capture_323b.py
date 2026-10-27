"""Explicit isolated Application composition; never loads/restarts a server."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from backend.adapters.inbound.application.saved_production import SavedProductionInbound
from backend.infrastructure.composition.factories.captured_content_validation import (
    NormalCapturedContentValidation,
)
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.infrastructure.composition.factories.p0_normal_profile import read_descriptor
from backend.infrastructure.composition.factories.rejected_capture_323b import (
    ENVELOPE_SHA256,
    TARGET,
    compose_rejected_capture_323b,
)
from backend.modules.pedagogical_design.application.commands.repair_adopted_capture import (
    PLAN_SHA256,
    RepairAdoptedCapture,
)
from backend.modules.work_orchestration.application.commands.prepare_recovered_capture import (
    PreparedRecoveredCapture,
    PrepareRecoveredCapture,
)
from backend.modules.work_orchestration.application.commands.publish_recovered_capture import (
    PublishRecoveredCapture,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction

ADOPTION_SHA256 = "a56d66a8a7d4a57eec6b9de36f80079195e8909d58c949e0e218bcf826b3bd2f"


class R4RecoveredCaptureBridge:
    def __init__(self, saved: SavedProductionInbound) -> None:
        self.saved, self._record = saved, cast(SavedProduction | None, None)

    def source(self, production: str, version: str) -> SavedProduction:
        record = self._record
        if record is None or (production, version) != (record.production_ref, record.version_ref):
            raise ValueError("LOCAL_RECOVERY_R4_SOURCE_NOT_BOUND")
        return record

    def save(self, record: SavedProduction) -> Mapping[str, object]:
        if self._record is not None and self._record.sha256 != record.sha256:
            raise ValueError("LOCAL_RECOVERY_R4_ONE_RECORD_ONLY")
        self._record = record
        result = self.saved.execute("save", body={"production_ref": record.production_ref,
            "version_ref": record.version_ref}, correlation="323b.local-recovered-save")
        if not isinstance(result, Mapping):
            raise ValueError("LOCAL_RECOVERY_R4_RECEIPT_REQUIRED")
        return result

    def reopen(self, production_ref: str, version_ref: str) -> SavedProduction:
        result = self.saved.execute("open", production_ref, version_ref, correlation="323b.local-recovered-open")
        if (not isinstance(result, Mapping) or result.get("status") != "CANDIDATE"
                or result.get("active_authority") != "NONE_RESTORED"
                or not isinstance(result.get("record"), Mapping)):
            raise ValueError("LOCAL_RECOVERY_R4_CANDIDATE_REQUIRED")
        record = SavedProduction(cast(Mapping[str, object], result["record"]))
        if result.get("record_sha256") != record.sha256:
            raise ValueError("LOCAL_RECOVERY_R4_READBACK_BINDING")
        return record


class RecoveredCapture323BComposition:
    def __init__(self, *, envelope_path: Path, plan_path: Path, adoption_path: Path) -> None:
        self.envelope_path, self.plan_path, self.adoption_path = envelope_path, plan_path, adoption_path
        self._verify_scope()
        plan = cast(Mapping[str, object], read_descriptor({"path": str(plan_path), "sha256": PLAN_SHA256}))
        self.reader = compose_rejected_capture_323b(envelope_path)
        self.preparer = PrepareRecoveredCapture(NormalCapturedContentValidation(),
            repair=RepairAdoptedCapture(plan).execute, plan_sha256=PLAN_SHA256, adoption_sha256=ADOPTION_SHA256, scope=TARGET)

    def _verify_scope(self) -> None:
        plan = cast(Mapping[str, object], read_descriptor({"path": str(self.plan_path), "sha256": PLAN_SHA256}))
        adoption = cast(Mapping[str, object], read_descriptor({"path": str(self.adoption_path), "sha256": ADOPTION_SHA256}))
        if (plan["command_id"] != TARGET.command_id or plan["capture_sha256"] != TARGET.result_sha256
                or adoption.get("status") != "ADOPTED_LOCAL_EXACT" or adoption.get("plan_sha256") != PLAN_SHA256
                or adoption.get("source") != "DIRECT_HUMAN_ASYNC_QUESTION_REPLY"
                or adoption.get("answer_exact") != "Oui, extension locale exacte"
                or adoption.get("command_id") != TARGET.command_id
                or adoption.get("capture_sha256") != TARGET.result_sha256):
            raise ValueError("LOCAL_RECOVERY_ADOPTION_SCOPE")
        read_descriptor({"path": str(self.envelope_path), "sha256": ENVELOPE_SHA256})

    def prepare(self) -> PreparedRecoveredCapture:
        self._verify_scope()
        return self.preparer.execute(self.reader.read(TARGET))

    def publish(self, *, expected_record_sha256: str) -> dict[str, object]:
        self._verify_scope()
        envelope = cast(Mapping[str, object], read_descriptor({"path": str(self.envelope_path), "sha256": ENVELOPE_SHA256}))
        profile = cast(Mapping[str, object], envelope["profile"])
        # Bridge is dormant until the explicit publish call. Existing library only.
        saved = build_saved_application(Path(str(profile["saved_root"])), create=False, word_profile="product-v7")
        bridge = R4RecoveredCaptureBridge(saved)
        saved.source = bridge.source
        usecase = PublishRecoveredCapture(query=self.reader.query, request=TARGET,
            preparer=self.preparer, saver=bridge, verify_scope=self._verify_scope)
        return usecase.execute(expected_record_sha256=expected_record_sha256)
