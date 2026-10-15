"""Application-only OFF reader; original LOCK, no writer API or grant authority."""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha, utc
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt, decode
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    EVENT_ORDER,
    reject_orphan_namespaces,
    validate_events,
    validate_slot,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
    NORMAL_EVENTS,
    P0ContinuityProductLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    REJECTED_FILES,
    BoundChainV2,
    observed_evidence,
    validate_captured_rejection,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_contract import (
    UNKNOWN_FILES,
    disposition_target,
    observation,
    validate_inventory,
    validate_unknown,
)
from backend.core_contracts.outcome import ApplicationFailureKind
from backend.infrastructure.filesystem import capture_secure_path, read_file_nofollow
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionPortError,
)


@dataclass(frozen=True)
class ValidatedUnknownOff:
    plan: Mapping[str, object]
    plan_sha256: str
    chain: BoundChainV2
    manifest: Mapping[str, object]
    disposition: Mapping[str, object]
    tariff: Mapping[str, object]


class P0UnknownOffReader:
    """Only public operation is inspect. No inheritance of ledger writers."""

    def __init__(self, *, loader: Callable[[], ValidatedUnknownOff], plan_sha256: str,
        clock: Callable[[], datetime]) -> None:
        self._loader, self._identity, self._clock = loader, plan_sha256, clock

    def inspect(self, *, inspection_ref: str, expected_plan_or_profile_sha256: str) -> Mapping[str, object]:
        if (inspection_ref != "p1-inspection:" + self._identity
            or expected_plan_or_profile_sha256 != self._identity):
            raise P1CampaignInspectionPortError(ApplicationFailureKind.AF_MAPPING_CORRUPTION)
        try:
            return self._inspect()
        except ValueError as error:
            kind = ApplicationFailureKind.AF_MAPPING_CORRUPTION
            if str(error) == "P0_PRODUCT_CONCURRENT_DISPATCH":
                kind = ApplicationFailureKind.AF_CONCURRENCY
            raise P1CampaignInspectionPortError(kind) from None
        except OSError:
            raise P1CampaignInspectionPortError(ApplicationFailureKind.AF_PORT_UNAVAILABLE) from None

    def _inspect(self) -> Mapping[str, object]:
        loaded: list[ValidatedUnknownOff] = []

        def fresh_chain() -> BoundChainV2:
            context = self._loader()
            if context.plan_sha256 != self._identity:
                raise ValueError("P0_UNKNOWN_OFF_PLAN_CHANGED")
            loaded[:] = [context]
            return context.chain

        initial = self._loader()
        profile = cast(Mapping[str, object], initial.chain.current.envelope["profile"])
        # This object stays private: use only the existing OPEN_EXISTING readonly
        # LOCK and witness/inventory validators, never its inherited writers.
        lock = P0ContinuityProductLedger(root=Path(str(profile["receipt_root"])),
            permission=initial.chain.current.permission, chain_loader=fresh_chain,
            broker_identity=self, clock=self._clock)
        with lock.locked():
            context = loaded[0]
            chain = context.chain
            root, prefix = lock.root, lock.prefix
            selected = disposition_target(context.disposition)
            rejected = cast(Mapping[str, object], chain.disposition["target_attempt"])
            inventory = self._inventory(root)
            records: list[dict[str, object]] = []
            classes: dict[str, str] = {}
            paths = sorted(root.glob(prefix + "*.json"))
            if len(paths) != 3:
                raise ValueError("P0_UNKNOWN_OFF_EXACT_THREE_SLOTS_REQUIRED")
            for path in paths:
                if re.fullmatch(re.escape(prefix) + r"[0-9a-f]{64}\.json", path.name) is None:
                    raise ValueError("P0_PRODUCT_SLOT_NAME")
                raw = read_file_nofollow(path, allowed_root=root, maximum_bytes=32_000)
                record = decode(raw)
                if sha(raw) != sha(canonical(record)):
                    raise ValueError("P0_UNKNOWN_OFF_SLOT_CANONICAL_REQUIRED")
                validate_slot(chain, record, file_name=path.name)
                namespace = str(record["namespace_sha256"])
                receipt = P0NormalReceipt(root, namespace)
                existing = {s for s in NORMAL_EVENTS if receipt.exists(s)}
                if namespace == selected["namespace_sha256"]:
                    if existing != UNKNOWN_FILES:
                        raise ValueError("P0_UNKNOWN_OFF_EXACT_EVENT_SET_REQUIRED")
                    files, hashes = self._files(root, namespace, existing)
                    validate_unknown(chain, record, disposition=context.disposition,
                        files=files, raw_hashes=hashes, tariff=context.tariff)
                    classes[namespace] = "UNKNOWN"
                elif namespace == rejected["namespace_sha256"]:
                    if existing != REJECTED_FILES:
                        raise ValueError("P0_REJECTED_EXACT_EVENT_SET_REQUIRED")
                    files, hashes = self._files(root, namespace, existing)
                    validate_captured_rejection(chain, record, selected=rejected, files=files,
                        raw_hashes=hashes, tariff=context.tariff)
                    observed = observed_evidence(chain, record, files=files, raw_hashes=hashes,
                        selected=rejected, plan_sha256=str(chain.evidence["inspection_plan_sha256"]),
                        orientation=cast(Mapping[str, object], chain.evidence["owner_orientation_adoption"]),
                        diagnostic=cast(Mapping[str, object], chain.evidence["owner_diagnostic"]),
                        now=utc(chain.evidence["timestamp_utc"]))
                    if canonical(observed) != canonical(chain.evidence):
                        raise ValueError("P0_REJECTED_ADOPTED_EVIDENCE_CHANGED")
                    classes[namespace] = "KNOWN_REJECTED"
                else:
                    if existing != {*EVENT_ORDER, "DISPATCH", "RESULT"}:
                        raise ValueError("P0_UNKNOWN_OFF_UNCLASSIFIED_LIFECYCLE")
                    if receipt.confirmed(cast(Mapping[str, object], record["grant"])) is None:
                        raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED")
                    if receipt.read("DISPATCH")["preflight_sha256"] != record["preflight_sha256"]:
                        raise ValueError("P0_CONTINUITY_CAPTURE_SLOT_BINDING")
                    validate_events(record, {s: receipt.read(s) for s in EVENT_ORDER})
                    classes[namespace] = "CONSUMED"
                records.append(record)
            total = validate_inventory(chain, context.manifest, records, classes)
            lock._verify_witness_evidence(chain, records)
            reject_orphan_namespaces(chain, records, normal_namespaces=lock._normal_namespaces())
            # Fresh plan/source/native/adoption checks and same inventory/bytes
            # before releasing the retained exclusive original LOCK.
            final = self._loader()
            if (canonical(final.plan) != canonical(context.plan)
                or canonical(final.manifest) != canonical(context.manifest)
                or canonical(final.disposition) != canonical(context.disposition)
                or canonical(final.chain.manifest) != canonical(chain.manifest)
                or self._inventory(root) != inventory):
                raise ValueError("P0_UNKNOWN_OFF_READ_SET_CHANGED")
            lock.pin._root_unchanged()
            return observation(chain, plan_sha256=self._identity,
                disposition_sha256=sha(canonical(context.disposition)), reserved_budget_usd=total,
                now=self._clock())

    @staticmethod
    def _files(root: Path, namespace: str, states: set[str]) -> tuple[dict[str, Mapping[str, object]], dict[str, str]]:
        files: dict[str, Mapping[str, object]] = {}
        hashes: dict[str, str] = {}
        for state in states:
            raw = read_file_nofollow(root / (namespace + "." + state + ".json"),
                allowed_root=root, maximum_bytes=1_000_000)
            files[state], hashes[state] = decode(raw), sha(raw)
        return files, hashes

    @staticmethod
    def _inventory(root: Path) -> dict[str, tuple[str, int | None, int | None]]:
        paths = sorted(root.glob("*.json"))
        if len(paths) > 1024:
            raise ValueError("P0_CONTINUITY_RECEIPT_INVENTORY_LIMIT")
        result: dict[str, tuple[str, int | None, int | None]] = {}
        for path in paths:
            before = capture_secure_path(path, allowed_root=root)
            pin = sha(read_file_nofollow(path, allowed_root=root, maximum_bytes=1_000_000))
            if not before.same_identity(capture_secure_path(path, allowed_root=root)):
                raise ValueError("P0_UNKNOWN_OFF_READ_SET_CHANGED")
            result[path.name] = (pin, before.device, before.inode)
        return result
