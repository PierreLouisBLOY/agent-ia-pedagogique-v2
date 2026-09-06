"""One bounded child and watchdog; immutable private one-shot effect receipts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, fields, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from backend.infrastructure.filesystem import (
    assert_local_data_root,
    atomic_publish_fresh,
    capture_secure_path,
    ensure_private_directory,
    private_temporary_file,
)
from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import (
    ConversationRejected,
    plain,
)
from backend.modules.work_orchestration.ports.outbound.generation_job import (
    GenerationJobResult,
    GenerationUsage,
)

FRAME_LIMIT = 256 * 1024
WORKER_MODULE = "backend.infrastructure.composition.bootstrap.conversation_worker"
ENVIRONMENT_KEYS = frozenset({"SystemRoot", "WINDIR", "COMSPEC", "PATH", "TEMP", "TMP",
                              "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING"})


def encode_frame(payload: object) -> bytes:
    raw = json.dumps(plain(payload), ensure_ascii=False, allow_nan=False,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > FRAME_LIMIT:
        raise ValueError("IPC_SIZE_REJECTED")
    return struct.pack("!I", len(raw)) + raw


def decode_frame(raw: bytes) -> dict[str, object]:
    if len(raw) < 4 or not 1 <= struct.unpack("!I", raw[:4])[0] <= FRAME_LIMIT:
        raise ValueError("IPC_FRAME_REJECTED")
    if len(raw) != 4 + struct.unpack("!I", raw[:4])[0]:
        raise ValueError("IPC_FRAME_REJECTED")
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("IPC_FRAME_REJECTED")
            result[key] = value
        return result
    def reject(value: str) -> object:
        raise ValueError("IPC_FRAME_REJECTED")
    value = json.loads(raw[4:].decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError("IPC_FRAME_REJECTED")
    return cast(dict[str, object], value)


def request_payload(request: ConversationDraftRequest) -> dict[str, object]:
    return {"request_id": request.request_id, "conversation_id": request.conversation_id,
            "generation_id": request.generation_id, "brief": request.brief,
            "context": request.context.as_dict()}


def decode_request(data: Mapping[str, object]) -> ConversationDraftRequest:
    if set(data) != {"request_id", "conversation_id", "generation_id", "brief", "context"}:
        raise ValueError("IPC_REQUEST_REJECTED")
    return ConversationDraftRequest(cast(str, data["request_id"]), cast(str, data["conversation_id"]),
        cast(str, data["generation_id"]), cast(str, data["brief"]),
        ConfirmedConversationContext(cast(Mapping[str, object], data["context"])))


def result_payload(result: GenerationJobResult) -> dict[str, object]:
    draft = result.draft
    payload: dict[str, object] = {"generation_id": result.generation_id, "state": result.state, "error_code": result.error_code,
            "draft": None if draft is None else {"production_ref": draft.production_ref,
                "content": draft.content, "sections": draft.sections, "references": draft.references,
                "lineage": draft.lineage, "limitations": draft.limitations}}
    if result.usage is not None:
        payload["usage"] = asdict(result.usage)
    return payload


def decode_usage(value: object) -> GenerationUsage:
    if not isinstance(value, dict) or set(value) != {f.name for f in fields(GenerationUsage)}:
        raise ValueError("IPC_USAGE_REJECTED")
    return GenerationUsage(**value)


def decode_result(data: Mapping[str, object]) -> GenerationJobResult:
    if set(data) not in ({"generation_id", "state", "error_code", "draft"},
                        {"generation_id", "state", "error_code", "draft", "usage"}):
        raise ValueError("IPC_RESULT_REJECTED")
    draft = data["draft"]
    materialized = None
    if draft is not None:
        if not isinstance(draft, dict) or set(draft) != {
            "production_ref", "content", "sections", "references", "lineage", "limitations",
        }:
            raise ValueError("IPC_RESULT_REJECTED")
        materialized = ConversationDraft(draft["production_ref"], draft["content"],
            tuple(draft["sections"]), tuple(draft["references"]), draft["lineage"], tuple(draft["limitations"]))
    return GenerationJobResult(cast(str, data["generation_id"]), cast(str, data["state"]),
        materialized, cast(str | None, data["error_code"]),
        decode_usage(data["usage"]) if "usage" in data else None)


class OneShotReceipt:
    """An exclusive RESERVED publication is the lock; never deleted or silently replaced."""
    def __init__(self, root: Path, authorization_sha256: str, ceiling: Decimal) -> None:
        if (re.fullmatch(r"[0-9a-f]{64}", authorization_sha256) is None
                or not ceiling.is_finite() or ceiling < 0):
            raise ValueError("AUTHORIZATION_IDENTITY_REQUIRED")
        self.root = assert_local_data_root(root)
        repository = Path(__file__).resolve().parents[4]
        if self.root == repository or self.root.is_relative_to(repository):
            raise ValueError("RECEIPT_OUTSIDE_REPOSITORY_REQUIRED")
        self.digest, self.ceiling = authorization_sha256, ceiling
        self.reserved = False

    def require_unused(self) -> None:
        if capture_secure_path(self.root / (self.digest + ".RESERVED.json"), allowed_root=self.root).exists:
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def record(self, state: str, request: ConversationDraftRequest,
               usage: GenerationUsage | None = None) -> None:
        if state not in {"RESERVED", "DISPATCHED", "CONSUMED", "UNKNOWN",
                         "PROVIDER_ATTEMPTED", "USAGE_CAPTURED", "USAGE_PARSED"}:
            raise ValueError("INVALID_RECEIPT_STATE")
        if state != "RESERVED" and not self.reserved:
            raise ValueError("RECEIPT_NOT_RESERVED")
        ensure_private_directory(self.root, allowed_root=self.root)
        destination = self.root / (self.digest + "." + state + ".json")
        if capture_secure_path(destination, allowed_root=self.root).exists:
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
        temporary = private_temporary_file(self.root, allowed_root=self.root,
            prefix="receipt-", suffix=".tmp")
        payload: dict[str, object] = {"authorization_sha256": self.digest, "state": state,
            "generation_id": request.generation_id, "request_id": request.request_id,
            "reserved_usd": str(self.ceiling), "observed_usd": None,
            "timestamp": datetime.now(UTC).isoformat()}
        if usage is not None:
            payload["technical"] = usage_cost_evidence(usage)
        # Private temporary inode + exclusive atomic publication; no content or secret.
        with temporary.open("wb") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")).encode())
            handle.flush()
            os.fsync(handle.fileno())
        atomic_publish_fresh(temporary, destination, allowed_root=self.root)
        if state == "RESERVED":
            self.reserved = True


class ConversationProcessJob:
    def __init__(self, *, executable: Path, working_directory: Path,
        environment: Mapping[str, str], authorize: Callable[[ConversationDraftRequest], None],
        receipt: OneShotReceipt, launch: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        clock: Callable[[], float] = time.monotonic, timeout: float = 120,
        technical: Callable[[], Mapping[str, object]] | None = None) -> None:
        if (not 0 < timeout <= 120 or set(environment) - ENVIRONMENT_KEYS
                or environment.get("PYTHONDONTWRITEBYTECODE") != "1"):
            raise ValueError("WORKER_CONFIGURATION_REJECTED")
        self.executable, self.directory, self.environment = executable, working_directory, dict(environment)
        self.check, self.receipt, self.launch, self.clock, self.timeout = authorize, receipt, launch, clock, timeout
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._child: subprocess.Popen[bytes] | None = None
        self._result: GenerationJobResult | None = None
        self._used = False
        self._authorized_digest: str | None = None
        self.technical = technical

    def authorize(self, request: ConversationDraftRequest) -> None:
        if self._used or self._stop.is_set():
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
        self.check(request)
        self._authorized_digest = hashlib.sha256(encode_frame(request_payload(request))).hexdigest()

    def start(self, request: ConversationDraftRequest) -> None:
        frame = encode_frame(request_payload(request))
        with self._lock:
            if self._used or self._stop.is_set() or hashlib.sha256(frame).hexdigest() != self._authorized_digest:
                raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
            self.receipt.record("RESERVED", request)
            self._used = True
            deadline = self.clock() + self.timeout
            self._thread = threading.Thread(target=self._supervise, args=(request, frame, deadline),
                                            name="r2-generation-supervisor", daemon=True)
            self._thread.start()

    def _supervise(self, request: ConversationDraftRequest, frame: bytes, deadline: float) -> None:
        result = GenerationJobResult(request.generation_id, "UNKNOWN", error_code="GENERATION_OUTCOME_UNKNOWN")
        child = None
        channel = None
        usage = None
        try:
            self.receipt.record("DISPATCHED", request)
            args = [str(self.executable), "-m", WORKER_MODULE]
            options: dict[str, object] = {}
            if self.technical is not None:
                channel = PrivateWorkerChannel(self.technical())
                args.extend(channel.arguments)
                options = channel.launch_options
            child = self.launch(args, cwd=self.directory,
                env=self.environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, shell=False, bufsize=0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **options)
            if channel is not None:
                channel.after_launch()
            self._child = child
            if child.stdin is None or child.stdout is None:
                raise ValueError("IPC_UNAVAILABLE")
            os.set_blocking(child.stdin.fileno(), False)
            os.set_blocking(child.stdout.fileno(), False)
            received = bytearray()
            sent = 0
            expected = None
            while not self._stop.is_set() and self.clock() < deadline:
                if channel is not None:
                    for captured in channel.pump():
                        usage = captured
                        state = ("PROVIDER_ATTEMPTED" if not captured.response_received else
                                 "USAGE_CAPTURED" if captured.parsing == "NOT_RUN" else "USAGE_PARSED")
                        self.receipt.record(state, request, captured)
                if sent < len(frame):
                    try:
                        sent += os.write(child.stdin.fileno(), frame[sent:sent + 4096])
                    except BlockingIOError:
                        pass
                    if sent == len(frame):
                        child.stdin.close()
                try:
                    chunk = os.read(child.stdout.fileno(), min(4096, FRAME_LIMIT + 5 - len(received)))
                except BlockingIOError:
                    chunk = None
                if chunk:
                    received.extend(chunk)
                    if expected is None and len(received) >= 4:
                        expected = struct.unpack("!I", received[:4])[0]
                        if not 1 <= expected <= FRAME_LIMIT:
                            raise ValueError("IPC_SIZE_REJECTED")
                    if expected is not None and len(received) > expected + 4:
                        raise ValueError("IPC_SIZE_REJECTED")
                if chunk == b"" and child.poll() is not None:
                    if child.returncode != 0:
                        raise ValueError("WORKER_FAILED")
                    result = decode_result(decode_frame(bytes(received)))
                    if result.generation_id != request.generation_id:
                        raise ValueError("IPC_IDENTITY_REJECTED")
                    break
                self._stop.wait(.01)
            if channel is not None:
                for captured in channel.pump():
                    usage = captured
                    state = ("PROVIDER_ATTEMPTED" if not captured.response_received else
                             "USAGE_CAPTURED" if captured.parsing == "NOT_RUN" else "USAGE_PARSED")
                    self.receipt.record(state, request, captured)
            if usage is not None:
                result = replace(result, usage=result.usage or usage)
            self.receipt.record("UNKNOWN" if result.state == "UNKNOWN" else "CONSUMED", request, result.usage)
        except Exception:
            # A failing result pipe must not hide metadata already written by the child.
            if channel is not None:
                try:
                    for captured in channel.pump():
                        usage = captured
                        state = ("PROVIDER_ATTEMPTED" if not captured.response_received else
                                 "USAGE_CAPTURED" if captured.parsing == "NOT_RUN" else "USAGE_PARSED")
                        self.receipt.record(state, request, captured)
                except Exception:
                    pass  # Keep the last validated capture; RESERVED still prevents replay.
            result = GenerationJobResult(request.generation_id, "UNKNOWN",
                error_code="GENERATION_OUTCOME_UNKNOWN", usage=usage)
            try:
                self.receipt.record("UNKNOWN", request, usage)
            except Exception:
                pass  # RESERVED remains an irreversible refusal on restart.
        finally:
            if child is not None:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=1)
                for pipe in (child.stdin, child.stdout):
                    if pipe is not None:
                        pipe.close()
            if channel is not None:
                channel.close()
            with self._lock:
                self._result = result

    def poll(self) -> GenerationJobResult | None:
        with self._lock:
            result, self._result = self._result, None
            return result

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            if self._thread.is_alive() or (self._child is not None and self._child.poll() is None):
                raise ConversationRejected("GENERATION_OUTCOME_UNKNOWN")


def usage_cost_evidence(usage: GenerationUsage) -> dict[str, object]:
    """R2 documented rate, not an invoice; missing cache/tier is not free."""
    amount = None
    kind = "UNKNOWN"
    if usage.service_tier == "default" and usage.input_tokens is not None and usage.output_tokens is not None:
        amount = (Decimal(usage.input_tokens) * Decimal("2.5")
                  + Decimal(usage.output_tokens) * Decimal("12")) / Decimal(1_000_000)
        kind = "CONSERVATIVE_BOUND"
        cached, written = usage.cached_input_tokens, usage.cache_write_input_tokens
        if cached is not None and written is not None and cached + written <= usage.input_tokens:
            amount = (Decimal(usage.input_tokens - cached - written) * Decimal("2")
                + Decimal(cached) * Decimal("0.2") + Decimal(written) * Decimal("2.5")
                + Decimal(usage.output_tokens) * Decimal("12")) / Decimal(1_000_000)
            kind = "DOCUMENTED_RATE_CALCULATION_NOT_INVOICE"
    return {"usage": asdict(usage), "cost_kind": kind,
            "calculated_usd": str(amount) if amount is not None else None}


class PrivateWorkerChannel:
    """Inherited anonymous pipes; never a listener, shared env or pedagogical frame."""
    def __init__(self, packet: Mapping[str, object]) -> None:
        self._out = bytearray(encode_frame(dict(packet)))
        if len(self._out) > 16384:
            raise ValueError("PRIVATE_CHANNEL_BOUND")
        self._in = bytearray()
        self._read_child, self._write_parent = os.pipe()
        self._read_parent, self._write_child = os.pipe()
        self._fds = {self._read_child, self._write_parent, self._read_parent, self._write_child}
        self._sent = 0
        self.launch_options: dict[str, object] = {}
        if os.name == "nt":
            import msvcrt
            handles = [msvcrt.get_osfhandle(fd) for fd in (self._read_child, self._write_child)]
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {"handle_list": handles}
            self.launch_options = {"startupinfo": startup, "close_fds": True}
        else:
            handles = [self._read_child, self._write_child]
            self.launch_options = {"pass_fds": tuple(handles), "close_fds": True}
        self.arguments = ["--private-read", str(handles[0]), "--private-write", str(handles[1])]
        os.set_blocking(self._write_parent, False)
        os.set_blocking(self._read_parent, False)

    def __repr__(self) -> str:
        return "PrivateWorkerChannel([REDACTED])"

    def after_launch(self) -> None:
        for fd in (self._read_child, self._write_child):
            os.close(fd)
            self._fds.remove(fd)

    def pump(self) -> tuple[GenerationUsage, ...]:
        if self._sent < len(self._out):
            try:
                self._sent += os.write(self._write_parent, self._out[self._sent:self._sent + 4096])
            except BlockingIOError:
                pass
            if self._sent == len(self._out):
                self._out[:] = b"\x00" * len(self._out)
                os.close(self._write_parent)
                self._fds.remove(self._write_parent)
        try:
            chunk = os.read(self._read_parent, 4096)
        except BlockingIOError:
            chunk = b""
        self._in.extend(chunk)
        if len(self._in) > 16384:
            raise ValueError("PRIVATE_CHANNEL_BOUND")
        results = []
        while len(self._in) >= 4:
            size = struct.unpack("!I", self._in[:4])[0]
            if not 1 <= size <= 4096:
                raise ValueError("PRIVATE_CHANNEL_BOUND")
            if len(self._in) < size + 4:
                break
            results.append(decode_usage(decode_frame(bytes(self._in[:size + 4]))))
            del self._in[:size + 4]
        return tuple(results)

    def close(self) -> None:
        self._out[:] = b"\x00" * len(self._out)
        for fd in tuple(self._fds):
            os.close(fd)
            self._fds.remove(fd)
