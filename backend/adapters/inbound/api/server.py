"""Single-request loopback host; explicit dispatch, bounded input, no generic file serving."""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import MappingProxyType
from typing import Final

from backend.adapters.inbound.api.local_browser import (
    HttpObservabilityPort,
    LocalBrowserHttpSecurityContract,
)
from backend.adapters.inbound.api.read15 import Read15Endpoint, public_error
from backend.adapters.inbound.api.routes import (
    ASSET_NAMES,
    MAX_TARGET_BYTES,
    SEARCH_TEMPLATE,
    RouteRejected,
    resolve_route,
)
from backend.adapters.inbound.api.search import SearchEndpoint, public_search_error
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration

MAX_HEADER_BYTES: Final = 64 * 1_024
SOCKET_TIMEOUT_SECONDS: Final = 5.0
_TOKEN = re.compile(rb"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_METHOD = re.compile(rb"^[A-Z]{1,10}$")
_MEDIA = {"index.html": "text/html; charset=utf-8",
          "app.js": "text/javascript; charset=utf-8", "styles.css": "text/css; charset=utf-8"}
_CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; " \
       "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
_REASONS = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
            405: "Method Not Allowed", 500: "Internal Server Error"}


class _InputRejected(ValueError):
    def __init__(self, code: str = "READ15_REQUEST_REJECTED") -> None:
        self.code = code
        super().__init__(code)


class LocalRead15Service:
    def __init__(
        self, configuration: LocalBrowserHttpConfiguration, endpoint: Read15Endpoint,
        observability: HttpObservabilityPort, assets: Mapping[str, bytes],
        *, search_endpoint: SearchEndpoint | None = None,
    ) -> None:
        if configuration.cors_enabled:
            raise ValueError("CORS must remain disabled for READ15-HTTP-LOCAL-1.0")
        if set(assets) != ASSET_NAMES or any(type(value) is not bytes for value in assets.values()):
            raise ValueError("asset inventory mismatch")
        self.configuration = configuration
        self.endpoint = endpoint
        self.search_endpoint = search_endpoint
        self.observability = observability
        self.security = LocalBrowserHttpSecurityContract(configuration, observability)
        self.assets = MappingProxyType(dict(assets))

    def respond(
        self, method: str, target: str, headers: Mapping[str, str], correlation_id: str,
    ) -> tuple[int, str, bytes, str]:
        decision = self.security.authorize_request(
            method=method, host_header=headers.get("host", ""),
            origin=headers.get("origin"), incoming_correlation_id=correlation_id,
        )
        if not decision.allowed:
            minimized = self.security.client_error(
                decision, status_code=405 if decision.code.value == "METHOD_REJECTED" else 403
            )
            return self.error(minimized.error_code.value, correlation_id)
        try:
            match = resolve_route(method, target)
        except RouteRejected as error:
            return self.error(error.code, correlation_id)
        if match.asset_name is not None:
            return 200, _MEDIA[match.asset_name], self.assets[match.asset_name], match.template
        if match.template == SEARCH_TEMPLATE:
            if (self.search_endpoint is None or match.search_text is None
                    or match.search_limit is None):
                return self.error("INTERNAL_ERROR", correlation_id)
            search_projection = self.search_endpoint.get(
                match.search_text, match.search_limit, correlation_id,
            )
            return (
                search_projection.status, "application/json; charset=utf-8",
                json.dumps(dict(search_projection.payload), ensure_ascii=False).encode("utf-8"),
                match.template,
            )
        if match.resource_ref is None:
            return self.error("INTERNAL_ERROR", correlation_id)
        projection = self.endpoint.get(match.resource_ref, correlation_id)
        return (
            projection.status, "application/json; charset=utf-8",
            json.dumps(dict(projection.payload), ensure_ascii=True).encode("utf-8"),
            match.template,
        )

    def error(self, code: str, correlation_id: str) -> tuple[int, str, bytes, str]:
        if code == "INTERNAL_ERROR":
            code = self.security.internal_error(correlation_id=correlation_id).error_code.value
        projection = (public_search_error(code, correlation_id)
                      if code == "SEARCH_REQUEST_REJECTED" else public_error(code, correlation_id))
        return (
            projection.status, "application/json; charset=utf-8",
            json.dumps(dict(projection.payload)).encode("utf-8"), "/{unmatched}",
        )


class LocalRead15Server(HTTPServer):
    """No background threads are created by the server itself."""

    allow_reuse_address = False
    request_queue_size = 1

    def __init__(self, service: LocalRead15Service) -> None:
        self.service = service
        self._running = threading.Event()
        self._stopping = threading.Event()
        self._active: socket.socket | None = None
        self._active_lock = threading.Lock()
        self._owner_thread: int | None = None
        if service.configuration.bind_host == "::1":
            self.address_family = socket.AF_INET6
        super().__init__(
            (service.configuration.bind_host, service.configuration.port), _LocalHandler
        )

    def server_bind(self) -> None:
        # HTTPServer normally performs reverse DNS here. Only bind the supplied literal.
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()
        self.server_name = self.service.configuration.bind_host
        self.server_port = self.service.configuration.port

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        request, address = self.socket.accept()
        request.settimeout(SOCKET_TIMEOUT_SECONDS)
        with self._active_lock:
            self._active = request
        return request, (str(address[0]), int(address[1]))

    def close_request(self, request: socket.socket | tuple[bytes, socket.socket]) -> None:
        if not isinstance(request, socket.socket):
            raise TypeError("TCP_REQUEST_REQUIRED")
        with self._active_lock:
            if self._active is request:
                self._active = None
        super().close_request(request)

    def serve_forever(self, poll_interval: float = 0.05) -> None:
        self._owner_thread = threading.get_ident()
        self._stopping.clear()
        self._running.set()
        try:
            super().serve_forever(poll_interval=poll_interval)
        finally:
            self._running.clear()
            self._owner_thread = None

    def stop(self) -> None:
        self._stopping.set()
        with self._active_lock:
            if self._active is not None:
                try:
                    self._active.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        if self._running.is_set() and self._owner_thread != threading.get_ident():
            self.shutdown()
        self.server_close()

    def handle_error(
        self, request: socket.socket | tuple[bytes, socket.socket],
        client_address: tuple[str, int],
    ) -> None:
        # Never delegate to the stdlib diagnostic printer.
        self.service.observability.security_rejected(
            runtime_boundary=True, boundary="HTTP_LOCAL_BROWSER", policy_code="INTERNAL_ERROR"
        )


