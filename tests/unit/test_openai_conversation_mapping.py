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
    assert scope["projection_sha256"] == digest(scope["projection"]) == "76caedfd0c8735bf8e6bff13549e0fff0c50ea908b94c0f8fc17c11bfdcea293"
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
