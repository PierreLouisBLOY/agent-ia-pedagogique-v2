"""Append-only private P0 effects, pinned Windows parents and no-follow reads."""
from __future__ import annotations

import ctypes
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_diagnostic import (
    MAX_FAILURE_DIAGNOSTIC_BYTES,
    validate_failure_document,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    recover_binding,
    sha,
)
from backend.infrastructure.filesystem import (
    assert_local_data_root,
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
    read_file_nofollow,
)


def decode(raw: bytes) -> dict[str, object]:
    import json

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len(dict(pairs)) != len(pairs):
            raise ValueError("P0_RECEIPT_DUPLICATE_KEY")
        return dict(pairs)

    result = json.loads(raw, object_pairs_hook=unique,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("P0_RECEIPT_NONFINITE")))
    if not isinstance(result, dict) or canonical(result) != raw:
        raise ValueError("P0_RECEIPT_CANONICAL")
    return cast(dict[str, object], result)


@contextmanager
def pinned_receipt_root(root: Path) -> Iterator[None]:
    """Retain every existing parent without DELETE sharing during publication/read.

    The filesystem helpers still check no-follow file identity before/after I/O.
    Parent handles close only after the complete operation. No SQL or rollback API.
    """
    if os.name != "nt":
        raise ValueError("P0_NORMAL_WINDOWS_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                       ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
    create.restype = ctypes.c_void_p
    class FileIdentity(ctypes.Structure):
        _fields_ = [("volume", ctypes.c_uint64), ("file_id", ctypes.c_ubyte * 16)]
    identify = kernel.GetFileInformationByHandleEx
    identify.argtypes, identify.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32), ctypes.c_int
    close = kernel.CloseHandle
    close.argtypes, close.restype = (ctypes.c_void_p,), ctypes.c_int
    held: list[int] = []
    try:
        for path in (*reversed(root.parents), root):
            before = capture_secure_path(path, allowed_root=path)
            if not before.is_directory:
                raise ValueError("P0_RECEIPT_EXISTING_PRIVATE_ROOT_REQUIRED")
            # A metadata-only handle does not hold Windows share/delete access.
            # GENERIC_READ participates in sharing and actually denies rename.
            handle = create(str(path), 0x80000000, 3, None, 3, 0x02200000, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise ValueError("P0_RECEIPT_PARENT_PIN_REFUSED")
            held.append(cast(int, handle))
            opened = FileIdentity()
            if (not identify(handle, 18, ctypes.byref(opened), ctypes.sizeof(opened))
                    or (opened.volume, int.from_bytes(bytes(opened.file_id), "little")) != (before.device, before.inode)
                    or not before.same_identity(capture_secure_path(path, allowed_root=path))):
                raise ValueError("P0_RECEIPT_PARENT_CHANGED")
        yield
    finally:
        for handle in reversed(held):
            close(handle)


class P0NormalReceipt:
    """Exactly one namespace; no discovery, renewal, overwrite or historical cleanup."""

    def __init__(self, root: Path, namespace: str) -> None:
        self.root = assert_local_data_root(root)
        repository = Path(__file__).resolve().parents[5]
        if self.root == repository or self.root.is_relative_to(repository) or not digest(namespace):
            raise ValueError("P0_RECEIPT_OUTSIDE_REPOSITORY_REQUIRED")
        before = capture_secure_path(self.root, allowed_root=self.root)
        if not before.is_directory:
            raise ValueError("P0_RECEIPT_EXISTING_PRIVATE_ROOT_REQUIRED")
        self.identity = before
        self.namespace = namespace
        self.root_sha256 = sha(canonical({"path": str(self.root), "device": before.device, "inode": before.inode}))

    def _path(self, name: str) -> Path:
        if name not in {"RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED",
                        "UNKNOWN", "PARSING_REJECTED", "DISPATCH", "RESULT"}:
            raise ValueError("P0_RECEIPT_NAME")
        return self.root / (self.namespace + "." + name + ".json")

    def _root_unchanged(self) -> None:
        if not self.identity.same_identity(capture_secure_path(self.root, allowed_root=self.root)):
            raise ValueError("P0_RECEIPT_ROOT_CHANGED")

    def exists(self, name: str) -> bool:
        self._root_unchanged()
        with pinned_receipt_root(self.root):
            return capture_secure_path(self._path(name), allowed_root=self.root).exists

    def publish(self, name: str, data: Mapping[str, object]) -> str:
        return self._publish_document(self._path(name), data)

    def _publish_document(self, path: Path, data: Mapping[str, object]) -> str:
        self._root_unchanged()
        raw = canonical(dict(data))
        if len(raw) > 256000:
            raise ValueError("P0_RECEIPT_SIZE")
        with pinned_receipt_root(self.root):
            self._root_unchanged()
            if capture_secure_path(path, allowed_root=self.root).exists:
                raise ValueError("P0_RECEIPT_ALREADY_USED")
            temporary = private_temporary_file(self.root, allowed_root=self.root, prefix="p0-effect-", suffix=".tmp")
            with temporary.open("wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            atomic_publish_fresh(temporary, path, allowed_root=self.root)
            self._root_unchanged()
        return sha(raw)

    def publish_failure_diagnostic(self, data: Mapping[str, object]) -> str:
        """Independent evidence, never a lifecycle event or a replacement receipt."""
        validate_failure_document(data, namespace=self.namespace)
        if len(canonical(dict(data))) > MAX_FAILURE_DIAGNOSTIC_BYTES:
            raise ValueError("P0_FAILURE_DIAGNOSTIC_SIZE")
        return self._publish_document(self.root / f"p0-diagnostic.{self.namespace}.json", data)

    def read_failure_diagnostic(self, *, grant: Mapping[str, object],
                                preflight: Mapping[str, object]) -> dict[str, object] | None:
        if (grant.get("namespace_sha256") != self.namespace
                or preflight.get("request_sha256") != grant.get("request_sha256")
                or preflight.get("request_bytes") != grant.get("request_bytes")):
            raise ValueError("P0_FAILURE_DIAGNOSTIC_BINDING")
        self._root_unchanged()
        path = self.root / f"p0-diagnostic.{self.namespace}.json"
        with pinned_receipt_root(self.root):
            if not capture_secure_path(path, allowed_root=self.root).exists:
                return None
            raw = read_file_nofollow(path, allowed_root=self.root,
                                     maximum_bytes=MAX_FAILURE_DIAGNOSTIC_BYTES)
            self._root_unchanged()
        value = decode(raw)
        validate_failure_document(value, namespace=self.namespace)
        if (value["grant_sha256"] != sha(canonical(dict(grant)))
                or value["request_sha256"] != grant.get("request_sha256")
                or value["preflight_sha256"] != sha(canonical(dict(preflight)))):
            raise ValueError("P0_FAILURE_DIAGNOSTIC_BINDING")
        return value

    def read(self, name: str) -> dict[str, object]:
        self._root_unchanged()
        with pinned_receipt_root(self.root):
            raw = read_file_nofollow(self._path(name), allowed_root=self.root, maximum_bytes=256000)
            self._root_unchanged()
        return decode(raw)

    def reserve(self, *, grant: Mapping[str, object], dispatch: Mapping[str, object], body: bytes,
                preflight: Mapping[str, object]) -> None:
        # Exclusive RESERVED is committed first: any later failure consumes the namespace.
        metadata = {"grant_sha256": sha(canonical(dict(grant))), "dispatch_sha256": sha(canonical(dict(dispatch))),
                    "request_sha256": sha(body), "preflight_sha256": sha(canonical(dict(preflight))),
                    "namespace_sha256": self.namespace}
        self.publish("RESERVED", self.event("RESERVED", grant, preflight))
        self.publish("DISPATCH", {"schema": "P0-NORMAL-DISPATCH-CAPTURE-1.0", **metadata,
                                  "grant": dict(grant), "dispatch": dict(dispatch),
                                  "body": body.decode(), "preflight": dict(preflight)})

    def event(self, state: str, grant: Mapping[str, object], preflight: Mapping[str, object], *,
              artifact: str | None = None, status: str | None = None,
              usage: Mapping[str, object] | None = None, provider_attempts: int | None = None) -> dict[str, object]:
        return {"schema": "P0-NORMAL-TECHNICAL-RECEIPT-1.0", "grant_sha256": sha(canonical(dict(grant))),
                "request_sha256": grant["request_sha256"], "preflight_sha256": sha(canonical(dict(preflight))),
                "namespace_sha256": self.namespace, "state": state, "timestamp_utc": datetime.now(UTC).isoformat(),
                "provider_attempts": (0 if state == "RESERVED" else 1) if provider_attempts is None else provider_attempts,
                "response_status": status,
                "response_artifact_sha256": artifact, "usage": dict(usage) if usage is not None else None,
                "reserved_usd": preflight["cost_bound_usd"], "observed_cost_status": "NOT_ESTABLISHED"}

    def confirmed(self, grant: Mapping[str, object]) -> tuple[dict[str, object], str] | None:
        if not self.exists("RESERVED"):
            return None
        if self.exists("UNKNOWN") or self.exists("PARSING_REJECTED") or not self.exists("RESPONSE_CAPTURED"):
            raise ValueError("P0_RECOVERY_OUTCOME_UNKNOWN")
        capture, record, artifact = self.read("DISPATCH"), self.read("RESPONSE_CAPTURED"), self.read("RESULT")
        closed(capture, {"schema", "grant_sha256", "dispatch_sha256", "request_sha256", "preflight_sha256",
                         "namespace_sha256", "grant", "dispatch", "body", "preflight"}, "P0_CAPTURE_FIELDS")
        expected_grant = sha(canonical(dict(grant)))
        dispatch, preflight = capture["dispatch"], capture["preflight"]
        if not isinstance(dispatch, dict) or not isinstance(preflight, dict) or not isinstance(capture["body"], str):
            raise ValueError("P0_CAPTURE_TYPES")
        if (capture["schema"] != "P0-NORMAL-DISPATCH-CAPTURE-1.0"
                or capture["grant"] != dict(grant) or capture["grant_sha256"] != expected_grant
                or capture["request_sha256"] != grant["request_sha256"]
                or sha(capture["body"].encode()) != grant["request_sha256"]
                or capture["preflight_sha256"] != sha(canonical(preflight))
                or capture["dispatch_sha256"] != sha(canonical(dispatch))
                or capture["namespace_sha256"] != self.namespace):
            raise ValueError("P0_CAPTURE_BINDING")
        if not isinstance(artifact.get("usage"), Mapping):
            raise ValueError("P0_CAPTURE_USAGE")
        expected = self.event("RESPONSE_CAPTURED", grant, preflight, artifact=sha(canonical(artifact)),
                              status=cast(str, artifact.get("response_status")), usage=cast(Mapping[str, object], artifact["usage"]))
        if set(record) != set(expected) or any(record[key] != value for key, value in expected.items() if key != "timestamp_utc"):
            raise ValueError("P0_CAPTURE_RECEIPT_BINDING")
        reserved = self.read("RESERVED")
        attempted = self.read("PROVIDER_ATTEMPTED")
        for saved, state in ((reserved, "RESERVED"), (attempted, "PROVIDER_ATTEMPTED")):
            wanted = self.event(state, grant, preflight)
            if set(saved) != set(wanted) or any(saved[key] != val for key, val in wanted.items() if key != "timestamp_utc"):
                raise ValueError("P0_CAPTURE_CHAIN")
        text = recover_binding(artifact=artifact, grant_sha256=expected_grant,
                               request_sha256=grant["request_sha256"],
                               dispatch_sha256=sha(canonical(dispatch)))
        return cast(dict[str, object], dispatch), text
