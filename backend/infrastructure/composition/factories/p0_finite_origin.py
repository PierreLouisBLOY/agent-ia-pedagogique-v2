"""Scoped read over the already authenticated normal origin; never a server."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from backend.adapters.inbound.application.p0_finite_origin import FiniteOriginInbound
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    validate_events,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.infrastructure.composition.factories.p0_normal_profile import (
    P0NormalProductComposition,
)
from backend.infrastructure.filesystem import capture_secure_path, hash_file_nofollow
from backend.modules.work_orchestration.application.queries.p0_finite_origin import ReadFiniteOrigin


class _OriginRead:
    def __init__(self, normal: P0NormalProductComposition) -> None:
        if normal.mode != "evidence-only" or normal.has_resolver or normal.generation is not None:
            raise ValueError("P0_CHAIN_ORIGIN_READONLY_REQUIRED")
        if normal.continuity:
            raise ValueError("P0_CHAIN_CONTINUITY_READ_SCOPE_REQUIRED")
        self.normal = normal

    def inspect_readonly(self) -> Mapping[str, object]:
        normal = self.normal
        normal.identities()
        ledger = P0ProductLedger(root=normal.root, permission=normal.permission)
        rows = []
        with ledger.locked(create=False):
            lock = normal.root / (ledger.prefix + "LOCK")
            native = capture_secure_path(lock, allowed_root=normal.root)
            slots = ledger.slots()
            for slot in slots:
                receipt = P0NormalReceipt(normal.root, str(slot["namespace_sha256"]))
                names = (
                    "RESERVED",
                    "PROVIDER_ATTEMPTED",
                    "RESPONSE_CAPTURED",
                    "PARSED",
                    "CONSUMED",
                    "UNKNOWN",
                    "PARSING_REJECTED",
                    "DISPATCH",
                    "RESULT",
                )
                markers = {
                    name: hash_file_nofollow(receipt._path(name), allowed_root=normal.root)
                    if receipt.exists(name)
                    else None
                    for name in names
                }
                complete = False
                try:
                    if receipt.confirmed(cast(Mapping[str, object], slot["grant"])) is not None:
                        validate_events(slot, {name: receipt.read(name) for name in names[:5]})
                        complete = True
                except (ValueError, FileNotFoundError):
                    pass
                snapshot = {
                    "schema": "P0-FINITE-RETAINED-ORIGIN-1.0",
                    "disposition": "RETAIN_UNCERTAINTY_NO_REPLAY",
                    "slot_sha256": sha(canonical(slot)),
                    **{
                        k: slot[k]
                        for k in (
                            "permission_sha256",
                            "namespace_sha256",
                            "grant_sha256",
                            "request_sha256",
                            "reserved_usd",
                        )
                    },
                    "markers_sha256": markers,
                }
                rows.append(
                    {
                        "slot": slot,
                        "confirmed_lifecycle": complete,
                        "lifecycle_snapshot": snapshot,
                        "disposition_adopted": False,
                    }
                )
            result = {
                "schema": "P0-FINITE-ORIGIN-OBSERVATION-1.0",
                "authority": "NONE",
                "historical_writes": 0,
                "observed_at_utc": datetime.now(UTC).isoformat(),
                "normal_permission_sha256": ledger.permission_sha256,
                "normal_envelope_sha256": normal.envelope_sha256,
                "campaign_namespace_sha256": normal.permission["permission_namespace_sha256"],
                "receipt_root_sha256": normal.permission["receipt_root_sha256"],
                "root_lock_sha256": ledger._held_lock_sha256,
                "root_lock_identity_sha256": sha(
                    canonical({"device": native.device, "inode": native.inode})
                ),
                "scope": "THIS_CAMPAIGN_ONLY_NOT_GLOBAL_BILLING",
                "slots": rows,
            }
        return result


def build_finite_origin_reader(normal: P0NormalProductComposition) -> FiniteOriginInbound:
    return FiniteOriginInbound(ReadFiniteOrigin(_OriginRead(normal)))
