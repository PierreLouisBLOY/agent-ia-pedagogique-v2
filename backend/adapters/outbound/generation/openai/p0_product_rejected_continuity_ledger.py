"""Read-only V2 reconciliation under the retained original Windows LOCK."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha, utc
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt, decode
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    BoundChain,
    allow_own_transition,
    reject_orphan_namespaces,
    validate_events,
    validate_historical_witnesses,
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
    reservation_totals,
    snapshot_v2,
    target,
    validate_captured_rejection,
)
from backend.infrastructure.filesystem import read_file_nofollow


class P0RejectedContinuityLedger(P0ContinuityProductLedger):
    """No new historical writer, lock format, refund or consumed marker."""

    def __init__(
        self,
        *,
        root: Path,
        permission: Mapping[str, object],
        chain_loader: Callable[[], BoundChain],
        broker_identity: object,
        clock: Callable[[], datetime],
        selected: Mapping[str, object],
        tariff: Mapping[str, object],
        orientation: Mapping[str, object],
        diagnostic: Mapping[str, object],
        plan_sha256: str,
    ) -> None:
        super().__init__(
            root=root,
            permission=permission,
            chain_loader=chain_loader,
            broker_identity=broker_identity,
            clock=clock,
        )
        self.selected, self.tariff = dict(target(selected)), dict(tariff)
        self.orientation, self.diagnostic = dict(orientation), dict(diagnostic)
        self.plan_sha256 = plan_sha256
        self._observed: dict[str, object] | None = None

    def slots(self) -> list[dict[str, object]]:
        if self._held_thread != threading.get_ident():
            with self.locked():
                return self.slots()
        chain = self.chain()
        self.pin._root_unchanged()
        records: list[dict[str, object]] = []
        selected_records: list[dict[str, object]] = []
        paths = sorted(self.root.glob(self.prefix + "*.json"))
        if len(paths) > 14:
            raise ValueError("P0_PRODUCT_LEDGER_LIMIT")
        for path in paths:
            if re.fullmatch(re.escape(self.prefix) + r"[0-9a-f]{64}\.json", path.name) is None:
                raise ValueError("P0_PRODUCT_SLOT_NAME")
            record = decode(read_file_nofollow(path, allowed_root=self.root, maximum_bytes=32_000))
            validate_slot(chain, record, file_name=path.name)
            receipt = P0NormalReceipt(self.root, str(record["namespace_sha256"]))
            existing = [state for state in NORMAL_EVENTS if receipt.exists(state)]
            if record["namespace_sha256"] == self.selected["namespace_sha256"]:
                if set(existing) != REJECTED_FILES:
                    raise ValueError("P0_REJECTED_EXACT_EVENT_SET_REQUIRED")
                documents: dict[str, Mapping[str, object]] = {}
                hashes: dict[str, str] = {}
                for state in existing:
                    raw = read_file_nofollow(
                        self.root / (str(record["namespace_sha256"]) + "." + state + ".json"),
                        allowed_root=self.root,
                        maximum_bytes=1_000_000,
                    )
                    documents[state], hashes[state] = decode(raw), sha(raw)
                validate_captured_rejection(
                    chain,
                    record,
                    selected=self.selected,
                    files=documents,
                    raw_hashes=hashes,
                    tariff=self.tariff,
                )
                adopted = chain.evidence if isinstance(chain, BoundChainV2) else None
                observation = observed_evidence(
                    chain,
                    record,
                    files=documents,
                    raw_hashes=hashes,
                    selected=self.selected,
                    plan_sha256=self.plan_sha256,
                    orientation=self.orientation,
                    diagnostic=self.diagnostic,
                    now=self.clock() if adopted is None else utc(adopted["timestamp_utc"]),
                )
                if adopted is not None and canonical(observation) != canonical(adopted):
                    raise ValueError("P0_REJECTED_ADOPTED_EVIDENCE_CHANGED")
                self._observed = observation
                selected_records.append(record)
            elif not existing and allow_own_transition(
                chain,
                record,
                self._pending,
                broker_identity=self.broker_identity,
                dispatch_sha256=str(self._pending_dispatch_sha256),
                now=self.clock(),
                existing_p0_events=existing,
            ):
                records.append(record)
                continue
            else:
                # The normal confirmed() contract and V1 lifecycle stay exact.
                if receipt.confirmed(cast(Mapping[str, object], record["grant"])) is None:
                    raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED")
                capture = receipt.read("DISPATCH")
                if capture["preflight_sha256"] != record["preflight_sha256"]:
                    raise ValueError("P0_CONTINUITY_CAPTURE_SLOT_BINDING")
                validate_events(
                    record,
                    {
                        state: receipt.read(state)
                        for state in (
                            "RESERVED",
                            "PROVIDER_ATTEMPTED",
                            "RESPONSE_CAPTURED",
                            "PARSED",
                            "CONSUMED",
                        )
                    },
                )
            records.append(record)
        if len(selected_records) != 1:
            raise ValueError("P0_REJECTED_TARGET_MISSING_OR_DUPLICATE")
        validate_historical_witnesses(chain, records)
        self._verify_witness_evidence(chain, records)
        reject_orphan_namespaces(chain, records, normal_namespaces=self._normal_namespaces())
        reservation_totals(chain, records)
        self.pin._root_unchanged()
        return records

    def snapshot(self) -> dict[str, object]:
        with self.locked():
            records = self.slots()
            chain = self.chain()
            if not isinstance(chain, BoundChainV2):
                raise ValueError("P0_REJECTED_ADOPTED_CHAIN_REQUIRED")
            return snapshot_v2(chain, records, now=self.clock())

    def bootstrap(self) -> dict[str, object]:
        with self.locked():
            records = self.slots()
            chain = self.chain()
            if isinstance(chain, BoundChainV2) or self._observed is None:
                raise ValueError("P0_REJECTED_INSPECTION_PLAN_REQUIRED")
            count, total, _ = reservation_totals(chain, records)
            return {
                "schema": "P0-PRODUCT-REJECTED-OBSERVATION-1.0",
                "state": "OBSERVED_NOT_ADOPTED",
                "timestamp_utc": self.clock().isoformat(),
                "observed_evidence": dict(self._observed),
                "observed_evidence_sha256": sha(canonical(self._observed)),
                "campaign_namespace_sha256": chain.manifest["campaign_namespace_sha256"],
                "root_permission_sha256": chain.root.permission_sha256,
                "observed_slots_reserved": count,
                "observed_reserved_budget_usd": str(total),
                "consumed_count": count - 1,
                "known_rejected_count": 1,
                "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
                "live_enabled": False,
                "provider_calls": 0,
                "ledger_mutations": 0,
                "inspection_plan_sha256": self.plan_sha256,
            }

    def inspect(
        self, *, inspection_ref: str, expected_plan_or_profile_sha256: str
    ) -> Mapping[str, object]:
        expected = self.plan_sha256
        if (
            inspection_ref != "p1-inspection:" + expected
            or expected_plan_or_profile_sha256 != expected
        ):
            raise ValueError("P0_REJECTED_INSPECTION_IDENTITY")
        # The Application query transforms full private descriptors to logical
        # references. The native reader must preserve the full evidence hash.
        return (
            self.snapshot() if isinstance(self.chain_loader(), BoundChainV2) else self.bootstrap()
        )
