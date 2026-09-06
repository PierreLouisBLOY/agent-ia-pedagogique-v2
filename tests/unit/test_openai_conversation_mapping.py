import json
from dataclasses import replace

import pytest

from backend.adapters.outbound.generation.openai.adapter import _map_response
from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.adapters.outbound.openai.contracts import (
    OpenAIReasoningEffort,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
)
from backend.agent_runtime.agents.generation import GenerationPortError
from backend.infrastructure.config.schemas.provider import (
    ModelContextLimits,
    ModelProfileId,
    ProviderInvocationLimits,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    OUTPUT_CONTRACT_ID,
    SECTION_IDS,
)
from tests.support.conversation_fakes import CONTEXT
from tests.unit.test_openai_generation_adapter import _model, _provider, _request


def model():
    return replace(_model(), model_profile_id=ModelProfileId("openai.gpt-5.6-terra.generation"),
        context_limits=ModelContextLimits(1_050_000, 32768, 4096),
        invocation_limits=ProviderInvocationLimits(1, 90000, max_output_tokens=4096))


def request():
    return replace(_request(), output_contract={"id":OUTPUT_CONTRACT_ID}, expected_sections=SECTION_IDS,
        pedagogical_context=CONTEXT, evidence_refs=("r2.synth.bilan", "r2.synth.bfr", "r2.synth.cas"))


def payload():
    return {"outcome":"OUTPUT", "sections":[{"code":code, "text":"Question synthétique substantielle, non fournie par un modèle."} for code in SECTION_IDS],
            "warnings":[], "uncertainties":[], "evidence_ids_used":["r2.synth.bilan"]}


def mapped(value):
    return _map_response(request=request(), response=OpenAIResponsesResponse(
        status=OpenAIResponseStatus.COMPLETED, output_text=json.dumps(value)),
        provider_profile=_provider(), model_profile=model())


def test_r2_opt_in_wire_schema_low_limits_and_declared_used_subset():
    technical = build_openai_request(request=request(), model_profile=model())
    assert technical.reasoning_effort is OpenAIReasoningEffort.LOW
    assert technical.max_output_tokens == 4096 and technical.model == "gpt-5.6-terra"
    assert set(technical.output_schema["properties"]) == {"outcome", "sections", "warnings", "uncertainties", "evidence_ids_used"}
    assert len(technical.input_json.encode()) <= 12288
    assert mapped(payload()).evidence_refs_used == ("r2.synth.bilan",)
    assert json.loads(technical.input_json)["pedagogical_context"]["total_points"] == "20"


@pytest.mark.parametrize("used", [["r2.synth.bilan", "r2.synth.bilan"], ["unknown"], [None], "all"])
def test_used_ids_are_distinct_allowlisted_not_inferred(used):
    value = payload()
    value["evidence_ids_used"] = used
    with pytest.raises(GenerationPortError):
        mapped(value)


def test_legacy_mapping_unchanged_and_empty_used_not_fabricated():
    legacy = build_openai_request(request=_request(), model_profile=_model())
    assert legacy.reasoning_effort is None
    assert set(legacy.output_schema["properties"]) == {"outcome", "sections", "warnings", "uncertainties"}
    value = payload()
    value["evidence_ids_used"] = []
    assert mapped(value).evidence_refs_used == ()


@pytest.mark.parametrize("field,value", [("model_profile_id",ModelProfileId("other")),
    ("invocation_limits",ProviderInvocationLimits(2,90000,max_output_tokens=4096)),
    ("invocation_limits",ProviderInvocationLimits(1,45000,max_output_tokens=4096)),
    ("invocation_limits",ProviderInvocationLimits(1,90000,max_output_tokens=2048))])
def test_profile_drift_fails_before_any_resolver(field, value):
    with pytest.raises(GenerationPortError):
        build_openai_request(request=request(), model_profile=replace(model(), **{field:value}))


def test_substantive_sections_size_and_duplicate_json_keys():
    from backend.adapters.outbound.generation.openai.adapter import _parse_payload
    value = payload()
    value["sections"][0]["text"] = "exercice à compléter"
    with pytest.raises(GenerationPortError):
        mapped(value)
    with pytest.raises(GenerationPortError):
        _parse_payload('{"outcome":"OUTPUT","outcome":"OUTPUT"}', conversation=True)
    with pytest.raises(GenerationPortError):
        build_openai_request(request=replace(request(), objective="x" * 13000), model_profile=model())


