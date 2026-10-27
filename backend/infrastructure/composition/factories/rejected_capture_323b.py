"""Owner-scoped local 7c99 read factory. No SDK, credential, server or effect."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from backend.adapters.inbound.application.rejected_capture import RejectedCaptureInbound
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.persistence.rejected_capture import NormalRejectedCaptureReader
from backend.infrastructure.composition.factories.p0_normal_profile import read_descriptor
from backend.modules.work_orchestration.application.queries.read_rejected_capture import (
    ReadRejectedCapture,
)
from backend.modules.work_orchestration.contracts.dto.rejected_capture import RejectedCaptureRequest

TARGET = RejectedCaptureRequest("7c99b1cf465a4ed5a5b445f71e8b4493",
    "09e11ecba8b214bd70fc4460aecd5ae24797e1460a5faf7153cbf0d1204a7491",
    "4ad6e9b4e585eacb79505c635a5d87e41cc28499212a93eb51660ca0787b647b", 10826,
    "a9bc7b17789f2e31d9c21e77dcefb5305ea65c10d363271d8737bd124e42021a",
    "daa30097ae74080a4881335ed6c749efcb0acf1fdf25c4e9c400a33c1546a346",
    "52967b4cf2c8fdbe57acd8c0350e4c14f8b7f0edae391f9e4ff8bf70eb0f0141")
ENVELOPE_SHA256 = "a242e819bd708eafc477cb4c1b782e634ed78c33b8dc5f046713b7fef6cac859"


def compose_rejected_capture_323b(envelope_path: Path) -> RejectedCaptureInbound:
    descriptor = {"path": str(envelope_path), "sha256": ENVELOPE_SHA256}

    def permission() -> Mapping[str, object]:
        envelope = cast(dict[str, object], read_descriptor(descriptor))
        value = cast(dict[str, object], read_descriptor(envelope["permission"]))
        decision = cast(dict[str, object], read_descriptor(envelope["decision"]))
        profile = cast(dict[str, object], envelope["profile"])
        if (sha(canonical(value)) != TARGET.permission_sha256
                or decision.get("status") != "ADOPTED"
                or value.get("model") != "gpt-5.6-terra"
                or profile.get("schema") != "P0-NORMAL-PROFILE-1.0"
                or value.get("profile_sha256") != sha(canonical(profile))
                or value.get("owner_decision_sha256") != sha(canonical(decision))):
            raise ValueError("REJECTED_CAPTURE_323B_ADOPTED_BINDING")
        return value

    permission()
    envelope = cast(dict[str, object], read_descriptor(descriptor))
    profile = cast(dict[str, object], envelope["profile"])
    reader = NormalRejectedCaptureReader(root=Path(str(profile["receipt_root"])),
        permission_loader=permission, binding=TARGET)
    return RejectedCaptureInbound(ReadRejectedCapture(reader, TARGET))
