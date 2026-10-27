"""Publish one owner-scoped local derivative, retaining all original outcomes."""
from __future__ import annotations

import re
from collections.abc import Callable

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.application.commands.prepare_recovered_capture import (
    PrepareRecoveredCapture,
)
from backend.modules.work_orchestration.application.queries.read_rejected_capture import (
    ReadRejectedCapture,
)
from backend.modules.work_orchestration.contracts.dto.rejected_capture import RejectedCaptureRequest
from backend.modules.work_orchestration.ports.outbound.recovered_capture_publication import (
    RecoveredCapturePublication,
)


class PublishRecoveredCapture:
    def __init__(self, *, query: ReadRejectedCapture, request: RejectedCaptureRequest,
                 preparer: PrepareRecoveredCapture, saver: RecoveredCapturePublication,
                 verify_scope: Callable[[], None]) -> None:
        self.query, self.request, self.preparer = query, request, preparer
        self.saver, self.verify_scope = saver, verify_scope

    def execute(self, *, expected_record_sha256: str) -> dict[str, object]:
        self.verify_scope()
        capture = self.query.execute(self.request)
        prepared = self.preparer.execute(capture)
        record = prepared.record
        if record.sha256 != expected_record_sha256:
            raise ValueError("LOCAL_RECOVERY_RECORD_CHANGED_BEFORE_SAVE")
        self.verify_scope()
        result: dict[str, object] = {"production_ref": record.production_ref, "version_ref": record.version_ref,
            "record_sha256": record.sha256, "provider_calls": 0, "new_reservations": 0,
            "status": "LOCAL_DERIVATIVE_SAVE_OUTCOME_UNCONFIRMED", "saved": None,
            "write_attempted": True, "readback_verified": False, "capture_verified_after": False}
        try:
            receipt = self.saver.save(record)
        except Exception as error:
            result["error_code"] = self._code(error)
            return result
        result["save_receipt"] = dict(receipt)
        if (receipt.get("saved") is not True or receipt.get("record_sha256") != record.sha256
                or receipt.get("production_ref") != record.production_ref or receipt.get("version_ref") != record.version_ref):
            result["error_code"] = "LOCAL_RECOVERY_SAVE_RECEIPT_BINDING"
            return result
        result.update(saved=True, status="LOCAL_DERIVATIVE_SAVED_VERIFICATION_FAILED")
        try:
            reopened = self.saver.reopen(record.production_ref, record.version_ref)
            if reopened.sha256 != record.sha256 or reopened.data != record.data:
                raise ValueError("LOCAL_RECOVERY_READBACK_CHANGED")
            result["readback_verified"] = True
            after = self.query.execute(self.request)
            for key in ("receipt_hashes_before", "receipt_hashes_after", "slot_sha256", "result_sha256", "output_text_sha256"):
                if after.metadata.get(key) != capture.metadata.get(key):
                    raise ValueError("LOCAL_RECOVERY_ORIGINAL_CHANGED_AFTER_SAVE")
            if fingerprint(after.dispatch) != fingerprint(capture.dispatch) or after.output_text != capture.output_text:
                raise ValueError("LOCAL_RECOVERY_ORIGINAL_CHANGED_AFTER_SAVE")
            self.verify_scope()
            result.update(capture_verified_after=True, status="LOCAL_DERIVATIVE_SAVED_VERIFIED")
        except Exception as error:
            result["error_code"] = self._code(error)
        return result

    @staticmethod
    def _code(error: Exception) -> str:
        text = str(error)
        return text if re.fullmatch(r"[A-Z0-9_]{1,160}", text) else type(error).__name__