def test_existing_factory_binding_is_inert_and_uses_closed_proposed_profile():
    from decimal import Decimal

    from backend.infrastructure.composition.factories.conversation import (
        build_conversation_generation_adapter,
        conversation_provider_configuration,
        proposed_conversation_cost,
    )
    from backend.infrastructure.config.secrets.provider import ProviderSecretValue
    calls = []
    class Resolver:
        def resolve(self, ref):
            assert ref.value == "openai.r2.generation"
            calls.append("synthetic-resolver")
            return ProviderSecretValue("SYNTHETIC_TEST_VALUE_NOT_A_CREDENTIAL")
    class Transport:
        def create(self, *, request):
            calls.append("synthetic-transport")
            assert request.reasoning_effort is OpenAIReasoningEffort.LOW
            return OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, json.dumps(payload()))
    class Factory:
        def build(self, *, secret, timeout_seconds):
            assert timeout_seconds == 90
            return Transport()
    adapter = build_conversation_generation_adapter(secret_resolver=Resolver(), transport_factory=Factory())
    assert calls == []
    config = conversation_provider_configuration()
    assert len(config.routes) == 1 and config.routes[0].fallback_model_profile_ids == ()
    assert config.model_profiles[0].invocation_limits.max_attempts == 1
    assert proposed_conversation_cost() == Decimal("0.131072")
    result = adapter.generate(request=request())
    assert result.evidence_refs_used == ("r2.synth.bilan",)
    assert calls == ["synthetic-resolver", "synthetic-transport"]


def test_cli_live_handoff_is_closed_before_any_path_or_runtime_access(monkeypatch, capsys):
    from backend.adapters.inbound.cli import local_browser
    def forbidden(*args, **kwargs):
        raise AssertionError("No composition or runtime access permitted")
    monkeypatch.setattr(local_browser, "build_local_read15", forbidden)
    assert local_browser.main(["--port", "9123", "--runtime", "UNOPENED_SYNTHETIC_PATH",
        "--data-root", "UNOPENED_SYNTHETIC_ROOT", "--runtime-sha256", "a" * 64,
        "--enable-conversation", "--live-authorization", "UNOPENED_SYNTHETIC_GRANT"]) == 1
    assert capsys.readouterr().out.strip() == "R2_LIVE_PREFLIGHT_NOT_READY"


def test_final_offline_projection_hashes_and_permissions_are_closed():
    import hashlib
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    scope = json.loads((root / "docs/development/phase_12_18_h2_r2_generation/LIVE_GENERATION_SCOPE.json").read_text("utf-8"))
    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert scope["projection_sha256"] == digest(scope["projection"]) == "576e7008056bd74038e1b74be94e3278e67b29fa5591f6699a34d964f15002a7"
    assert scope["profile_sha256"] == digest(scope["profile"])
    assert scope["pricing_sha256"] == digest(scope["pricing"])
    assert scope["output_schema_sha256"] == digest(scope["projection"]["text"]["format"]["schema"])
    assert scope["live_authorized"] is False and scope["transfer_authorized"] is False
    assert scope["financial_approval"] is None and scope["credential_source"] is None
    assert scope["input_token_bound_proved"] is False
    assert scope["provider_calls"] == 0
    assert len(scope["projection"]["input"].encode()) == scope["input_json_utf8_bytes"] == 2659
    assert scope["projection"]["store"] is False and scope["projection"]["tools"] == []
    projection = json.loads(scope["projection"]["input"])
    assert len(projection["resolved_inputs"]["evidence"]) == 3
    assert projection["pedagogical_context"] == CONTEXT


