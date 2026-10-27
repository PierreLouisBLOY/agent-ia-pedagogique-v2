"""Read one rejected normal capture under its existing native P1 LOCK."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    recover_binding,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.infrastructure.filesystem import capture_secure_path, read_file_nofollow
from backend.modules.work_orchestration.contracts.dto.rejected_capture import (
    RejectedCapture,
    RejectedCaptureRequest,
)

_DOCUMENTS = ("DISPATCH", "RESULT", "RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSING_REJECTED")


class NormalRejectedCaptureReader:
    def __init__(self, *, root: Path, permission_loader: Callable[[], Mapping[str, object]],
                 binding: RejectedCaptureRequest) -> None:
        self.root, self.loader, self.binding = root, permission_loader, binding

    def read(self, request: RejectedCaptureRequest) -> RejectedCapture:
        if request != self.binding:
            raise ValueError("REJECTED_CAPTURE_READER_SCOPE")
        permission = self.loader()
        if sha(canonical(permission)) != request.permission_sha256:
            raise ValueError("REJECTED_CAPTURE_PERMISSION")
        ledger = P0ProductLedger(root=self.root, permission=permission)
        with ledger.locked(create=False):
            slots = ledger.slots()
            selected = [row for row in slots if row["command_id"] == request.command_id]
            if len(selected) != 1:
                raise ValueError("REJECTED_CAPTURE_COMMAND_NOT_UNIQUE")
            slot = selected[0]
            expected = {"permission_sha256": request.permission_sha256,
                "request_sha256": request.request_sha256, "grant_sha256": request.grant_sha256,
                "preflight_sha256": request.preflight_sha256}
            if any(slot[key] != value for key, value in expected.items()):
                raise ValueError("REJECTED_CAPTURE_SLOT_BINDING")
            receipt = P0NormalReceipt(self.root, str(slot["namespace_sha256"]))
            if any(receipt.exists(name) for name in ("UNKNOWN", "PARSED", "CONSUMED")):
                raise ValueError("REJECTED_CAPTURE_EXACT_STATE_REQUIRED")
            slot_path = self.root / (ledger.prefix + str(slot["preview_sha256"]) + ".json")
            paths = {name: receipt._path(name) for name in _DOCUMENTS}
            paths["P1_SLOT"] = slot_path
            identities = {name: capture_secure_path(path, allowed_root=self.root)
                          for name, path in paths.items()}
            if read_file_nofollow(slot_path, allowed_root=self.root, maximum_bytes=32000) != canonical(slot):
                raise ValueError("REJECTED_CAPTURE_SLOT_CHANGED")
            documents = {name: receipt.read(name) for name in _DOCUMENTS}
            hashes = {name: sha(canonical(value)) for name, value in documents.items()}
            if hashes["RESULT"] != request.result_sha256:
                raise ValueError("REJECTED_CAPTURE_RESULT_SHA")
            capture, artifact = documents["DISPATCH"], documents["RESULT"]
            closed(capture, {"schema", "grant_sha256", "dispatch_sha256", "request_sha256",
                "preflight_sha256", "namespace_sha256", "grant", "dispatch", "body", "preflight"},
                "REJECTED_CAPTURE_DISPATCH_FIELDS")
            dispatch, grant, proof = capture["dispatch"], slot["grant"], capture["preflight"]
            if not isinstance(dispatch, dict) or not isinstance(grant, dict) or not isinstance(proof, dict):
                raise ValueError("REJECTED_CAPTURE_DISPATCH_TYPES")
            body = capture["body"]
            if (not isinstance(body, str) or len(body.encode()) != request.request_bytes
                    or sha(body.encode()) != request.request_sha256
                    or capture["schema"] != "P0-NORMAL-DISPATCH-CAPTURE-1.0"
                    or capture["grant"] != grant or grant["request_bytes"] != request.request_bytes
                    or sha(canonical(proof)) != request.preflight_sha256
                    or sha(canonical(dispatch)) != capture["dispatch_sha256"]
                    or capture["namespace_sha256"] != slot["namespace_sha256"]
                    or any(capture[key] != value for key, value in expected.items() if key != "permission_sha256")
                    or proof.get("cost_bound_usd") != slot["reserved_usd"]):
                raise ValueError("REJECTED_CAPTURE_DISPATCH_BINDING")
            text = recover_binding(artifact=artifact, grant_sha256=request.grant_sha256,
                request_sha256=request.request_sha256, dispatch_sha256=str(capture["dispatch_sha256"]))
            usage = cast(Mapping[str, object], artifact["usage"])
            for name in _DOCUMENTS[2:]:
                actual = documents[name]
                wanted = receipt.event(name, grant, proof,
                    artifact=request.result_sha256 if name == "RESPONSE_CAPTURED" else None,
                    status="completed" if name == "RESPONSE_CAPTURED" else None,
                    usage=usage if name == "RESPONSE_CAPTURED" else None)
                if (set(actual) != set(wanted)
                        or canonical({key: value for key, value in actual.items() if key != "timestamp_utc"})
                        != canonical({key: value for key, value in wanted.items() if key != "timestamp_utc"})):
                    raise ValueError("REJECTED_CAPTURE_RECEIPT_CHAIN")
                utc(actual["timestamp_utc"])
            # Read again while holding the same original LOCK; never acknowledge or resume.
            if (ledger.slots() != slots or canonical(self.loader()) != canonical(permission)
                    or any(sha(canonical(receipt.read(name))) != value for name, value in hashes.items())
                    or any(not identity.same_identity(capture_secure_path(paths[name], allowed_root=self.root))
                           for name, identity in identities.items())
                    or any(receipt.exists(name) for name in ("UNKNOWN", "PARSED", "CONSUMED"))):
                raise ValueError("REJECTED_CAPTURE_CHANGED_DURING_READ")
            metadata: dict[str, object] = {"observed_utc": datetime.now(UTC).isoformat(),
                "response_status": "completed", "outcome_marker": "PARSING_REJECTED",
                "result_sha256": request.result_sha256, "output_text_sha256": sha(text.encode()),
                "output_text_bytes": len(text.encode()), "receipt_hashes_before": hashes,
                "receipt_hashes_after": dict(hashes), "slot_sha256": sha(canonical(slot)),
                "reserved_usd": slot["reserved_usd"], "usage": dict(usage),
                "billed_cost": "NOT_ESTABLISHED", "provider_attempts": 1,
                "namespace_sha256": slot["namespace_sha256"], "retry_authorized": False}
            result = RejectedCapture(request, dispatch, text, metadata)
        return result
