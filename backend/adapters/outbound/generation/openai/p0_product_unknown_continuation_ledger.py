"""One operational addition under the original LOCK; frozen UNKNOWN stays counted."""
from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, money
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt, decode
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    EVENT_ORDER,
    allow_own_transition,
    reject_orphan_namespaces,
    validate_events,
    validate_slot,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import NORMAL_EVENTS
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    REJECTED_FILES,
    observed_evidence,
    reservation_totals,
    validate_captured_rejection,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_ledger import (
    P0RejectedContinuityLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_continuation_contract import (
    UnknownContinuation,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_contract import (
    UNKNOWN_FILES,
    validate_inventory,
    validate_unknown,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    P0UnknownOffReader,
)
from backend.infrastructure.filesystem import read_file_nofollow


class P0UnknownContinuationLedger(P0RejectedContinuityLedger):
    def __init__(self, *, operation_context: Callable[[], UnknownContinuation], **kwargs: object) -> None:
        self.operation_context = operation_context
        super().__init__(**kwargs)  # type: ignore[arg-type]

    def _history(self, context: UnknownContinuation) -> dict[str, tuple[str, int, int]]:
        inventory = P0UnknownOffReader._inventory(self.root)
        frozen = cast(list[Mapping[str, object]], context.history["frozen_inventory"])
        for row in frozen:
            if inventory.get(str(row["name"])) != (row["sha256"], row["device"], row["inode"]):
                raise ValueError("P1_UNKNOWN_FROZEN_HISTORY_CHANGED")
        return cast(dict[str, tuple[str, int, int]], inventory)

    def slots(self) -> list[dict[str, object]]:
        if self._held_thread != threading.get_ident():
            with self.locked():
                return self.slots()
        chain = self.chain()
        context = self.operation_context()
        if canonical(chain.current.permission) != canonical(context.current_chain.current.permission):
            raise ValueError("P1_UNKNOWN_CURRENT_ORIGIN_CHANGED")
        inventory = self._history(context)
        frozen = {str(row["name"]) for row in cast(list[Mapping[str, object]], context.history["frozen_inventory"])}
        expected = cast(list[Mapping[str, object]], context.historical_manifest["expected_slots"])
        classes_by_ns = {str(row["namespace_sha256"]): str(row["classification"]) for row in expected}
        records: list[dict[str, object]] = []
        historical: list[dict[str, object]] = []
        classes: dict[str, str] = {}
        additions: list[dict[str, object]] = []
        for path in sorted(self.root.glob(self.prefix + "*.json")):
            if re.fullmatch(re.escape(self.prefix) + r"[0-9a-f]{64}\.json", path.name) is None:
                raise ValueError("P0_PRODUCT_SLOT_NAME")
            raw = read_file_nofollow(path, allowed_root=self.root, maximum_bytes=32_000)
            record = decode(raw)
            if raw != canonical(record):
                raise ValueError("P1_UNKNOWN_SLOT_CANONICAL_REQUIRED")
            namespace = str(record["namespace_sha256"])
            receipt = P0NormalReceipt(self.root, namespace)
            existing = {state for state in NORMAL_EVENTS if receipt.exists(state)}
            category = classes_by_ns.get(namespace)
            if category is not None:
                validate_slot(context.historical_chain, record, file_name=path.name)
                if category == "UNKNOWN":
                    if existing != UNKNOWN_FILES:
                        raise ValueError("P0_UNKNOWN_OFF_EXACT_EVENT_SET_REQUIRED")
                    files, pins = P0UnknownOffReader._files(self.root, namespace, existing)
                    validate_unknown(context.historical_chain, record, disposition=context.unknown_disposition,
                        files=files, raw_hashes=pins, tariff=self.tariff)
                elif category == "KNOWN_REJECTED":
                    if existing != REJECTED_FILES:
                        raise ValueError("P0_REJECTED_EXACT_EVENT_SET_REQUIRED")
                    files, pins = P0UnknownOffReader._files(self.root, namespace, existing)
                    validate_captured_rejection(context.historical_chain, record, selected=self.selected,
                        files=files, raw_hashes=pins, tariff=self.tariff)
                    evidence = context.historical_chain.evidence
                    observed = observed_evidence(context.historical_chain, record, files=files, raw_hashes=pins,
                        selected=self.selected, plan_sha256=str(evidence["inspection_plan_sha256"]),
                        orientation=cast(Mapping[str, object], evidence["owner_orientation_adoption"]),
                        diagnostic=cast(Mapping[str, object], evidence["owner_diagnostic"]),
                        now=self._historical_stamp(evidence))
                    if canonical(observed) != canonical(evidence):
                        raise ValueError("P0_REJECTED_ADOPTED_EVIDENCE_CHANGED")
                else:
                    self._confirmed(record, receipt, existing)
                historical.append(record)
                classes[namespace] = category
            else:
                validate_slot(chain, record, file_name=path.name)
                self._own_binding(record, context)
                if not existing and allow_own_transition(chain, record, self._pending,
                    broker_identity=self.broker_identity, dispatch_sha256=str(self._pending_dispatch_sha256),
                    now=self.clock(), existing_p0_events=tuple(existing)):
                    pass
                else:
                    self._confirmed(record, receipt, existing)
                additions.append(record)
            records.append(record)
        validate_inventory(context.historical_chain, context.historical_manifest, historical, classes)
        if len(additions) > 1 or len(records) != 3 + len(additions):
            raise ValueError("P1_UNKNOWN_ONE_ADDITION_ONLY")
        if additions:
            namespace = str(additions[0]["namespace_sha256"])
            allowed = {self.prefix + str(additions[0]["preview_sha256"]) + ".json"}
            allowed |= {namespace + "." + state + ".json" for state in NORMAL_EVENTS}
        else:
            allowed = set()
        if set(inventory) - frozen - allowed:
            raise ValueError("P1_UNKNOWN_UNCLASSIFIED_ADDITION")
        self._verify_witness_evidence(chain, records)
        reject_orphan_namespaces(chain, records, normal_namespaces=self._normal_namespaces())
        reservation_totals(chain, records)
        if P0UnknownOffReader._inventory(self.root) != inventory:
            raise ValueError("P1_UNKNOWN_HISTORY_READ_SET_CHANGED")
        self.pin._root_unchanged()
        return records

    @staticmethod
    def _historical_stamp(evidence: Mapping[str, object]) -> datetime:
        from backend.adapters.outbound.generation.openai.p0_normal_policy import utc
        return utc(evidence["timestamp_utc"])

    @staticmethod
    def _confirmed(record: Mapping[str, object], receipt: P0NormalReceipt, existing: set[str]) -> None:
        if existing != {*EVENT_ORDER, "DISPATCH", "RESULT"}:
            raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED")
        if receipt.confirmed(cast(Mapping[str, object], record["grant"])) is None:
            raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED")
        if receipt.read("DISPATCH")["preflight_sha256"] != record["preflight_sha256"]:
            raise ValueError("P0_CONTINUITY_CAPTURE_SLOT_BINDING")
        validate_events(record, {state: receipt.read(state) for state in EVENT_ORDER})

    def _own_binding(self, record: Mapping[str, object], context: UnknownContinuation) -> None:
        intent = context.intent
        grant = cast(Mapping[str, object], record["grant"])
        if (record["permission_sha256"] != context.current_chain.current.permission_sha256
            or any(grant[k] != intent[k] for k in ("request_sha256", "request_bytes", "preparation_sha256",
                "context_sha256", "reference_set_sha256"))
            or money(record["reserved_usd"]) != money(intent["cost_bound_usd"])):
            raise ValueError("P1_UNKNOWN_EXACT_NEW_OPERATION_REQUIRED")

    def require_available(self) -> None:
        if len(self.slots()) != 3:
            raise ValueError("P1_UNKNOWN_OPERATION_ALREADY_RESERVED")

    def reserve(self, *, grant: Mapping[str, object], preview_sha256: str, command_id: str,
        preflight: Mapping[str, object]) -> None:
        self.chain()  # A caller cannot reserve without the retained original LOCK.
        self.require_available()
        record = {"grant": grant, "permission_sha256": self.permission_sha256,
            "reserved_usd": preflight["cost_bound_usd"]}
        self._own_binding(record, self.operation_context())
        super().reserve(grant=grant, preview_sha256=preview_sha256, command_id=command_id, preflight=preflight)

    def snapshot(self) -> dict[str, object]:
        with self.locked():
            records = self.slots()
            chain = self.chain()
            _, total, _ = reservation_totals(chain, records)
            historical_namespaces = {str(row["namespace_sha256"]) for row in
                cast(list[Mapping[str, object]], self.operation_context().historical_manifest["expected_slots"])}
            confirmed_new = sum(P0NormalReceipt(self.root, str(r["namespace_sha256"])).exists("CONSUMED")
                for r in records if str(r["namespace_sha256"]) not in historical_namespaces)
            return {"schema": "P0-UNKNOWN-CONTINUITY-SNAPSHOT-1.0", "state": "PRESERVED_HISTORY_NO_EFFECT_AUTHORITY",
                "timestamp_utc": self.clock().isoformat(), "slots_reserved": len(records),
                "consumed_count": 1 + confirmed_new, "known_rejected_count": 1, "unknown_count": 1,
                "pending_count": len(records) - 3 - confirmed_new,
                "reserved_budget_usd": str(total), "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
                "actual_billed_cost_status": "NOT_ESTABLISHED", "effect_permitted": False,
                "course_qualification": "NOT_COMPLETED"}