@pytest.mark.parametrize("field,value", [
    ("operation", "COUNT"), ("live_authorized", False), ("transfer_authorized", False),
    ("baseline_commit", "0" * 40), ("scope_sha256", "0" * 64), ("projection_sha256", "0" * 64),
    ("profile_sha256", "0" * 64), ("pricing_sha256", "0" * 64), ("output_schema_sha256", "0" * 64),
    ("max_calls", 2), ("max_calls", True), ("provider", "OTHER"), ("ceiling_usd", "0.150000"),
    ("ceiling_usd", "NaN"), ("ceiling_usd", "0.010000"), ("token_count_receipt", None),
    ("token_count_receipt_sha256", "0" * 64), ("credential_source", "AMBIENT"),
    ("expires_at", "2000-01-01T00:00:00+00:00"), ("expires_at", "2030-01-01T00:00:00"),
])
def test_corrective_grant_refused_before_credential_or_job(tmp_path, field, value):
    from types import SimpleNamespace

    from backend.infrastructure.composition.factories.conversation import build_r2_process_job
    from tests.support.conversation_fakes import corrective_grant, corrective_scope
    target = SimpleNamespace(expected_sha256="b" * 64)
    grant = corrective_grant(target)
    grant[field] = value
    def forbidden():
        raise AssertionError("credential input must not run")
    with pytest.raises((ValueError, TypeError)):
        build_r2_process_job(grant=grant, scope=corrective_scope(), baseline="f" * 40,
            target=target, receipt_root=tmp_path / "receipts", private_temp=tmp_path,
            credential_input=forbidden)
    assert not (tmp_path / "receipts").exists()


@pytest.mark.parametrize("field,value", [("input_tokens", 32769), ("input_tokens", True),
    ("input_tokens", -1), ("input_tokens", None), ("count_request_sha256", "0" * 64),
    ("generation_request_sha256", "0" * 64), ("kind", "BYTE_ESTIMATE"), ("count_cost_status", "UNKNOWN")])
def test_count_receipt_is_complete_hash_bound_and_not_an_estimate(field, value):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from backend.infrastructure.composition.factories.conversation import (
        r2_digest,
        validate_r2_grant,
    )
    from tests.support.conversation_fakes import corrective_grant, corrective_scope
    grant = corrective_grant(SimpleNamespace(expected_sha256="b" * 64))
    grant["token_count_receipt"][field] = value
    grant["token_count_receipt_sha256"] = r2_digest(grant["token_count_receipt"])
    with pytest.raises(ValueError):
        validate_r2_grant(grant, scope=corrective_scope(), baseline="f" * 40, now=datetime.now(UTC))


def test_count_handoff_has_only_supported_fields_and_binds_the_entire_create_request():
    from backend.infrastructure.composition.factories.conversation import (
        r2_count_handoff,
        r2_digest,
    )
    from tests.support.conversation_fakes import corrective_scope
    projection = corrective_scope()["projection"]
    handoff = r2_count_handoff(projection)
    assert set(handoff["parameters"]) == {"model", "instructions", "input", "text", "reasoning", "tools", "tool_choice"}
    assert handoff["generation_request_sha256"] == r2_digest(projection)
    assert handoff["status"] == "PENDING_AUTHORIZED_COUNT" and handoff["cost_status"] == "NOT_ESTABLISHED"
    changed = {**projection, "max_output_tokens": 4095}
    assert r2_count_handoff(changed)["generation_request_sha256"] != handoff["generation_request_sha256"]
    assert r2_count_handoff(changed)["count_request_sha256"] == handoff["count_request_sha256"]
    with pytest.raises(ValueError):
        r2_count_handoff({**projection, "extra_body": {}})


def test_real_transport_parameters_capture_tier_destination_no_retry_and_usage_before_parsing(monkeypatch):
    from types import SimpleNamespace

    from backend.adapters.outbound.openai import transport
    from backend.infrastructure.composition.factories.conversation import r2_request_parameters
    from backend.infrastructure.config.secrets.provider import ProviderSecretValue
    captured = {}
    def create(**params):
        captured["parameters"] = params
        return SimpleNamespace(status="completed", output=[], output_text="{", service_tier="default",
            incomplete_details=None, usage=SimpleNamespace(input_tokens=3000, output_tokens=1000,
                total_tokens=4000, input_tokens_details=SimpleNamespace(cached_tokens=100, cache_write_tokens=200),
                output_tokens_details=SimpleNamespace(reasoning_tokens=100)))
    def client(**kwargs):
        captured["client"] = kwargs
        return SimpleNamespace(responses=SimpleNamespace(create=create), close=lambda: captured.update(closed=True))
    monkeypatch.setattr(transport, "OpenAI", client)
    monkeypatch.setattr(transport, "DefaultHttpxClient", lambda **kwargs: captured.setdefault("http", kwargs))
    technical = build_openai_request(request=request(), model_profile=model())
    result = transport.OpenAISDKResponsesTransport(secret=ProviderSecretValue("SYNTHETIC_FAKE"),
        timeout_seconds=90.0, r2_destination=True).create(request=technical)
    assert captured["parameters"] == r2_request_parameters(technical)
    assert captured["client"]["base_url"] == "https://api.openai.com/v1"
    assert captured["client"]["organization"] == captured["client"]["project"] == ""
    assert captured["client"]["max_retries"] == 0 and captured["closed"]
    assert captured["http"] == {"trust_env": False, "follow_redirects": False}
    assert result.usage.cache_write_input_tokens == 200 and result.usage.reasoning_tokens == 100
    assert result.output_text == "{" and result.service_tier == "default"


