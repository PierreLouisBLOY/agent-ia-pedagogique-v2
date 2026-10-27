"""Versioned continuity ledger; original native LOCK, no old-data mutation."""
from __future__ import annotations

import ctypes
import json
import re
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    P0NormalReceipt,
    decode,
    pinned_receipt_root,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    BoundChain,
    OwnPending,
    allow_own_transition,
    metadata,
    reject_orphan_namespaces,
    validate_events,
    validate_historical_witnesses,
    validate_slot,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.infrastructure.filesystem import (
    LocalFileSecurityError,
    capture_secure_path,
    read_file_nofollow,
)

NORMAL_EVENTS = {"RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED",
    "UNKNOWN", "PARSING_REJECTED", "DISPATCH", "RESULT"}


def _decode_historical_metadata(raw: bytes) -> dict[str, object]:
    """Pinned external technical witness format; never the business decoder."""
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len(dict(pairs)) != len(pairs):
            raise ValueError("P0_CONTINUITY_HISTORICAL_METADATA_DUPLICATE")
        return dict(pairs)

    def reject_constant(_: str) -> object:
        raise ValueError("P0_CONTINUITY_HISTORICAL_METADATA_NONFINITE")

    try:
        document = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("P0_CONTINUITY_HISTORICAL_METADATA_FORMAT") from None
    if not isinstance(document, dict):
        raise ValueError("P0_CONTINUITY_HISTORICAL_METADATA_OBJECT_REQUIRED")
    return cast(dict[str, object], document)


