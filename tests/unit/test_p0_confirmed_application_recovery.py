"""Declared captured-effect double and real Application persistence, no provider."""
from secrets import token_hex

import pytest

from backend.infrastructure.composition.factories.local_browser import (
    bind_confirmed_p0_publication,
    build_saved_application,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.integration.test_p0_creation_http import context
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_creation_contract import service


class CapturedEffectDouble(P0GenerationDouble):
    """Simulates a single normalized capture; recovery has no executable port."""
    dispatch = None
    captured = None
    recovery_calls = 0

    def generate(self, *, request):
        self.dispatch = as_plain(request)
        self.captured = as_plain(super().generate(request=request))
        return self.captured

    def confirmed_dispatch(self):
        return self.dispatch

    def recover_confirmed(self, *, request):
        self.recovery_calls += 1
        assert as_plain(request) == self.dispatch
        return self.captured


def prepare(app):
    return app.execute("prepare", {"command_id": token_hex(16),
        "context": context("BTS_CG_YEAR_2", "ASSESSMENT", None), "reference": {}})


def bind(app, port, root, *, create=False):
    saved = build_saved_application(root, create=create, source=app.saved_source,
                                    word_profile="product-v7")
    app.saved_reader = saved.read_local_p0
    bind_confirmed_p0_publication(app, saved, port)
    return saved


def test_confirmed_effect_survives_stop_before_save_and_recovery_never_dispatches(tmp_path):
    port = CapturedEffectDouble()
    first = service(port)
    prep = prepare(first)
    # Simulate process termination after the technical capture, before Application publish.
    port.generate(request=first.prepared[prep["preparation_ref"]])
    assert len(port.requests) == 1
    port.authorize = port.generate = lambda **kwargs: pytest.fail("Recovery attempted dispatch")
    resumed = service(port)
    saved = bind(resumed, port, tmp_path / "library", create=True)
    exact = saved.read_local_p0(port.dispatch["production_ref"], port.dispatch["version_ref"])
    assert exact.p0_bundle.sha256 == resumed.records[exact.version_ref].sha256
    assert len(port.requests) == port.recovery_calls == 1
    assert resumed._memory(exact.p0_bundle)["quality"]["sources"] == "RESERVE"
    before = exact.sha256
    again = service(port)
    reopened = bind(again, port, tmp_path / "library")
    assert reopened.read_local_p0(exact.production_ref, exact.version_ref).sha256 == before
    assert len(port.requests) == 1 and port.recovery_calls == 2
    assert again.prepared == {} and again.review_consumed == set()


def test_normal_result_is_saved_before_success_and_publication_failure_is_not_success(tmp_path):
    port = CapturedEffectDouble()
    app = service(port)
    saved = bind(app, port, tmp_path / "library", create=True)
    prep = prepare(app)
    result = app.execute("generate", {"command_id": token_hex(16),
        "preparation_ref": prep["preparation_ref"], "preparation_sha256": prep["preparation_sha256"]})
    pub = result["publication"]
    assert pub["state"] == "APPLICATION_SAVED"
    assert saved.read_local_p0(pub["production_ref"], pub["version_ref"]).sha256 == pub["record_sha256"]
    failed_port = CapturedEffectDouble()
    failed = service(failed_port)
    failed.publish_generated = lambda *args: (_ for _ in ()).throw(OSError("PRIVATE_DETAIL"))
    prep = prepare(failed)
    command = {"command_id": token_hex(16), "preparation_ref": prep["preparation_ref"],
               "preparation_sha256": prep["preparation_sha256"]}
    with pytest.raises(ValueError, match="P0_OUTCOME_UNKNOWN"):
        failed.execute("generate", command)
    assert failed.execute("generate", command)["state"] == "OUTCOME_UNKNOWN"
    assert len(failed_port.requests) == 1 and failed_port.captured is not None


@pytest.mark.parametrize("field", ("production_ref", "version_ref", "references", "lineage", "title"))
def test_recovery_rejects_substituted_output_or_existing_version(tmp_path, field):
    port = CapturedEffectDouble()
    first = service(port)
    saved = bind(first, port, tmp_path / "library", create=True)
    prep = prepare(first)
    result = first.execute("generate", {"command_id": token_hex(16),
        "preparation_ref": prep["preparation_ref"], "preparation_sha256": prep["preparation_sha256"]})
    pub = result["publication"]
    if field in {"production_ref", "version_ref"}:
        port.captured[field] = field[:3] + ":" + "f" * 32
    elif field == "references":
        port.captured[field][0]["excerpt_sha256"] = "0" * 64
    elif field == "lineage":
        port.captured[field]["source_request_id"] = "req:" + "e" * 32
    else:
        port.captured[field] = "A different confirmed result cannot replace the original"
    fresh = service(port)
    with pytest.raises(ValueError):
        bind(fresh, port, tmp_path / "library")
    assert saved.read_local_p0(pub["production_ref"], pub["version_ref"]).sha256 == pub["record_sha256"]
    assert len(port.requests) == 1


def test_recovery_missing_capability_or_unknown_capture_fails_closed(tmp_path):
    unavailable = service(P0GenerationDouble())
    with pytest.raises(ValueError, match="P0_CONFIRMED_RECOVERY_UNAVAILABLE"):
        unavailable.recover_confirmed_generation({})
    port = CapturedEffectDouble()
    app = service(port)
    port.confirmed_dispatch = lambda: (_ for _ in ()).throw(ValueError("P0_CAPTURE_UNKNOWN"))
    with pytest.raises(ValueError, match="P0_CAPTURE_UNKNOWN"):
        bind(app, port, tmp_path / "library", create=True)
    assert app.records == {} and port.requests == []


def test_normal_guard_warnings_remain_reserves_in_application_and_after_restart(tmp_path):
    from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
    from tests.unit.test_p0_normal_generation import synthetic_configuration

    config, app, prep, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    import json

    from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
    from backend.adapters.outbound.openai.contracts import (
        OpenAIResponsesResponse,
        OpenAIResponseStatus,
    )
    content = json.loads(transport.response.output_text)
    content["title"] = "Source officielle — déjà validé"  # deliberately retain a scanner warning
    transport.response = OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED,
        canonical(content).decode(), transport.response.usage, service_tier="default")
    adapter = NormalP0GenerationAdapter(**config)
    app.generation = adapter
    saved = bind(app, adapter, tmp_path / "library", create=True)
    result = app.execute("generate", {"command_id": token_hex(16),
        "preparation_ref": prep["preparation_ref"], "preparation_sha256": prep["preparation_sha256"]})
    assert result["agentic"]["quality"]["sources"] == "RESERVE"
    controls = result["agentic"]["generation_controls"]
    assert controls["source_usage_declaration"] == "NOT_IN_OUTPUT_SCHEMA"
    assert controls["declared_evidence_refs_used"] == [] and controls["guard_warnings"]
    pub = result["publication"]
    record = saved.read_local_p0(pub["production_ref"], pub["version_ref"])
    assert "SOURCE_USAGE_NOT_DECLARED" in record.data["reservations"]
    assert "GENERATION_CONTROL_SHA256" in record.data["provenance"]
    resolver.resolve = lambda *args, **kwargs: pytest.fail("Recovery resolved a secret")
    transport.build = lambda *args, **kwargs: pytest.fail("Recovery constructed a transport")
    # Expiry cannot restore a right; it does not prevent read-only recovery.
    from datetime import timedelta

    from tests.unit.test_p0_normal_generation import NOW
    config["clock"] = lambda: NOW + timedelta(days=7)
    resumed = service(NormalP0GenerationAdapter(**config))
    reopened = bind(resumed, resumed.generation, tmp_path / "library")
    assert reopened.read_local_p0(record.production_ref, record.version_ref).sha256 == record.sha256
    assert resumed._memory(record.p0_bundle)["quality"]["sources"] == "RESERVE"
    assert resolver.calls == transport.calls == 1
