"""One-shot authority with exclusively invented resolvers/transports/pricing."""

import json
from dataclasses import asdict, replace
from datetime import timedelta
from typing import Any

import pytest

from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.infrastructure.composition.factories.r3_harden_execution import (
    HardenExecutionEvidence,
    build_harden_adapter,
)
from backend.infrastructure.composition.factories.r3_harden_profile import load_harden_profile
from backend.infrastructure.composition.factories.r3_harden_serialization import (
    r3_harden_count_parameters,
    r3_harden_request_parameters,
)
from backend.infrastructure.config.schemas.provider import ProviderCostLimit
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from tests.support.r3_d3_fixtures import (
    BASELINE,
    NOW,
    SyntheticResolver,
    SyntheticTransport,
    synthetic_harden_request,
)


def fixture() -> dict[str, Any]:
    provider, original = load_harden_profile()
    model = replace(
        original,
        invocation_limits=replace(
            original.invocation_limits,
            max_cost=ProviderCostLimit(amount_microunits=100000, currency_code="USD"),
        ),
    )
    request = synthetic_harden_request()
    wire = build_openai_request(request=request, model_profile=model)
    grant = {
        "purpose": "HARDEN_DOSSIER_3_ONCE",
        "baseline_commit": BASELINE,
        "runner_sha256": "1" * 64,
        "pricing_sha256": "2" * 64,
        "profile_sha256": fingerprint(asdict(model)),
        "request_sha256": fingerprint(r3_harden_request_parameters(wire, model_profile=model)),
        "count_sha256": fingerprint(r3_harden_count_parameters(wire, model_profile=model)),
        "projection_sha256": fingerprint(json.loads(wire.input_json)),
        "exact_input_tokens": 1000,
        "input_microusd_per_million": 1000000,
        "output_microusd_per_million": 1000000,
        "ceiling_microusd": 100000,
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "max_calls": 1,
        "retry": False,
        "fallback": None,
        "transfer_authorized": True,
        "execution_authorized": True,
        "receipt_namespace": "3" * 64,
    }
    events: list[str] = []
    evidence = HardenExecutionEvidence()
    used: set[str] = set()

    def reserve(namespace: str) -> None:
        if namespace in used:
            raise ValueError("SYNTHETIC_ALREADY_USED")
        used.add(namespace)
        events.append("RESERVE")

    def capture(value: HardenExecutionEvidence) -> None:
        events.append(value.state + ":" + value.parsing)

    args = {
        "provider_profile": provider,
        "model_profile": model,
        "secret_resolver": SyntheticResolver(events),
        "transport_factory": SyntheticTransport(events),
        "grant": grant,
        "expected_grant_sha256": fingerprint(grant),
        "baseline_commit": BASELINE,
        "runner_sha256": "1" * 64,
        "pricing_sha256": "2" * 64,
        "clock": lambda: NOW,
        "evidence": evidence,
        "reserve_once": reserve,
        "capture": capture,
    }
    return {
        "args": args,
        "grant": grant,
        "events": events,
        "evidence": evidence,
        "request": request,
    }