class P0ContinuityProductLedger(P0ProductLedger):
    def __init__(self, *, root: Path, permission: Mapping[str, object],
                 chain_loader: Callable[[], BoundChain], broker_identity: object,
                 clock: Callable[[], datetime]) -> None:
        super().__init__(root=root, permission=permission)
        self.chain_loader, self.broker_identity, self.clock = chain_loader, broker_identity, clock
        self._held_thread: int | None = None
        self._pending: OwnPending | None = None
        self._pending_dispatch_sha256: str | None = None
        self._chain: BoundChain | None = None

    @contextmanager
    def locked(self, *, create: bool = True) -> Iterator[None]:
        # The continuity LOCK is always OPEN_EXISTING, for either caller mode.
        if self._held_thread == threading.get_ident():
            raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
        self.pin._root_unchanged()
        with pinned_receipt_root(self.root):
            lock = self.root / (self.prefix + "LOCK")
            before = capture_secure_path(lock, allowed_root=self.root)
            if not before.exists:
                raise ValueError("P0_CONTINUITY_ORIGINAL_LOCK_MISSING")
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel.CreateFileW
            create_file.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
            create_file.restype = ctypes.c_void_p
            close = kernel.CloseHandle
            close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
            identify = kernel.GetFileInformationByHandleEx
            identify.argtypes, identify.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32), ctypes.c_int
            read = kernel.ReadFile
            read.argtypes, read.restype = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p), ctypes.c_int

            class FileIdentity(ctypes.Structure):
                _fields_ = [("volume", ctypes.c_uint64), ("file_id", ctypes.c_ubyte * 16)]

            handle = create_file(str(lock), 0x80000000, 0, None, 3, 0x00200000, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
            try:
                opened = FileIdentity()
                if (not identify(handle, 18, ctypes.byref(opened), ctypes.sizeof(opened))
                        or (opened.volume, int.from_bytes(bytes(opened.file_id), "little")) != (before.device, before.inode)
                        or not before.same_identity(capture_secure_path(lock, allowed_root=self.root))):
                    raise ValueError("P0_CONTINUITY_LOCK_IDENTITY_CHANGED")
                # Read from this same retained exclusive handle, after acquisition.
                buffer, size = ctypes.create_string_buffer(1001), ctypes.c_uint32()
                if not read(handle, buffer, 1001, ctypes.byref(size), None) or size.value > 1000:
                    raise ValueError("P0_CONTINUITY_ORIGINAL_LOCK_BINDING")
                chain = self.chain_loader()
                raw = buffer.raw[:size.value]
                if (raw != canonical({"permission_sha256": chain.root.permission_sha256})
                        or sha(raw) != chain.manifest["root_lock_sha256"]
                        or chain.current.permission_sha256 != self.permission_sha256
                        or chain.manifest["campaign_namespace_sha256"] != self.permission["permission_namespace_sha256"]):
                    raise ValueError("P0_CONTINUITY_ORIGINAL_LOCK_BINDING")
                self.pin._root_unchanged()
                self._held_thread, self._chain = threading.get_ident(), chain
                self._held_lock_sha256 = sha(raw)
                yield
                self.pin._root_unchanged()
                if not before.same_identity(capture_secure_path(lock, allowed_root=self.root)):
                    raise ValueError("P0_CONTINUITY_LOCK_IDENTITY_CHANGED")
            finally:
                self._held_thread, self._chain = None, None
                self._held_lock_sha256 = None
                close(handle)

    def chain(self) -> BoundChain:
        if self._held_thread != threading.get_ident() or self._chain is None:
            raise ValueError("P0_CONTINUITY_RETAINED_LOCK_REQUIRED")
        return self._chain

    @contextmanager
    def own_transition(self, pending: OwnPending, *, dispatch_sha256: str) -> Iterator[None]:
        self.chain()
        if self._pending is not None:
            raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
        self._pending, self._pending_dispatch_sha256 = pending, dispatch_sha256
        try:
            yield
        finally:
            self._pending, self._pending_dispatch_sha256 = None, None

    def _normal_namespaces(self) -> dict[str, Mapping[str, object] | None]:
        result: dict[str, Mapping[str, object] | None] = {}
        files = sorted(self.root.glob("*.json"))
        if len(files) > 1024:
            raise ValueError("P0_CONTINUITY_RECEIPT_INVENTORY_LIMIT")
        for path in files:
            matched = re.fullmatch(r"([0-9a-f]{64})\.([A-Z_]+)\.json", path.name)
            if matched is None:
                if any(path.name.endswith("." + state + ".json") for state in NORMAL_EVENTS):
                    raise ValueError("P0_CONTINUITY_NORMAL_NAMESPACE_AMBIGUOUS")
                continue
            if matched[2] not in NORMAL_EVENTS:
                raise ValueError("P0_CONTINUITY_NORMAL_NAMESPACE_AMBIGUOUS")
            namespace = matched[1]
            if namespace not in result:
                receipt = P0NormalReceipt(self.root, namespace)
                result[namespace] = receipt.read("DISPATCH") if receipt.exists("DISPATCH") else None
        return result

    def _verify_witness_evidence(self, chain: BoundChain, records: list[dict[str, object]]) -> None:
        for raw_witness in cast(list[object], chain.manifest["historical_reservations"]):
            witness = cast(Mapping[str, object], raw_witness)
            descriptor = cast(Mapping[str, object], witness["metadata_evidence"])
            path = Path(str(descriptor["path"]))
            raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=256_000)
            if sha(raw) != descriptor["sha256"]:
                raise ValueError("P0_CONTINUITY_HISTORICAL_EVIDENCE_CHANGED")
            document = _decode_historical_metadata(raw)
            origin = next((proof for proof in chain.origins if proof.permission_sha256 == witness["permission_sha256"]), None)
            flags, events = document.get("flags"), document.get("events")
            if (document.get("schema") != "LU-P1-OWNER-EXACT-RECEIPT-METADATA-1.0"
                    or document.get("permission_sha256") != witness["permission_sha256"]
                    or document.get("request_sha256") != witness["request_sha256"]
                    or document.get("slot_namespace_sha256") != witness["namespace_sha256"]
                    or document.get("campaign_namespace_sha256") != chain.manifest["campaign_namespace_sha256"]
                    or origin is None or document.get("source_commit") != origin.permission["baseline_commit"]
                    or not isinstance(flags, Mapping) or not isinstance(events, Mapping)
                    or any(flags.get(state) is not True for state in ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED"))
                    or flags.get("UNKNOWN") is not False or flags.get("PARSING_REJECTED") is not False
                    or document.get("raw_output_text_disclosed") is not False):
                raise ValueError("P0_CONTINUITY_HISTORICAL_EVIDENCE_BINDING")
            receipt = P0NormalReceipt(self.root, str(witness["namespace_sha256"]))
            for state in ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED"):
                event = events.get(state)
                if not isinstance(event, Mapping) or event.get("receipt_sha256") != sha(canonical(receipt.read(state))):
                    raise ValueError("P0_CONTINUITY_HISTORICAL_EVIDENCE_BINDING")

    def slots(self) -> list[dict[str, object]]:
        if self._held_thread != threading.get_ident():
            with self.locked():
                return self.slots()
        chain = self.chain()
        self.pin._root_unchanged()
        records: list[dict[str, object]] = []
        files = sorted(self.root.glob(self.prefix + "*.json"))
        if len(files) > 14:
            raise ValueError("P0_PRODUCT_LEDGER_LIMIT")
        for path in files:
            if re.fullmatch(re.escape(self.prefix) + r"[0-9a-f]{64}\.json", path.name) is None:
                raise ValueError("P0_PRODUCT_SLOT_NAME")
            record = decode(read_file_nofollow(path, allowed_root=self.root, maximum_bytes=32_000))
            if record.get("schema") == "P0-FINITE-CHAIN-SLOT-2.0":
                if self.finite_extension is None:
                    raise ValueError("P0_CHAIN_ORIGIN_NOT_BOUND")
                self.finite_extension.validate(record, file_name=path.name)
                records.append(record)
                continue
            validate_slot(chain, record, file_name=path.name)
            receipt = P0NormalReceipt(self.root, str(record["namespace_sha256"]))
            existing = [state for state in NORMAL_EVENTS if receipt.exists(state)]
            if not existing and allow_own_transition(chain, record, self._pending,
                    broker_identity=self.broker_identity, dispatch_sha256=str(self._pending_dispatch_sha256),
                    now=self.clock(), existing_p0_events=existing):
                records.append(record)
                continue
            try:
                if receipt.confirmed(cast(Mapping[str, object], record["grant"])) is None:
                    raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED")
                capture = receipt.read("DISPATCH")
                if capture["preflight_sha256"] != record["preflight_sha256"]:
                    raise ValueError("P0_CONTINUITY_CAPTURE_SLOT_BINDING")
                lifecycle = {state: receipt.read(state) for state in
                    ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED")}
                validate_events(record, lifecycle)
            except (ValueError, FileNotFoundError, LocalFileSecurityError):
                if self.finite_extension is None:
                    raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED") from None
                self.finite_extension.validate_retained_origin(record)
            records.append(record)
        if self.finite_extension is not None:
            self.finite_extension.validate_group(records)
        validate_historical_witnesses(chain, records)
        self._verify_witness_evidence(chain, records)
        reject_orphan_namespaces(chain, records, normal_namespaces=self._normal_namespaces())
        # The closed arithmetic validates cumulative reserve and duplicates.
        metadata(chain, [r for r in records if r.get("schema") != "P0-FINITE-CHAIN-SLOT-2.0"], now=self.clock())
        self.pin._root_unchanged()
        return records

    def snapshot(self) -> dict[str, object]:
        with self.locked():
            records = self.slots()
            return metadata(self.chain(), records, now=self.clock())
