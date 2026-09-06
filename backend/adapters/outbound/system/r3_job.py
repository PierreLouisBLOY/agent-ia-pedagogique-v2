"""One supervised, bounded synthetic child; production default remains unauthorized."""
import json
import multiprocessing
from collections.abc import Callable, Mapping
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from time import monotonic
from typing import cast

from backend.infrastructure.composition.bootstrap.r3_worker import run_synthetic_worker
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded, object_data
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import (
    R3JobRequest,
    R3JobResult,
    R3Rejected,
)


class UnapprovedR3Job:
    def authorize(self, request: R3JobRequest) -> None:
        raise R3Rejected("R3_NOT_AUTHORIZED")

    def start(self, request: R3JobRequest) -> None:
        raise R3Rejected("R3_NOT_AUTHORIZED")

    def poll(self) -> R3JobResult | None:
        return None

    def close(self) -> None:
        return None


class InjectedR3Job:
    """Explicit synthetic injection, no runtime credential or transport binding."""
    def __init__(self, handler: Callable[[R3JobRequest], Mapping[str, object]], *,
                 timeout: float = 90.0) -> None:
        if not 0 < timeout <= 90:
            raise ValueError("R3_TIMEOUT")
        self._handler, self._timeout = handler, timeout
        self._process: BaseProcess | None = None
        self._pipe: Connection | None = None
        self._request: R3JobRequest | None = None
        self._started = 0.0
        self._closed = False
        self._consumed: set[str] = set()

    def authorize(self, request: R3JobRequest) -> None:
        if self._closed or self._request is not None or request.operation_ref in self._consumed:
            raise R3Rejected("JOB_UNAVAILABLE")

    def start(self, request: R3JobRequest) -> None:
        self.authorize(request)
        r = request.revision
        raw = encoded({"operation_ref": request.operation_ref, "operation": request.operation,
            "revision": None if r is None else {"operation": r.operation,
                "production_ref": r.production_ref, "base_version_ref": r.base_version_ref,
                "subject": r.subject, "context": r.context, "references": r.references,
                "base": r.base.data if r.base else None},
            "bundle": request.bundle.data if request.bundle else None, "dimensions": request.dimensions})
        if len(raw) > 256 * 1024:
            raise R3Rejected("REQUEST_TOO_LARGE")
        context = multiprocessing.get_context("spawn")
        reader, writer = context.Pipe(duplex=False)
        process = context.Process(target=run_synthetic_worker, args=(self._handler, raw, writer), daemon=True)
        self._request, self._started, self._pipe, self._process = request, monotonic(), cast(Connection, reader), process
        try:
            self._consumed.add(request.operation_ref)
            process.start()
        except Exception:
            reader.close()
            self._pipe, self._process, self._request = None, None, None
            raise R3Rejected("JOB_UNAVAILABLE") from None
        finally:
            writer.close()

    def _finish(self) -> None:
        if self._pipe:
            self._pipe.close()
        if self._process and self._process.pid:
            self._process.join(0.2)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(2)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(2)
        self._pipe, self._process, self._request = None, None, None

    def poll(self) -> R3JobResult | None:
        pipe, process, request = self._pipe, self._process, self._request
        if pipe is None or process is None or request is None:
            return None
        if pipe.poll():
            try:
                data = object_data(json.loads(pipe.recv_bytes(256 * 1024)), {"state", "payload"})
                result = R3JobResult(request.operation_ref, str(data["state"]),
                    object_data(data["payload"]) if data["payload"] is not None else None)
            except (ValueError, EOFError, OSError):
                result = R3JobResult(request.operation_ref, "UNKNOWN")
            self._finish()
            return result
        if not process.is_alive() or monotonic() - self._started > self._timeout:
            self._finish()
            return R3JobResult(request.operation_ref, "UNKNOWN")
        return None

    def close(self) -> None:
        self._closed = True
        self._finish()
