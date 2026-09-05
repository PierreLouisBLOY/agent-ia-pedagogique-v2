"""Synthetic-only doubles and deterministic clock; never imported by product code."""
import http.client
import json
import socket
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from backend.adapters.outbound.persistence.conversation_memory import ConversationMemoryStore
from backend.modules.pedagogical_context.application.services.conversation_context import (
    ConversationContextService,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    SECTION_IDS,
    ConversationDraft,
)
from backend.modules.work_orchestration.application.services.conversation import (
    ConversationService,
    initial_conversation,
)
from backend.modules.work_orchestration.contracts.dto.conversation import (
    ConversationCommand,
    ConversationRejected,
)
from backend.modules.work_orchestration.ports.outbound.generation_job import GenerationJobResult

PILOT = "Crée un contrôle BTS CG de 1 h sur le bilan fonctionnel et le BFR, noté sur 20."
CONTEXT = {
    "resource_type": "ASSESSMENT", "level": "BTS_CG_YEAR_2", "discipline": "analyse financière",
    "topics": ["bilan fonctionnel", "BFR"],
    "objectives": ["identifier les emplois et ressources stables", "calculer le FRNG et le BFR",
                   "interpréter la trésorerie nette"],
    "difficulty": "STANDARD", "duration_minutes": 60, "total_points": "20", "language": "fr",
}


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 5, 12, tzinfo=UTC)

    def __call__(self):
        return self.value


class Ids:
    def __init__(self):
        self.counter = 0

    def __call__(self, prefix):
        self.counter += 1
        return f"{prefix}:{self.counter:032x}"


class FakeJobs:
    def __init__(self):
        self.calls = []
        self.result = None
        self.denied = None
        self.closed = False

    def authorize(self, request):
        if self.denied:
            raise ConversationRejected(self.denied)

    def start(self, request):
        self.calls.append(request)

    def poll(self):
        result, self.result = self.result, None
        return result

    def close(self):
        self.closed = True

    def succeed(self, production=1):
        self.result = GenerationJobResult(self.calls[-1].generation_id, "CANDIDATE_READY",
                                           draft=sample_draft(production))


def sample_draft(production=1):
    sections = tuple({"section_id": code, "text": f"{code} : question synthétique détaillée pour le test."}
                     for code in SECTION_IDS)
    return ConversationDraft(
        f"prod:{production:032x}", "Sujet synthétique non issu d’un fournisseur.", sections,
        ({"evidence_id": "r2.synth.bilan", "source_ref": "doc:r2-synth-bilan", "version_ref": "v1",
          "checksum_sha256": "a" * 64, "locator": "r2.synth.bilan",
          "provenance_label": "SUPPORT_SYNTHETIQUE_R2 — aucune source officielle attestée",
          "declared_used": True},),
        {"source_run_id": "r2-test-run", "source_step_id": "r2-generation",
         "evidence_set_ref": "r2-test-evidence"}, ("CANDIDATE — NON VALIDÉE",),
    )


def harness():
    clock, ids, jobs = Clock(), Ids(), FakeJobs()
    conversation_id = ids("conv")
    expires = clock() + timedelta(hours=2)
    store = ConversationMemoryStore(initial_conversation(conversation_id, expires))
    service = ConversationService(conversation_id=conversation_id, store=store, jobs=jobs,
                                  contexts=ConversationContextService(), new_id=ids, clock=clock,
                                  expires_at=expires)
    return service, store, jobs, clock


def command(service, number, text=PILOT, *, operation="messages", **extra):
    view = service.snapshot()
    body = {"command_id": f"00000000-0000-0000-0000-{number:012x}",
            "conversation_id": view["conversation_id"], "expected_revision": view["revision"]}
    if operation == "messages":
        body.update(text=text, **extra)
    else:
        body.update(confirmed_context_sha256=view["confirmed_context_sha256"], **extra)
    return ConversationCommand(operation, body)


def confirm(service, number=1):
    return service.execute(command(service, number, context_patch=CONTEXT, confirm_context=True))


@contextmanager
def running_conversation(tmp_path, *, jobs=None, enabled=True):
    from backend.infrastructure.composition.factories.local_browser import build_local_read15
    from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
    from tests.support.conversation_synthetic import synthetic_target
    target = synthetic_target(tmp_path / "synthetic")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    composition = build_local_read15(LocalBrowserHttpConfiguration(port=port), target,
                                     enable_conversation=enabled, generation_jobs=jobs)
    thread = threading.Thread(target=composition.serve_forever, daemon=True)
    thread.start()
    assert composition.server._running.wait(2)
    try:
        yield composition, target
    finally:
        composition.close()
        thread.join(3)
        assert not thread.is_alive()


