"""The existing provider adapter, synthetic secret/transport, zero network."""

import json

import pytest

from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_content import bind_p0_content
from backend.adapters.outbound.generation.p0_codesign_agents import CoDesignGenerator
from backend.adapters.outbound.openai.contracts import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity
from tests.test_codesign_global_324 import simple


def model(attempts=1):
    return ModelProfileConfig(
        ModelProfileId("openai.synthetic.codesign"),
        ProviderProfileId("openai.synthetic"),
        ModelCode("gpt-5.6-terra"),
        ModelContextLimits(128000, 100000, 4096),
        ProviderInvocationLimits(
            max_attempts=attempts, call_timeout_milliseconds=120000, max_output_tokens=4096
        ),
        (ProviderWorkloadKind.GENERATION, ProviderWorkloadKind.CORRECTION),
        structured_output_required=True,
    )


class Transport:
    def __init__(self, content):
        self.content, self.builds, self.calls = content, 0, []

    def build(self, *, secret, timeout_seconds):
        assert secret.reveal_for_transport() == "SYNTHETIC_SECRET_324_NOT_REAL"
        assert timeout_seconds == 120
        self.builds += 1
        return self

    def create(self, *, request):
        self.calls.append(request)
        return OpenAIResponsesResponse(
            OpenAIResponseStatus.COMPLETED, json.dumps(self.content, ensure_ascii=False)
        )


def adapter(transport, attempts=1):
    return OpenAIGenerationAdapter(
        provider_profile=ProviderProfileConfig(
            ProviderProfileId("openai.synthetic"),
            ProviderCode("openai"),
            ProviderCredentialRef("OPENAI_API_KEY"),
        ),
        model_profile=model(attempts),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"OPENAI_API_KEY": "SYNTHETIC_SECRET_324_NOT_REAL"}
        ),
        transport_factory=transport,
    )


@pytest.mark.parametrize("direction", ("V2_TO_AI", "AI_TO_V2"))
def test_existing_openai_adapter_accepts_exact_p0_schema_and_preserves_bindings(direction):
    dispatch, content = simple()
    parent = bind_p0_content(dispatch, content)
    transport = Transport(content)
    child, proof = CoDesignGenerator(adapter(transport)).propose(
        parent=parent,
        evidence=dispatch["evidence"],
        objective="Clarifier",
        direction=direction,
        identity=OperationIdentity("run:" + "a" * 32, "step:" + "c" * 32, None, "d" * 32),
    )
    assert transport.builds == len(transport.calls) == 1
    assert transport.calls[0].schema_name == "p0_codesign_content"
    assert transport.calls[0].output_schema["additionalProperties"] is False
    assert transport.calls[0].max_output_tokens == 4096
    assert (
        child.data["context"] == parent.data["context"]
        and child.data["references"] == parent.data["references"]
    )
    assert child.data["lineage"]["source_step_id"] == "step:" + "c" * 32
    assert proof["correction"] is None
    assert proof["controls"]["bundle_sha256"] == child.sha256


def test_retrying_model_profile_is_refused_before_secret_and_transport():
    dispatch, content = simple()
    parent = bind_p0_content(dispatch, content)
    transport = Transport(content)
    with pytest.raises(ValueError, match="P0_CODESIGN_PROVIDER_PROFILE_REQUIRED"):
        CoDesignGenerator(adapter(transport, 2)).propose(
            parent=parent,
            evidence=dispatch["evidence"],
            objective="Clarifier",
            direction="V2_TO_AI",
            identity=OperationIdentity("run:" + "a" * 32, "step:" + "c" * 32, None, "d" * 32),
        )
    assert transport.builds == len(transport.calls) == 0


def test_existing_sdk_correction_preserves_target_and_c11_c12_without_second_attempt():
    from copy import deepcopy

    from backend.adapters.outbound.generation.p0_codesign_agents import correction_request
    from tests.test_codesign_global_324 import composition
    from tests.test_codesign_safety_324 import command

    dispatch, content = simple()
    service, _, _ = composition(dispatch, content, correction=True)
    result = service.execute("codesign", command(service.records[dispatch["version_ref"]]))
    parent = service.records[result["trace"]["productions"][0]["version_ref"]]
    report = result["trace"]["reports"][0]
    identity = OperationIdentity("run:" + "a" * 32, "step:" + "c" * 32, None, "d" * 32)
    request = correction_request(parent, report, identity)
    changed = deepcopy(content)
    changed["title"] = "Perception : une distinction explicitée"
    transport = Transport(
        {
            "content": changed,
            "addressed_findings": ["finding-1"],
            "unresolved_findings": [],
            "change_summary": "Le titre est précisé.",
        }
    )
    child, proof = CoDesignGenerator(adapter(transport)).propose(
        parent=parent,
        evidence=dispatch["evidence"],
        objective="Clarifier",
        direction="V2_TO_AI",
        identity=identity,
        correction=request,
    )
    assert transport.builds == len(transport.calls) == 1
    assert transport.calls[0].schema_name == "p0_codesign_content"
    assert set(transport.calls[0].output_schema["required"]) == {
        "content",
        "addressed_findings",
        "unresolved_findings",
        "change_summary",
    }
    assert child.data["lineage"]["parent_version_ref"] == parent.version_ref
    assert proof["correction"]["addressed_findings"] == ["finding-1"]
    assert proof["correction"]["resolution"] == "FRESH_REVIEW_REQUIRED"