@pytest.mark.parametrize("name", ["OPENAI_BASE_URL", "OPENAI_CUSTOM_HEADERS", "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID", "OPENAI_API_KEY", "HTTP_PROXY", "https_proxy", "SSL_CERT_FILE"])
def test_ambient_destination_and_credentials_fail_closed_before_sdk(monkeypatch, name):
    from backend.adapters.outbound.openai import transport
    from backend.adapters.outbound.openai.contracts import OpenAITransportError
    from backend.infrastructure.config.secrets.provider import ProviderSecretValue
    monkeypatch.setenv(name, "SYNTHETIC_NOT_READ")
    def forbidden(**kwargs):
        raise AssertionError("SDK constructor must not run")
    monkeypatch.setattr(transport, "OpenAI", forbidden)
    with pytest.raises(OpenAITransportError):
        transport.OpenAISDKResponsesTransport(secret=ProviderSecretValue("SYNTHETIC_FAKE"),
            timeout_seconds=90.0, r2_destination=True)


def test_partial_usage_is_unknown_or_bound_never_zero_and_reasoning_not_added_twice():
    from backend.adapters.outbound.system.conversation_job import usage_cost_evidence
    from backend.modules.work_orchestration.ports.outbound.generation_job import GenerationUsage
    assert usage_cost_evidence(GenerationUsage())["calculated_usd"] is None
    value = GenerationUsage(provider_attempted=True, response_received=True,
        input_tokens=3000, output_tokens=1000, reasoning_tokens=100, service_tier="default")
    assert usage_cost_evidence(value)["calculated_usd"] == "0.0195"
    assert usage_cost_evidence(value)["cost_kind"] == "CONSERVATIVE_BOUND"
    assert usage_cost_evidence(replace(value, service_tier="UNKNOWN"))["calculated_usd"] is None
    assert usage_cost_evidence(replace(value, reasoning_tokens=900)) == {
        **usage_cost_evidence(value), "usage": {**usage_cost_evidence(value)["usage"], "reasoning_tokens": 900}}


def test_hash_change_is_rejected_before_resolver_and_response_capture_survives_bad_json():
    from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
    from backend.adapters.outbound.openai.contracts import OpenAIResponseUsage
    from backend.infrastructure.composition.factories.conversation import (
        R2ExecutionEvidence,
        r2_digest,
        r2_request_parameters,
    )
    calls, evidence_values = [], []
    technical = build_openai_request(request=request(), model_profile=model())
    evidence = R2ExecutionEvidence(request_sha256=r2_digest(r2_request_parameters(technical)), publish=evidence_values.append)
    class Resolver:
        def resolve(self, ref):
            from backend.infrastructure.config.secrets.provider import ProviderSecretValue
            calls.append("FAKE_RESOLVE")
            return ProviderSecretValue("SYNTHETIC_FAKE")
    class Factory:
        def build(self, **kwargs):
            return self
        def create(self, **kwargs):
            calls.append("FAKE_CREATE")
            return OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, "{",
                usage=OpenAIResponseUsage(input_tokens=25, output_tokens=10), service_tier="default")
    adapter = OpenAIGenerationAdapter(provider_profile=_provider(), model_profile=model(),
        secret_resolver=Resolver(), transport_factory=Factory())
    adapter.bind_conversation_execution(before_request=evidence.before_request, on_dispatch=evidence.on_dispatch,
        on_response=evidence.on_response, on_parsing=evidence.on_parsing)
    with pytest.raises(ValueError):
        adapter.generate(request=replace(request(), objective="Not the approved request"))
    assert calls == [] and evidence_values == []
    with pytest.raises(GenerationPortError):
        adapter.generate(request=request())
    assert calls == ["FAKE_RESOLVE", "FAKE_CREATE"]
    assert evidence_values[-2].response_received and evidence_values[-2].parsing == "NOT_RUN"
    assert evidence_values[-1].input_tokens == 25 and evidence_values[-1].parsing == "FAILED"
    with pytest.raises(ValueError):
        adapter.generate(request=request())
    assert len(calls) == 2