def http_call(composition, path="/api/v2/conversation", *, body=None, headers=None, method=None):
    port = composition.server.service.configuration.port
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=7)
    merged = {"X-Local-Intent": "conversation-v1"}
    if body is not None:
        merged.update({"Content-Type": "application/json; charset=utf-8",
            "Origin": f"http://127.0.0.1:{port}",
            "X-R2-Nonce": composition.conversation.endpoint.nonce})
    merged.update(headers or {})
    try:
        connection.request(method or ("POST" if body is not None else "GET"), path,
                           json.dumps(body).encode() if body is not None else None, headers=merged)
        response = connection.getresponse()
        raw = response.read()
        return response.status, dict(response.getheaders()), json.loads(raw)
    finally:
        connection.close()


def http_command(composition, number, *, operation="messages", **fields):
    status, _, envelope = http_call(composition)
    assert status == 200
    view = envelope["data"]["conversation"]
    body = {"command_id": f"00000000-0000-0000-0000-{number:012x}",
            "conversation_id": view["conversation_id"], "expected_revision": view["revision"], **fields}
    return http_call(composition, "/api/v2/conversation/" + operation, body=body), body


def wait_terminal(composition):
    # Harness wait is distinct from the product's 120s watchdog. Leave bounded
    # headroom for a fresh Python child during concurrent lint/typecheck runs.
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        status, _, data = http_call(composition)
        assert status == 200
        view = data["data"]["conversation"]
        if view["active_generation"] and view["active_generation"]["state"] != "IN_PROGRESS":
            return view
        time.sleep(.02)
    raise AssertionError("synthetic worker did not terminate")


def process_job(tmp_path, *, mode="candidate", timeout=120, digest="b" * 64):
    import subprocess
    import sys
    from decimal import Decimal
    from pathlib import Path

    from backend.adapters.outbound.system.conversation_job import (
        ConversationProcessJob,
        OneShotReceipt,
    )
    root = Path(__file__).resolve().parents[2]
    def launch(args, **kwargs):
        assert args[1:] == ["-m", "backend.infrastructure.composition.bootstrap.conversation_worker"]
        return subprocess.Popen([args[0], "-m", "tests.support.conversation_fakes", mode], **kwargs)
    environment = {"SystemRoot":"C:/Windows", "WINDIR":"C:/Windows", "TEMP":str(tmp_path),
                   "TMP":str(tmp_path), "PYTHONPATH":str(root), "PYTHONDONTWRITEBYTECODE":"1",
                   "PYTHONIOENCODING":"utf-8"}
    tmp_path.mkdir(parents=True, exist_ok=True)
    return ConversationProcessJob(executable=Path(sys.executable), working_directory=root,
        environment=environment, authorize=lambda request: None,
        receipt=OneShotReceipt(tmp_path / "receipts", digest, Decimal("0")), launch=launch, timeout=timeout)


def synthetic_worker_main():
    import struct
    import sys
    import tempfile
    from decimal import Decimal
    from pathlib import Path

    from backend.adapters.outbound.system.conversation_job import encode_frame, result_payload
    from backend.infrastructure.composition.bootstrap.conversation_worker import (
        read_request,
        run_generation,
    )
    from tests.support.conversation_synthetic import synthetic_target
    from tests.unit.test_conversation_generation import SyntheticGenerationPort
    request = read_request(sys.stdin.buffer)
    mode = sys.argv[1]
    if mode == "blocked":
        time.sleep(30)
        return 1
    if mode == "oversize":
        sys.stdout.buffer.write(struct.pack("!I", 256 * 1024 + 1))
        return 0
    if mode == "malformed":
        sys.stdout.buffer.write(encode_frame({"private":"PRIVATE_TEST_MARKER"}))
        return 0
    target = synthetic_target(Path(tempfile.mkdtemp(prefix="r2-worker-synth-")) / "fixture")
    port = SyntheticGenerationPort()
    if mode == "invalid-output":
        port.empty_used = True
    result = run_generation(request, target=target, generation=port, reserved_cost=Decimal("0"))
    sys.stdout.buffer.write(encode_frame(result_payload(result)))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(synthetic_worker_main())