class _LocalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server: LocalRead15Server

    def log_message(self, format: str, *args: object) -> None:
        return

    def handle_one_request(self) -> None:
        self.close_connection = True
        started = time.monotonic()
        self._deadline = started + SOCKET_TIMEOUT_SECONDS
        self._input_buffer = bytearray()
        method = "UNKNOWN"
        service = self.server.service
        # Untrusted headers never determine this request's identity or grant permissions.
        correlation = service.observability.correlation_id(None)
        try:
            method, target, headers = self._read_bounded()
            status, media, body, template = service.respond(method, target, headers, correlation)
        except _InputRejected as error:
            status, media, body, template = service.error(error.code, correlation)
            service.observability.validation_rejected(
                boundary="HTTP", rule_code=error.code, field_code="request",
                correlation_id=correlation,
            )
        except (TimeoutError, OSError):
            status, media, body, template = service.error("READ15_REQUEST_REJECTED", correlation)
        except Exception:
            status, media, body, template = service.error("INTERNAL_ERROR", correlation)
        parsed_method = getattr(self, "command", "UNKNOWN")
        method = parsed_method if parsed_method in {
            "GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"
        } else "UNKNOWN"
        try:
            self.connection.settimeout(SOCKET_TIMEOUT_SECONDS)
            self._write_response(status, media, body, method == "HEAD", correlation)
        except (OSError, TimeoutError):
            pass
        finally:
            service.observability.http_request(
                method=method, route_template=template, status_code=status,
                duration_ms=max(0, int((time.monotonic() - started) * 1_000)),
                incoming_correlation_id=correlation,
            )

    def _line(self, limit: int) -> bytes:
        while True:
            if self.server._stopping.is_set():
                raise OSError("SERVER_STOPPING")
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            newline = self._input_buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._input_buffer[:newline + 1])
                del self._input_buffer[:newline + 1]
                if len(line) > limit or not line.endswith(b"\r\n"):
                    raise _InputRejected()
                return line
            if len(self._input_buffer) > limit:
                raise _InputRejected()
            self.connection.settimeout(min(0.1, remaining))
            try:
                chunk = self.connection.recv(min(4_096, limit + 1 - len(self._input_buffer)))
            except TimeoutError:
                continue
            if not chunk:
                raise _InputRejected()
            self._input_buffer.extend(chunk)

    def _read_bounded(self) -> tuple[str, str, dict[str, str]]:
        # Both budgets are enforced on raw bytes before header parsing or dispatch.
        line = self._line(MAX_TARGET_BYTES + 32)
        parts = line[:-2].split(b" ")
        if len(parts) != 3:
            raise _InputRejected()
        verb, target, version = parts
        if (
            _METHOD.fullmatch(verb) is None or len(target) > MAX_TARGET_BYTES
            or version not in {b"HTTP/1.0", b"HTTP/1.1"}
            or not target or any(byte <= 32 or byte >= 127 for byte in target)
        ):
            raise _InputRejected()
        # Preserve HEAD even for an error while reading its subsequent headers.
        self.command = verb.decode("ascii")
        headers: dict[str, str] = {}
        total = 0
        while True:
            line = self._line(MAX_HEADER_BYTES - total)
            total += len(line)
            if line == b"\r\n":
                break
            key, separator, value = line[:-2].partition(b":")
            if not separator or _TOKEN.fullmatch(key) is None:
                raise _InputRejected()
            name = key.decode("ascii").lower()
            if name in headers:
                raise _InputRejected(
                    "HOST_REJECTED" if name == "host" else
                    "ORIGIN_REJECTED" if name == "origin" else "READ15_REQUEST_REJECTED"
                )
            value = value.strip(b" \t")
            if any(byte < 32 or byte >= 127 for byte in value):
                raise _InputRejected()
            headers[name] = value.decode("ascii")
        if (
            "transfer-encoding" in headers or headers.get("content-length", "0") != "0"
            or any(name in headers for name in ("expect", "authorization", "cookie",
                                                "proxy-authorization"))
        ):
            raise _InputRejected()
        return self.command, target.decode("ascii"), headers

    def _write_response(
        self, status: int, media: str, body: bytes, head: bool, correlation_id: str
    ) -> None:
        header = (
            f"HTTP/1.0 {status} {_REASONS[status]}\r\n"
            f"Content-Type: {media}\r\nContent-Length: {len(body)}\r\n"
            f"X-Correlation-Id: {correlation_id}\r\n"
            "Connection: close\r\nCache-Control: no-store\r\n"
            "X-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n"
            f"Content-Security-Policy: {_CSP}\r\n\r\n"
        )
        self.wfile.write(header.encode("ascii"))
        if not head:
            self.wfile.write(body)
