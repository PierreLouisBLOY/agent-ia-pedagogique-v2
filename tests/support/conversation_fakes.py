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
    mode = sys.argv[1]
    if mode.startswith("private-"):
        return corrective_worker_main(mode)
    request = read_request(sys.stdin.buffer)
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


def corrective_scope():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "docs/development/phase_12_18_h2_r2_generation/LIVE_GENERATION_SCOPE.json").read_text("utf-8"))


def corrective_grant(target, receipt_root=None):
    """SYNTHETIC GRANT AND COUNTER RECEIPT: no account, count or live permission."""
    from backend.infrastructure.composition.factories.conversation import (
        r2_count_handoff,
        r2_digest,
        r2_environment_identity,
    )
    scope = corrective_scope()
    count = r2_count_handoff(scope["projection"])
    proof = {"kind": "AUTHORIZED_PROVIDER_COUNT", "input_tokens": 3000,
        "generation_request_sha256": count["generation_request_sha256"],
        "count_request_sha256": count["count_request_sha256"],
        "count_authorization_sha256": "a" * 64, "count_cost_status": "APPROVED_BOUND"}
    return {"schema": "R2-GENERATION-GRANT-1.0", "operation": "GENERATION",
        "baseline_commit": "f" * 40, "scope_sha256": r2_digest(scope),
        **{k: scope[k] for k in ("projection_sha256", "profile_sha256", "pricing_sha256", "output_schema_sha256", "usage_contract_sha256")},
        "provider": "OPENAI_ONLY", "max_calls": 1, "ceiling_usd": "0.140000",
        "live_authorized": True, "transfer_authorized": True,
        "credential_source": "MASKED_LOCAL_PRIVATE_CHANNEL",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        "token_count_receipt": proof, "token_count_receipt_sha256": r2_digest(proof),
        "receipt_root_sha256": r2_digest(str(receipt_root.absolute()).casefold()) if receipt_root else "b" * 64,
        "runtime_sha256": target.expected_sha256, "environment": r2_environment_identity()}


def corrective_process_job(tmp_path, *, mode="private-candidate", timeout=120):
    import subprocess

    from backend.infrastructure.composition.factories.conversation import build_r2_process_job
    from tests.support.conversation_synthetic import synthetic_target
    target = synthetic_target(tmp_path / "synthetic")
    inputs = []
    def read_fake():
        inputs.append("FAKE_INPUT")
        return "SYNTHETIC_PRIVATE_CHANNEL_VALUE_NOT_A_CREDENTIAL"
    job = build_r2_process_job(grant=corrective_grant(target, tmp_path / "receipts"), scope=corrective_scope(), baseline="f" * 40,
        target=target, receipt_root=tmp_path / "receipts", private_temp=tmp_path,
        credential_input=read_fake)
    def launch(args, **kwargs):
        assert args[1:3] == ["-m", "backend.infrastructure.composition.bootstrap.conversation_worker"]
        assert args[3] == "--private-read" and args[5] == "--private-write"
        assert "SYNTHETIC_PRIVATE_CHANNEL" not in repr((args, kwargs))
        assert not any(k.startswith("OPENAI_") for k in kwargs["env"])
        return subprocess.Popen([args[0], "-m", "tests.support.conversation_fakes", mode, *args[3:]], **kwargs)
    job.launch, job.timeout = launch, timeout
    return job, target, inputs


def corrective_worker_main(mode):
    import argparse
    import sys

    from backend.adapters.outbound.openai.contracts import (
        OpenAIResponsesResponse,
        OpenAIResponseStatus,
        OpenAIResponseUsage,
    )
    from backend.adapters.outbound.system.conversation_job import encode_frame, result_payload
    from backend.infrastructure.composition.bootstrap.conversation_worker import (
        private_pipe,
        read_private_packet,
        read_request,
        run_authorized_generation,
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-read", type=int, required=True)
    parser.add_argument("--private-write", type=int, required=True)
    args = parser.parse_args(sys.argv[2:])
    calls = []
    class Factory:
        def build(self, *, secret, timeout_seconds):
            assert secret.reveal_for_transport() == "SYNTHETIC_PRIVATE_CHANNEL_VALUE_NOT_A_CREDENTIAL"
            assert timeout_seconds == 90
            return self
        def create(self, *, request):
            calls.append("FAKE_CREATE")
            assert len(calls) == 1 and request.service_tier == "default"
            if mode == "private-timeout":
                time.sleep(30)
            value = {"outcome": "OUTPUT", "sections": [{"code": code,
                "text": "Question substantielle synthétique détaillée, sans appel fournisseur."} for code in SECTION_IDS],
                "warnings": [], "uncertainties": [], "evidence_ids_used": ["r2.evidence.1"]}
            status = OpenAIResponseStatus.REFUSED if mode == "private-refused" else (
                OpenAIResponseStatus.INCOMPLETE if mode == "private-incomplete" else OpenAIResponseStatus.COMPLETED)
            return OpenAIResponsesResponse(status=status,
                output_text="{" if mode == "private-invalid" else json.dumps(value),
                usage=OpenAIResponseUsage(input_tokens=3000, cached_input_tokens=100,
                    cache_write_input_tokens=200, output_tokens=1000, total_tokens=4000, reasoning_tokens=100),
                service_tier="default")
    with private_pipe(args.private_read, "rb") as source, private_pipe(args.private_write, "wb") as sink:
        packet = read_private_packet(source)
        assert set(packet) == {"grant", "runtime_path", "data_root", "secret"}
        request = read_request(sys.stdin.buffer)
        result = run_authorized_generation(packet, request=request, sink=sink,
            material=("f" * 40, corrective_scope()), transport_factory=Factory())
        assert calls == ["FAKE_CREATE"]
        if mode == "private-disconnect":
            return 1
        sys.stdout.buffer.write(encode_frame(result_payload(result)))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(synthetic_worker_main())