def test_used_authorization_and_receipt_relocation_refuse_before_masked_input(tmp_path):
    from backend.infrastructure.composition.factories.conversation import build_r2_process_job
    from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
    from tests.support.conversation_fakes import corrective_grant, corrective_scope
    from tests.support.conversation_synthetic import synthetic_target
    from tests.unit.test_conversation_generation import draft_request
    target = synthetic_target(tmp_path / "synthetic")
    root = tmp_path / "receipts"
    grant = corrective_grant(target, root)
    def forbidden():
        raise AssertionError("No credential input expected")
    options = dict(grant=grant, scope=corrective_scope(), baseline="f" * 40, target=target,
        private_temp=tmp_path, credential_input=forbidden)
    with pytest.raises(ValueError, match="NAMESPACE"):
        build_r2_process_job(**options, receipt_root=tmp_path / "other")
    job = build_r2_process_job(**options, receipt_root=root)
    job.receipt.record("RESERVED", draft_request())
    with pytest.raises(ConversationRejected):
        build_r2_process_job(**options, receipt_root=root)
    job.close()


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{}TRAILING', '[]'])
def test_grant_json_is_closed_and_has_no_duplicate_or_nonfinite_fallback(tmp_path, raw):
    from backend.infrastructure.composition.factories.conversation import load_r2_grant
    path = tmp_path / "synthetic-grant.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        load_r2_grant(path)


@pytest.mark.parametrize("drift", ("version", "import_path"))
def test_wrong_sdk_version_rejected_without_credential_or_runtime(monkeypatch, tmp_path, drift):
    from types import SimpleNamespace

    from backend.infrastructure.composition.factories import conversation
    from tests.support.conversation_fakes import corrective_grant, corrective_scope
    target = SimpleNamespace(expected_sha256="b" * 64)
    grant = corrective_grant(target)
    if drift == "version":
        monkeypatch.setattr(conversation, "version", lambda name: "3.5.0")
    else:
        monkeypatch.setattr(conversation, "openai_sdk_import_path", lambda: tmp_path / "synthetic-sdk.py")
    with pytest.raises(ValueError, match="LOCKED_ENVIRONMENT|LOCKED_SDK_PATH"):
        conversation.build_r2_process_job(grant=grant, scope=corrective_scope(), baseline="f" * 40,
            target=target, receipt_root=tmp_path / "receipts", private_temp=tmp_path,
            credential_input=lambda: pytest.fail("No real/fake key needed"))


@pytest.mark.parametrize("tty", (False, True))
def test_cli_never_falls_back_to_unmasked_input(monkeypatch, capsys, tty):
    import warnings
    from types import SimpleNamespace

    from backend.adapters.inbound.cli import local_browser
    monkeypatch.setattr(local_browser, "load_r2_grant", lambda path: {})
    monkeypatch.setattr(local_browser, "r2_source_material", lambda: ("f" * 40, {}))
    monkeypatch.setattr(local_browser, "build_r2_process_job", lambda **kwargs: object())
    monkeypatch.setattr(local_browser.sys, "stdin", SimpleNamespace(isatty=lambda: tty))
    def no_fallback(prompt):
        warnings.warn("Synthetic unavailable masked console", local_browser.getpass.GetPassWarning, stacklevel=2)
        pytest.fail("The unmasked fallback must not execute")
    monkeypatch.setattr(local_browser.getpass, "getpass", no_fallback)
    monkeypatch.setattr(local_browser, "build_local_read15", lambda *args, **kwargs: pytest.fail("No startup"))
    assert local_browser.main(["--port", "9123", "--runtime", "UNOPENED_SYNTHETIC_PATH",
        "--data-root", "UNOPENED_SYNTHETIC_ROOT", "--runtime-sha256", "a" * 64,
        "--enable-conversation", "--live-authorization", "UNOPENED_SYNTHETIC_GRANT"]) == 1
    assert capsys.readouterr().out.strip() == "R2_LIVE_PREFLIGHT_NOT_READY"
