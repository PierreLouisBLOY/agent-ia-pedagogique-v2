"""Actual CLI/normal factories/HTTP/coverage/R4, only effect/source ports synthetic."""

from decimal import Decimal
from threading import Event, Thread

from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.contracts import BudgetSpec
from backend.infrastructure.composition.factories.p0_codesign import P0CoDesignBinding
from tests.test_codesign_global_324 import Generation, Guard, Review, Search
from tests.test_normal_on_323a import accept, call, f, prepare, terminal


def test_normal_startup_http_slow_followup_codesign_saved_reopen_compare_word(
    tmp_path, monkeypatch
):
    from backend.adapters.outbound.generation.p0_codesign_runtime import _Run

    original_run = _Run.run
    diagnostics = []

    def observed_run(self, **kwargs):
        try:
            return original_run(self, **kwargs)
        except Exception as error:
            diagnostics.append((type(error).__name__, str(error)))
            raise

    monkeypatch.setattr(_Run, "run", observed_run)
    from backend.infrastructure.composition.factories import local_browser as normal_factory

    original_factory = normal_factory.build_p0_creation
    generation, reviewer = Generation(f.CONTENT), Review(correction=True)
    owner = {}

    def configured(*args, **kwargs):
        # Declared synthetic scope is independent of the CREATE-only fixture.
        # Production inventory/coverage, validators, CLI and R4 remain unchanged.
        binding = P0CoDesignBinding(
            search=Search(),
            generation=generation,
            review=P0ReviewAdapter(reviewer, authorize=lambda _: True),
            guard=Guard(),
            envelope=BudgetSpec(max_retries=0, max_cost=Decimal("1.00")),
            permission_scope_ref="scope:SYNTHETIC_GLOBAL_324",
            authorize=lambda _: True,
        )
        service, endpoint = original_factory(*args, **kwargs, codesign=binding)
        owner["service"] = service
        return service, endpoint

    monkeypatch.setattr(normal_factory, "build_p0_creation", configured)
    control = f.Control()
    with f.running(tmp_path / "SYNTHETIC-startup", monkeypatch, control) as (port, configuration):
        nonce, command, shown = prepare(port)
        decision = accept(command, shown)
        status, result = call(port, "POST", "/api/v2/p0/consent-generate", decision, nonce)
        assert status == 202
        initial = terminal(port, decision["command_id"])
        assert initial["state"] == "LOCAL_COMMAND_COMPLETED"
        parent = initial["result"]["view"]
        request = {
            "command_id": "a" * 32,
            "production_ref": parent["production_ref"],
            "version_ref": parent["version_ref"],
            "bundle_sha256": parent["bundle_sha256"],
            "direction": "V2_TO_AI",
            "evidence_query": None,
            "objective": "Clarifier le titre",
        }
        status, preview = call(
            port, "POST", "/api/v2/p0/codesign-preview", {**request, "command_id": "b" * 32}, nonce
        )
        assert status == 200 and preview["data"]["authority"] == "NONE"
        assert generation.calls == reviewer.calls == []
        entered, release = Event(), Event()
        original_generate = generation.generate

        def slow(*, request):
            entered.set()
            assert release.wait(20)
            return original_generate(request=request)

        generation.generate = slow
        result_box = []
        worker = Thread(
            target=lambda: result_box.append(
                call(port, "POST", "/api/v2/p0/codesign", request, nonce)
            )
        )
        worker.start()
        try:
            assert entered.wait(20), (result_box, diagnostics)
            status, passive = call(
                port,
                "GET",
                "/api/v2/p0/versions/" + parent["production_ref"] + "/" + parent["version_ref"],
            )
            assert status == 200 and passive["data"]["bundle_sha256"] == parent["bundle_sha256"]
            status, following = call(port, "GET", "/api/v2/p0/commands/" + request["command_id"])
            assert status == 200 and following["data"]["state"] == "LOCAL_COMMAND_RUNNING"
        finally:
            release.set()
            worker.join(30)
        assert not worker.is_alive()
        status, submitted = result_box[0]
        assert status == 202 and submitted["data"]["command_id"] == request["command_id"]
        observed = terminal(port, request["command_id"])
        assert observed["state"] == "LOCAL_COMMAND_COMPLETED", observed
        final = observed["result"]
        assert final["state"] == "CODESIGN_CANDIDATE", final
        view = final["view"]
        assert len(generation.calls) == len(reviewer.calls) == 2
        status, repeated = call(port, "POST", "/api/v2/p0/codesign", request, nonce)
        assert status == 202 and repeated["data"]["result"] == final
        base = "/api/v2/productions/" + view["production_ref"] + "/versions/" + view["version_ref"]
        status, opened = call(port, "GET", base + "/saved")
        assert status == 200 and opened["data"]["active_authority"] == "NONE_RESTORED"
        status, comparison = call(port, "GET", base + "/compare/student")
        assert status == 200 and comparison["data"]["promotion"] == "NOT_PERFORMED"
        for kind in ("student", "correction"):
            status, raw = f.request(port, "GET", base + "/word/" + kind)
            assert status == 200 and raw[:2] == b"PK"
        assert control.calls == control.builds == 1
        assert control.prompt_calls == 0
    # Reopening through R4 only consumes no agent port, no prompt or effect.
    from backend.infrastructure.composition.factories.local_browser import build_saved_application

    reopened = build_saved_application(configuration[2], word_profile="product-v7")
    record = reopened.read_local_p0(view["production_ref"], view["version_ref"])
    assert len(record.data["codesign"]["trace"]["operations"]) == 2
    assert len(generation.calls) == len(reviewer.calls) == 2