def test_one_shot_before_secret_capture_before_parse_and_no_reuse() -> None:
    data = fixture()
    adapter = build_harden_adapter(**data["args"])
    result = adapter.generate(request=data["request"])
    assert result.status.value == "SUCCEEDED"
    events = data["events"]
    assert (
        events.index("RESERVE")
        < events.index("SYNTHETIC_RESOLVE")
        < events.index("DISPATCH_POSSIBLE:NOT_RUN")
        < events.index("SYNTHETIC_CREATE")
    )
    assert events.index("RESPONSE_RECEIVED:NOT_RUN") < events.index("RESPONSE_RECEIVED:SUCCEEDED")
    assert data["evidence"].response.usage.input_tokens == 1000
    with pytest.raises(ValueError):
        adapter.generate(request=data["request"])
    assert events.count("SYNTHETIC_CREATE") == 1
    # Even a fresh adapter with a fresh volatile capture cannot bypass persistent reservation.
    data["args"]["evidence"] = HardenExecutionEvidence()
    with pytest.raises(ValueError, match="SYNTHETIC_ALREADY_USED"):
        build_harden_adapter(**data["args"]).generate(request=data["request"])
    assert events.count("SYNTHETIC_RESOLVE") == 1


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "hash",
        "expired",
        "profile",
        "baseline",
        "transfer",
        "retry",
        "fallback",
        "calls",
        "bool",
        "budget",
        "null_budget",
        "destination",
    ],
)
def test_invalid_grant_fails_without_secret_or_effect(kind: str) -> None:
    data = fixture()
    grant, args = data["grant"], data["args"]
    if kind == "missing":
        del grant["purpose"]
    elif kind == "hash":
        args["expected_grant_sha256"] = "0" * 64
    elif kind == "expired":
        grant["expires_at"] = NOW.isoformat()
    elif kind == "profile":
        grant["profile_sha256"] = "0" * 64
    elif kind == "baseline":
        grant["baseline_commit"] = "0" * 40
    elif kind == "transfer":
        grant["transfer_authorized"] = False
    elif kind == "retry":
        grant["retry"] = True
    elif kind == "fallback":
        grant["fallback"] = "other"
    elif kind == "calls":
        grant["max_calls"] = 2
    elif kind == "bool":
        grant["exact_input_tokens"] = True
    elif kind == "budget":
        grant["output_microusd_per_million"] = 999999999
    elif kind == "null_budget":
        args["model_profile"] = load_harden_profile()[1]
    else:
        args["transport_factory"].r2_destination = False
    if kind != "hash":
        args["expected_grant_sha256"] = fingerprint(grant)
    with pytest.raises(ValueError):
        build_harden_adapter(**args)
    assert data["events"] == []


@pytest.mark.parametrize("key", ["request_sha256", "count_sha256", "projection_sha256"])
def test_exact_body_checks_precede_resolver(key: str) -> None:
    data = fixture()
    data["grant"][key] = "0" * 64
    data["args"]["expected_grant_sha256"] = fingerprint(data["grant"])
    with pytest.raises(ValueError):
        build_harden_adapter(**data["args"]).generate(request=data["request"])
    assert data["events"] == []


def test_bad_output_keeps_raw_usage_before_parse_failure_and_no_retry() -> None:
    data = fixture()
    data["args"]["transport_factory"] = SyntheticTransport(data["events"], output="not json")
    adapter = build_harden_adapter(**data["args"])
    with pytest.raises(ValueError):
        adapter.generate(request=data["request"])
    assert data["evidence"].response.output_text == "not json"
    assert data["evidence"].response.usage.output_tokens == 500
    assert data["events"][-1] == "RESPONSE_RECEIVED:FAILED"
    with pytest.raises(ValueError):
        adapter.generate(request=data["request"])
    assert data["events"].count("SYNTHETIC_CREATE") == 1


def test_sdk_destination_isolation_uses_replaced_clients_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.adapters.outbound.openai import transport
    from backend.infrastructure.config.secrets.provider import ProviderSecretValue

    seen: dict[str, Any] = {}

    def http(**kwargs: Any) -> object:
        seen["http"] = kwargs
        return object()

    def client(**kwargs: Any) -> object:
        seen["client"] = kwargs
        return object()

    monkeypatch.setattr(transport, "DefaultHttpxClient", http)
    monkeypatch.setattr(transport, "OpenAI", client)
    transport.OpenAISDKResponsesTransport(
        secret=ProviderSecretValue("SYNTHETIC_NOT_A_CREDENTIAL"),
        timeout_seconds=90.0,
        r2_destination=True,
    )
    assert seen["http"] == {"trust_env": False, "follow_redirects": False}
    assert seen["client"]["base_url"] == "https://api.openai.com/v1"
    assert seen["client"]["max_retries"] == 0
    for key in ("organization", "project", "admin_api_key", "webhook_secret"):
        assert seen["client"][key] == ""
