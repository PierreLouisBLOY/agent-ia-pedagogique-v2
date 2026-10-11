"""Real loopback HTTP, pure Application proposal, no SQL or provider composition."""

import http.client
import json
import socket
import threading
from contextlib import contextmanager

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.api.read15 import Read15Endpoint
from backend.adapters.inbound.api.server import LocalRead15Server, LocalRead15Service
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.work_orchestration.application.queries.propose_p0_intention import (
    ProposeP0Intention,
)
from tests.unit.test_local_browser_http_contract import RecordingObservability


@contextmanager
def running():
    def forbidden(*args, **kwargs):
        raise AssertionError("Intention proposal must not invoke storage or generation.")

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    service = LocalRead15Service(LocalBrowserHttpConfiguration(port=port), Read15Endpoint(forbidden),
        RecordingObservability(), {"index.html": b"", "app.js": b"", "styles.css": b""},
        p0_endpoint=P0CreationEndpoint(forbidden, forbidden, [], nonce="synthetic-intent-nonce",
            intention_execute=ProposeP0Intention().execute))
    server = LocalRead15Server(service)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield port
    finally:
        server.stop()
        worker.join(timeout=5)
        assert not worker.is_alive()


@pytest.mark.parametrize("mutation,code", [
    (None, None), ("host", "HOST_REJECTED"), ("origin", "ORIGIN_REJECTED"),
    ("missing_origin", "ORIGIN_REJECTED"), ("nonce", "LOCAL_INTENT_REJECTED"),
    ("intent", "LOCAL_INTENT_REJECTED"), ("site", "ORIGIN_REJECTED"),
])
def test_companion_uses_existing_local_command_security_before_application(monkeypatch, mutation, code):
    calls = []
    original = ProposeP0Intention.execute

    def recording(self, body):
        calls.append(body)
        return original(self, body)

    monkeypatch.setattr(ProposeP0Intention, "execute", recording)
    with running() as port:
        headers = {"Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}",
                   "Content-Type": "application/json; charset=utf-8", "X-Local-Intent": "conversation-v1",
                   "X-R2-Nonce": "synthetic-intent-nonce", "Sec-Fetch-Site": "same-origin"}
        if mutation == "missing_origin":
            del headers["Origin"]
        elif mutation is not None:
            key = {"host": "Host", "origin": "Origin", "nonce": "X-R2-Nonce",
                   "intent": "X-Local-Intent", "site": "Sec-Fetch-Site"}[mutation]
            headers[key] = "cross-site" if mutation == "site" else "synthetic-wrong"
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request("POST", "/api/v2/p0/intention", body=json.dumps({"command_id": "a" * 32,
                "intention": "Un cours Première STMG sur les finalités, difficulté standard ; expliquer les finalités."}),
                headers=headers)
            response = connection.getresponse()
            payload = json.loads(response.read())
            if code is None:
                assert response.status == 200 and len(calls) == 1
                assert payload["data"]["contract_id"] == "P0-INTENTION-PROPOSAL-1.0"
                assert payload["data"]["confirmation_required"] is True
                assert payload["data"]["provider_attempts"] == 0
            else:
                assert response.status == 403 and calls == []
                assert payload["error"]["code"] == code
        finally:
            connection.close()
