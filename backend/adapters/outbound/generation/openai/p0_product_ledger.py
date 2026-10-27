"""P1 pessimistic append-only budget; a Windows handle serializes processes."""
from __future__ import annotations

import ctypes
import os
import re
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

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
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    P0NormalReceipt,
    decode,
    pinned_receipt_root,
)
from backend.infrastructure.filesystem import (
    LocalFileSecurityError,
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
    read_file_nofollow,
)

SLOT_FIELDS = {"schema", "permission_sha256", "preview_sha256", "command_id", "grant", "grant_sha256",
               "namespace_sha256", "request_sha256", "preflight_sha256", "reserved_usd"}


class FiniteLedgerExtension(Protocol):
    def validate(self, record: Mapping[str, object], *, file_name: str) -> None: ...

    def validate_group(self, records: list[dict[str, object]]) -> None: ...

    def validate_retained_origin(self, record: Mapping[str, object]) -> None: ...


class P0ProductLedger:
    def __init__(self, *, root: Path, permission: Mapping[str, object]) -> None:
        self.permission = dict(permission)
        self.permission_sha256 = sha(canonical(self.permission))
        self.root = root
        self.pin = P0NormalReceipt(root, str(permission["permission_namespace_sha256"]))
        if self.pin.root_sha256 != permission["receipt_root_sha256"]:
            raise ValueError("P0_PRODUCT_RECEIPT_ROOT_BINDING")
        self.prefix = str(permission["permission_namespace_sha256"]) + ".P1."
        self.finite_extension: FiniteLedgerExtension | None = None
        self._held_thread: int | None = None
        self._held_lock_sha256: str | None = None

    def _publish(self, path: Path, raw: bytes) -> None:
        self.pin._root_unchanged()
        temporary = private_temporary_file(self.root, allowed_root=self.root, prefix="p1-proof-", suffix=".tmp")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_publish_fresh(temporary, path, allowed_root=self.root)

    @contextmanager
    def locked(self, *, create: bool = True) -> Iterator[None]:
        self.pin._root_unchanged()
        with pinned_receipt_root(self.root):
            lock = self.root / (self.prefix + "LOCK")
            if not capture_secure_path(lock, allowed_root=self.root).exists:
                if not create:
                    raise ValueError("P0_PRODUCT_EXISTING_LOCK_REQUIRED")
                try:
                    self._publish(lock, canonical({"permission_sha256": self.permission_sha256}))
                except Exception:
                    if not capture_secure_path(lock, allowed_root=self.root).exists:
                        raise
            try:
                raw = read_file_nofollow(lock, allowed_root=self.root, maximum_bytes=1000)
            except PermissionError:
                raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH") from None
            except LocalFileSecurityError as error:
                if isinstance(error.__cause__, PermissionError):
                    raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH") from None
                raise
            if raw != canonical({"permission_sha256": self.permission_sha256}):
                raise ValueError("P0_PRODUCT_LOCK_BINDING")
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel.CreateFileW
            create_file.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                               ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
            create_file.restype = ctypes.c_void_p
            before = capture_secure_path(lock, allowed_root=self.root)
            class FileIdentity(ctypes.Structure):
                _fields_ = [("volume", ctypes.c_uint64), ("file_id", ctypes.c_ubyte * 16)]
            identify = kernel.GetFileInformationByHandleEx
            identify.argtypes, identify.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32), ctypes.c_int
            close = kernel.CloseHandle
            close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
            handle = create_file(str(lock), 0x80000000, 0, None, 3, 0x00200000, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
            try:
                opened = FileIdentity()
                if (not identify(handle, 18, ctypes.byref(opened), ctypes.sizeof(opened))
                        or (opened.volume, int.from_bytes(bytes(opened.file_id), "little")) != (before.device, before.inode)
                        or not before.same_identity(capture_secure_path(lock, allowed_root=self.root))):
                    raise ValueError("P0_PRODUCT_LOCK_CHANGED")
                self.pin._root_unchanged()
                read = kernel.ReadFile
                read.argtypes, read.restype = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p), ctypes.c_int
                buffer, size = ctypes.create_string_buffer(1001), ctypes.c_uint32()
                if not read(handle, buffer, 1001, ctypes.byref(size), None) or size.value > 1000:
                    raise ValueError("P0_PRODUCT_LOCK_BINDING")
                retained_raw = buffer.raw[:size.value]
                if retained_raw != canonical({"permission_sha256": self.permission_sha256}):
                    raise ValueError("P0_PRODUCT_LOCK_BINDING")
                self._held_thread = threading.get_ident()
                self._held_lock_sha256 = sha(retained_raw)
                yield
            finally:
                self._held_thread = None
                self._held_lock_sha256 = None
                close(handle)

    def slots(self) -> list[dict[str, object]]:
        self.pin._root_unchanged()
        result = []
        with pinned_receipt_root(self.root):
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
                    result.append(record)
                    continue
                closed(record, SLOT_FIELDS, "P0_PRODUCT_SLOT_FIELDS")
                grant = record["grant"]
                if (not isinstance(grant, dict) or record["schema"] != "P0-PRODUCT-BUDGET-SLOT-1.0"
                        or record["permission_sha256"] != self.permission_sha256
                        or sha(canonical(grant)) != record["grant_sha256"]
                        or record["request_sha256"] != grant.get("request_sha256")
                        or record["namespace_sha256"] != grant.get("namespace_sha256")
                        or path.name != self.prefix + str(record["preview_sha256"]) + ".json"
                        or any(not digest(record[k]) for k in ("preview_sha256", "grant_sha256", "namespace_sha256", "request_sha256", "preflight_sha256"))
                        or not isinstance(record["command_id"], str) or re.fullmatch(r"[0-9a-f]{32}", record["command_id"]) is None
                        or money(record["reserved_usd"]) > money(self.permission["per_call_ceiling_usd"])):
                    raise ValueError("P0_PRODUCT_SLOT_BINDING")
                if any(grant.get(k) != self.permission[k] for k in (HASH_FIELDS & self.permission.keys()) | {"baseline_commit"}):
                    raise ValueError("P0_PRODUCT_SLOT_PERMISSION_BINDING")
                validate_grant(grant, identities={k: grant[k] for k in HASH_FIELDS | {"baseline_commit", "request_bytes"}},
                               now=utc(grant["issued_at_utc"]))
                result.append(record)
        if self.finite_extension is not None:
            self.finite_extension.validate_group(result)
        legacy = [record for record in result if record.get("schema") != "P0-FINITE-CHAIN-SLOT-2.0"]
        if (len(legacy) > cast(int, self.permission["max_calls"])
                or sum((money(r["reserved_usd"]) for r in legacy), Decimal(0)) > money(self.permission["cumulative_ceiling_usd"])):
            raise ValueError("P0_PRODUCT_LEDGER_OVERBUDGET")
        return result

    def reserve_finite(self, record: Mapping[str, object]) -> None:
        if self._held_thread != threading.get_ident() or self.finite_extension is None:
            raise ValueError("P0_CHAIN_RETAINED_LOCK_REQUIRED")
        name = self.prefix + str(record.get("preview_sha256")) + ".json"
        self.finite_extension.validate(record, file_name=name)
        self._publish(self.root / name, canonical(record))

    def reserve(self, *, grant: Mapping[str, object], preview_sha256: str, command_id: str,
                preflight: Mapping[str, object]) -> None:
        record = {"schema": "P0-PRODUCT-BUDGET-SLOT-1.0", "permission_sha256": self.permission_sha256,
            "preview_sha256": preview_sha256, "command_id": command_id, "grant": dict(grant),
            "grant_sha256": sha(canonical(grant)), "namespace_sha256": grant["namespace_sha256"],
            "request_sha256": grant["request_sha256"], "preflight_sha256": sha(canonical(preflight)),
            "reserved_usd": preflight["cost_bound_usd"]}
        self._publish(self.root / (self.prefix + preview_sha256 + ".json"), canonical(record))
