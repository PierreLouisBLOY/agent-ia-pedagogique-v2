"""One same-need pilot child under the retained P1 LOCK and frozen history.

Only the outbound adapter owns paths.  This ledger never repairs, removes or
reclassifies a historical receipt, and an orphan child always consumes capacity.
"""
from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    HASH_FIELDS,
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
    validate_grant,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt, decode
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    EVENT_FIELDS,
    EVENT_ORDER,
    validate_events,
    validate_slot,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
    NORMAL_EVENTS,
    P0ContinuityProductLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import (
    SLOT_FIELDS,
    P0ProductLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    REJECTED_FILES,
    BoundChainV2,
    observed_evidence,
    validate_captured_rejection,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_contract import (
    UNKNOWN_FILES,
    validate_inventory,
    validate_unknown,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    P0UnknownOffReader,
    ValidatedUnknownOff,
)
from backend.adapters.outbound.persistence.p0_pilot_incident import P0PilotIncidentDisposition
from backend.infrastructure.filesystem import read_file_nofollow


class P0PilotMixedLedger(P0ProductLedger):
    """The original chain proves history; a separate permission owns one child."""

    def __init__(self, *, root: Path, permission: Mapping[str, object],
                 historical: Callable[[], ValidatedUnknownOff],
                 frozen_inventory: Sequence[Mapping[str, object]],
                 frozen_inventory_sha256: str,
                 candidate_request_sha256: str,
                 candidate_preparation_sha256: str,
                 candidate_context_sha256: str,
                 candidate_reference_set_sha256: str,
                 clock: Callable[[], datetime], broker_identity: object,
                 historical_extras: Sequence[Mapping[str, object]] = (),
                 incident: P0PilotIncidentDisposition | None = None) -> None:
        super().__init__(root=root, permission=permission)
        self._historical, self._clock, self._broker_identity = historical, clock, broker_identity
        self._candidate = (candidate_request_sha256, candidate_preparation_sha256,
            candidate_context_sha256, candidate_reference_set_sha256)
        self.incident = incident
        self.base_slots_count = incident.base_slots_count if incident is not None else 3
        if any(not digest(pin) for pin in self._candidate):
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        self._frozen = [dict(row) for row in frozen_inventory]
        self._extras = [dict(row) for row in historical_extras]
        if (len(self._frozen) != 20 or not digest(frozen_inventory_sha256)
            or len({str(row.get("name")) for row in self._frozen}) != 20
            or any(set(row) != {"name", "sha256", "device", "inode"}
                or type(row["name"]) is not str
                or not digest(row["sha256"])
                or any(type(row[key]) is not int or cast(int, row[key]) <= 0 for key in ("device", "inode"))
                for row in self._frozen)):
            raise ValueError("P1_PILOT_FROZEN_INVENTORY_REQUIRED")
        # The owner receipt hashes the native inventory keyed by file name;
        # frozen_inventory is its separately serialized list projection.
        acquired = {str(row["name"]): [row["sha256"], row["device"], row["inode"]]
            for row in self._frozen}
        if sha(canonical(acquired)) != frozen_inventory_sha256:
            raise ValueError("P1_PILOT_FROZEN_INVENTORY_REQUIRED")
        if (len(self._extras) > 3 or any(set(row) != {"name", "sha256", "device", "inode"}
            or re.fullmatch(r"p0-diagnostic\.[0-9a-f]{64}\.json", str(row["name"])) is None
            or not digest(row["sha256"])
            or any(type(row[key]) is not int or cast(int, row[key]) <= 0 for key in ("device", "inode"))
            for row in self._extras)
            or len({str(row["name"]) for row in self._frozen + self._extras}) !=
                len(self._frozen) + len(self._extras)):
            raise ValueError("P1_PILOT_HISTORICAL_DIAGNOSTIC_PIN_REQUIRED")
        first = historical()
        if first.chain.manifest["campaign_namespace_sha256"] != permission["permission_namespace_sha256"]:
            raise ValueError("P1_PILOT_CAMPAIGN_CHANGED")
        self._origin = P0ContinuityProductLedger(root=root, permission=first.chain.current.permission,
            chain_loader=lambda: historical().chain, broker_identity=self, clock=clock)
        self._held_thread: int | None = None
        self._pending: tuple[object, str, str, str, str, str] | None = None

    @contextmanager
    def locked(self, *, create: bool = True) -> Iterator[None]:
        if self._held_thread == threading.get_ident():
            raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
        # The continuity adapter still requires the original existing LOCK.
        with self._origin.locked(create=create):
            self._held_thread = threading.get_ident()
            try:
                yield
            finally:
                self._held_thread = None

    def _require_lock(self) -> None:
        if self._held_thread != threading.get_ident():
            raise ValueError("P1_PILOT_ORIGINAL_LOCK_REQUIRED")
        self._origin.chain()

    def _history(self, context: ValidatedUnknownOff) -> tuple[list[dict[str, object]],
                                                               dict[str, tuple[str, int | None, int | None]]]:
        chain = self._origin.chain()
        if not isinstance(chain, BoundChainV2):
            raise ValueError("P1_PILOT_HISTORICAL_CHAIN_REQUIRED")
        if canonical(context.chain.manifest) != canonical(chain.manifest):
            raise ValueError("P1_PILOT_HISTORY_CHANGED")
        inventory = P0UnknownOffReader._inventory(self.root)
        for row in self._frozen + self._extras:
            if inventory.get(str(row["name"])) != (row["sha256"], row["device"], row["inode"]):
                raise ValueError("P1_PILOT_FROZEN_HISTORY_CHANGED")
        selected = cast(Mapping[str, object], context.disposition["target_attempt"])
        rejected = cast(Mapping[str, object], chain.disposition["target_attempt"])
        records: list[dict[str, object]] = []
        classes: dict[str, str] = {}
        for path in sorted(self.root.glob(self.prefix + "*.json")):
            if re.fullmatch(re.escape(self.prefix) + r"[0-9a-f]{64}\.json", path.name) is None:
                raise ValueError("P0_PRODUCT_SLOT_NAME")
            raw = read_file_nofollow(path, allowed_root=self.root, maximum_bytes=32_000)
            record = decode(raw)
            retained = self.incident.retained() if self.incident is not None else ()
            pinned = next((item for item in retained if path == item.slot_path()), None)
            if pinned is not None:
                if sha(raw) != pinned.sources["slot"]:
                    raise ValueError("P1_PILOT_INCIDENT_SLOT_CHANGED")
                continue
            namespace = str(record["namespace_sha256"])
            if namespace not in {selected["namespace_sha256"], rejected["namespace_sha256"]}:
                # The confirmed third slot is identified by its old permission,
                # never by the child's new permission or a guessed namespace.
                if record.get("permission_sha256") == self.permission_sha256:
                    continue
            validate_slot(chain, record, file_name=path.name)
            receipt = P0NormalReceipt(self.root, namespace)
            existing = {state for state in NORMAL_EVENTS if receipt.exists(state)}
            if namespace == selected["namespace_sha256"]:
                if existing != UNKNOWN_FILES:
                    raise ValueError("P1_PILOT_PARENT_UNKNOWN_CHANGED")
                files, hashes = P0UnknownOffReader._files(self.root, namespace, existing)
                validate_unknown(chain, record, disposition=context.disposition,
                    files=files, raw_hashes=hashes, tariff=context.tariff)
                classes[namespace] = "UNKNOWN"
            elif namespace == rejected["namespace_sha256"]:
                if existing != REJECTED_FILES:
                    raise ValueError("P1_PILOT_REJECTED_HISTORY_CHANGED")
                files, hashes = P0UnknownOffReader._files(self.root, namespace, existing)
                validate_captured_rejection(chain, record, selected=rejected,
                    files=files, raw_hashes=hashes, tariff=context.tariff)
                evidence = chain.evidence
                observed = observed_evidence(chain, record, files=files, raw_hashes=hashes,
                    selected=rejected, plan_sha256=str(evidence["inspection_plan_sha256"]),
                    orientation=cast(Mapping[str, object], evidence["owner_orientation_adoption"]),
                    diagnostic=cast(Mapping[str, object], evidence["owner_diagnostic"]),
                    now=utc(evidence["timestamp_utc"]))
                if canonical(observed) != canonical(evidence):
                    raise ValueError("P1_PILOT_REJECTED_EVIDENCE_CHANGED")
                classes[namespace] = "KNOWN_REJECTED"
            else:
                if existing != {*EVENT_ORDER, "DISPATCH", "RESULT"}:
                    raise ValueError("P1_PILOT_CONSUMED_HISTORY_CHANGED")
                if receipt.confirmed(cast(Mapping[str, object], record["grant"])) is None:
                    raise ValueError("P1_PILOT_CONSUMED_HISTORY_CHANGED")
                if receipt.read("DISPATCH")["preflight_sha256"] != record["preflight_sha256"]:
                    raise ValueError("P1_PILOT_CONSUMED_HISTORY_CHANGED")
                validate_events(record, {state: receipt.read(state) for state in EVENT_ORDER})
                classes[namespace] = "CONSUMED"
            records.append(record)
        validate_inventory(chain, context.manifest, records, classes)
        self._origin._verify_witness_evidence(chain, records)
        return records, inventory

    def _child(self, record: Mapping[str, object], *, file_name: str,
               existing: set[str], expected_permission: Mapping[str, object] | None = None,
               parked: bool = False, retained_empty: bool = False) -> None:
        permission = self.permission if expected_permission is None else expected_permission
        permission_sha256 = sha(canonical(permission))
        closed(record, SLOT_FIELDS, "P1_PILOT_CHILD_SLOT_FIELDS")
        grant = record["grant"]
        if not isinstance(grant, Mapping):
            raise ValueError("P1_PILOT_CHILD_GRANT_REQUIRED")
        if (record["schema"] != "P0-PRODUCT-BUDGET-SLOT-1.0"
            or record["permission_sha256"] != permission_sha256
            or record["grant_sha256"] != sha(canonical(grant))
            or record["namespace_sha256"] != grant.get("namespace_sha256")
            or record["request_sha256"] != grant.get("request_sha256")
            or file_name != self.prefix + str(record["preview_sha256"]) + ".json"
            or any(not digest(record[key]) for key in
                ("preview_sha256", "grant_sha256", "namespace_sha256", "request_sha256", "preflight_sha256"))
            or not isinstance(record["command_id"], str)
            or re.fullmatch(r"[0-9a-f]{32}", str(record["command_id"])) is None
            or any(grant.get(key) != permission[key] for key in
                (HASH_FIELDS & permission.keys()) | {"baseline_commit"})
            or tuple(grant.get(key) for key in ("request_sha256", "preparation_sha256",
                "context_sha256", "reference_set_sha256")) != self._candidate
            or money(record["reserved_usd"]) > money(permission["per_call_ceiling_usd"])):
            raise ValueError("P1_PILOT_CHILD_SLOT_BINDING")
        validate_grant(grant, identities={key: grant[key] for key in
            HASH_FIELDS | {"baseline_commit", "request_bytes"}}, now=utc(grant["issued_at_utc"]))
        receipt = P0NormalReceipt(self.root, str(record["namespace_sha256"]))
        pending = self._pending
        live = (pending is not None and pending[0] is self._broker_identity
            and pending[1:] == (str(record["command_id"]), str(record["grant_sha256"]),
                str(record["namespace_sha256"]), str(record["preflight_sha256"]),
                str(record["request_sha256"]))
            and self._held_thread == threading.get_ident()
            and self._clock() < utc(grant["expires_at_utc"]))
        if not existing:
            if not live and not retained_empty:
                raise ValueError("P1_PILOT_ORPHAN_CHILD_STOP")
            return
        # A terminal UNKNOWN never becomes a free slot or a success, even if
        # a response artifact had already been published before an interruption.
        if "UNKNOWN" in existing:
            if (not {"RESERVED", "DISPATCH", "UNKNOWN"} <= existing
                or existing - {"RESERVED", "DISPATCH", "PROVIDER_ATTEMPTED",
                    "RESULT", "RESPONSE_CAPTURED", "UNKNOWN"}):
                raise ValueError("P1_PILOT_CHILD_OUTCOME_AMBIGUOUS")
        elif "PARSING_REJECTED" in existing:
            if existing != {"RESERVED", "DISPATCH", "PROVIDER_ATTEMPTED",
                "RESULT", "RESPONSE_CAPTURED", "PARSING_REJECTED"}:
                raise ValueError("P1_PILOT_CHILD_OUTCOME_AMBIGUOUS")
        elif "CONSUMED" in existing:
            if existing != {*EVENT_ORDER, "DISPATCH", "RESULT"}:
                raise ValueError("P1_PILOT_CHILD_OUTCOME_AMBIGUOUS")
            if receipt.confirmed(grant) is None:
                raise ValueError("P1_PILOT_CHILD_OUTCOME_AMBIGUOUS")
            validate_events(record, {state: receipt.read(state) for state in EVENT_ORDER})
        elif not live and not (parked and existing == {"RESERVED", "DISPATCH"}):
            raise ValueError("P1_PILOT_ORPHAN_CHILD_STOP")
        if "DISPATCH" not in existing:
            if existing == {"RESERVED"} and live:
                return
            raise ValueError("P1_PILOT_CHILD_DISPATCH_MISSING")
        capture = receipt.read("DISPATCH")
        proof = capture.get("preflight")
        if (not isinstance(proof, Mapping)
            or capture.get("schema") != "P0-NORMAL-DISPATCH-CAPTURE-1.0"
            or capture.get("grant") != grant
            or capture.get("grant_sha256") != record["grant_sha256"]
            or capture.get("request_sha256") != record["request_sha256"]
            or capture.get("namespace_sha256") != record["namespace_sha256"]
            or capture.get("preflight_sha256") != record["preflight_sha256"]
            or sha(canonical(proof)) != record["preflight_sha256"]
            or not isinstance(capture.get("body"), str)
            or sha(str(capture["body"]).encode()) != record["request_sha256"]
            or len(str(capture["body"]).encode()) != grant["request_bytes"]):
            raise ValueError("P1_PILOT_CHILD_PREFLIGHT_CHANGED")
        artifact: Mapping[str, object] | None = None
        if "RESULT" in existing:
            artifact = receipt.read("RESULT")
            if (artifact.get("schema") != "P0-NORMAL-CONFIRMED-RESULT-1.0"
                or artifact.get("grant_sha256") != record["grant_sha256"]
                or artifact.get("request_sha256") != record["request_sha256"]
                or artifact.get("dispatch_sha256") != capture.get("dispatch_sha256")
                or not isinstance(artifact.get("usage"), Mapping)):
                raise ValueError("P1_PILOT_CHILD_RESULT_CHANGED")
        previous = utc(grant["issued_at_utc"])
        ordered = ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED",
            "CONSUMED", "PARSING_REJECTED", "UNKNOWN")
        for state in ordered:
            if state not in existing:
                continue
            event = receipt.read(state)
            closed(event, EVENT_FIELDS, "P1_PILOT_CHILD_EVENT_FIELDS")
            stamp = utc(event["timestamp_utc"])
            attempted = 0 if state == "RESERVED" else (0 if state == "UNKNOWN" and
                "PROVIDER_ATTEMPTED" not in existing else 1)
            status = artifact.get("response_status") if state == "RESPONSE_CAPTURED" and artifact else None
            usage = artifact.get("usage") if state == "RESPONSE_CAPTURED" and artifact else None
            expected = receipt.event(state, grant, proof,
                artifact=sha(canonical(artifact)) if state == "RESPONSE_CAPTURED" and artifact else None,
                status=cast(str | None, status), usage=cast(Mapping[str, object] | None, usage),
                provider_attempts=attempted)
            if (event.get("schema") != "P0-NORMAL-TECHNICAL-RECEIPT-1.0"
                or event.get("state") != state or event.get("grant_sha256") != record["grant_sha256"]
                or event.get("request_sha256") != record["request_sha256"]
                or event.get("preflight_sha256") != record["preflight_sha256"]
                or event.get("namespace_sha256") != record["namespace_sha256"]
                or money(event.get("reserved_usd")) != money(record["reserved_usd"])
                or any(event[key] != expected[key] for key in EVENT_FIELDS - {"timestamp_utc"})
                or not previous <= stamp < utc(grant["expires_at_utc"])):
                raise ValueError("P1_PILOT_CHILD_RECEIPT_CHANGED")
            previous = stamp

    def slots(self) -> list[dict[str, object]]:
        if self._held_thread != threading.get_ident():
            with self.locked():
                return self.slots()
        self._require_lock()
        context = self._historical()
        historical, inventory = self._history(context)
        prior: list[dict[str, object]] = []
        for retained in (self.incident.retained() if self.incident is not None else ()):
            # The old child is pinned by its own permission and retained
            # receipts. Its reservation is never credited to the new call.
            retained.read()
            docs = retained.sources_checked()
            old = docs["slot"]
            if old["permission_sha256"] == self.permission_sha256:
                raise ValueError("P1_PILOT_INCIDENT_PERMISSION_REUSED")
            namespace = str(old["namespace_sha256"])
            receipt = P0NormalReceipt(self.root, namespace)
            existing = {state for state in NORMAL_EVENTS if receipt.exists(state)}
            if existing != retained.expected_events:
                raise ValueError("P1_PILOT_INCIDENT_RECEIPTS_CHANGED")
            self._child(old, file_name=retained.slot_path().name,
                existing=existing, expected_permission=docs["prior_permission"],
                parked=True, retained_empty=not retained.expected_events)
            prior.append(old)
        children = []
        for path in sorted(self.root.glob(self.prefix + "*.json")):
            record = decode(read_file_nofollow(path, allowed_root=self.root, maximum_bytes=32_000))
            if record["permission_sha256"] != self.permission_sha256:
                continue
            namespace = str(record["namespace_sha256"])
            receipt = P0NormalReceipt(self.root, namespace)
            existing = {state for state in NORMAL_EVENTS if receipt.exists(state)}
            self._child(record, file_name=path.name, existing=existing)
            children.append(record)
        if len(historical) != 3 or len(children) > 1:
            raise ValueError("P1_PILOT_ONE_CHILD_ONLY")
        frozen = {str(row["name"]) for row in self._frozen + self._extras}
        allowed: set[str] = set()
        for retained, old in zip(
                self.incident.retained() if self.incident is not None else (), prior, strict=True):
            namespace = str(old["namespace_sha256"])
            if self.incident is None:
                raise ValueError("P1_PILOT_INCIDENT_DISPOSITION_REQUIRED")
            allowed.add(retained.slot_path().name)
            allowed |= {namespace + "." + state + ".json" for state in NORMAL_EVENTS}
            allowed.add("p0-diagnostic." + namespace + ".json")
        if children:
            child = children[0]
            namespace = str(child["namespace_sha256"])
            allowed.add(self.prefix + str(child["preview_sha256"]) + ".json")
            allowed |= {namespace + "." + state + ".json" for state in NORMAL_EVENTS}
            allowed.add("p0-diagnostic." + namespace + ".json")
        if set(inventory) - frozen - allowed:
            raise ValueError("P1_PILOT_UNCLASSIFIED_RECEIPT_STOP")
        all_slots = historical + prior + children
        for key in ("namespace_sha256", "command_id", "preview_sha256"):
            if len({row[key] for row in all_slots}) != len(all_slots):
                raise ValueError("P1_PILOT_SLOT_DUPLICATE")
        total = sum((money(row["reserved_usd"]) for row in all_slots), Decimal(0))
        if (len(all_slots) > 14 or total > money(self.permission["cumulative_ceiling_usd"])
            or P0UnknownOffReader._inventory(self.root) != inventory):
            raise ValueError("P1_PILOT_CUMUL_OR_READ_SET_CHANGED")
        self.pin._root_unchanged()
        return all_slots

    def arm(self, *, record: Mapping[str, object]) -> None:
        self._require_lock()
        if self._pending is not None or record.get("permission_sha256") != self.permission_sha256:
            raise ValueError("P1_PILOT_PENDING_ALREADY_USED")
        self._pending = (self._broker_identity, str(record["command_id"]),
            str(record["grant_sha256"]), str(record["namespace_sha256"]),
            str(record["preflight_sha256"]), str(record["request_sha256"]))

    def disarm(self) -> None:
        self._pending = None

    def reserve(self, *, grant: Mapping[str, object], preview_sha256: str,
                command_id: str, preflight: Mapping[str, object]) -> None:
        self._require_lock()
        if tuple(grant.get(key) for key in ("request_sha256", "preparation_sha256",
            "context_sha256", "reference_set_sha256")) != self._candidate:
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        if len(self.slots()) != self.base_slots_count:
            raise ValueError("P1_PILOT_OPERATION_ALREADY_RESERVED")
        if (money(preflight["cost_bound_usd"]) > money("0.14")
            or sum((money(row["reserved_usd"]) for row in self.slots()), Decimal(0))
                + money(preflight["cost_bound_usd"]) > money("1.96")):
            raise ValueError("P1_PILOT_CUMUL_EXCEEDED")
        super().reserve(grant=grant, preview_sha256=preview_sha256,
            command_id=command_id, preflight=preflight)
