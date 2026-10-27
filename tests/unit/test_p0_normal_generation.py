"""Declared synthetic grant/tokenizer/tariff/transport; never provider intelligence."""
import copy
import threading
from datetime import UTC, datetime, timedelta
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    CONTENT_FIELDS,
    build_p0_content_request,
)
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import HASH_FIELDS, canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretValue,
)
from backend.infrastructure.filesystem import LocalFileSecurityError
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.integration.test_p0_creation_http import context
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_creation_contract import service
from tests.unit.test_p0_normal_policy import fixture as policy_fixture

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


class SyntheticResolver:
    def __init__(self):
        self.calls = 0
        self.before = lambda: None

    def resolve(self, credential_ref):
        self.calls += 1
        self.before()
        return ProviderSecretValue("SYNTHETIC_NON_CREDENTIAL_ONLY")


class SyntheticTransport:
    def __init__(self, response):
        self.response = response
        self.build_calls = 0
        self.calls = 0
        self.failure = None
        self.after_capture = None

    def build(self, *, secret, timeout_seconds):
        assert str(secret) == "[REDACTED]" and timeout_seconds == 120.0
        self.build_calls += 1
        return self

    def create(self, *, request):
        self.calls += 1
        if self.failure:
            raise self.failure
        return self.response


def synthetic_configuration(tmp_path, kind="ASSESSMENT", mode=None):
    app = service(None)
    prepared = app.execute("prepare", {"command_id": token_hex(16),
        "context": context("BTS_CG_YEAR_2", kind, mode), "reference": {}})
    dispatch = as_plain(app.prepared[prepared["preparation_ref"]])
    proposed = P0GenerationDouble().generate(request=dispatch)
    content = {key: as_plain(proposed[key]) for key in CONTENT_FIELDS}
    response = OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, canonical(content).decode(),
        OpenAIResponseUsage(1000, 0, 100, 1100, reasoning_tokens=0), service_tier="default")
    grant, _, _, _, tariff, tokenizer = policy_fixture()
    raw = NormalP0GenerationAdapter.body(build_p0_content_request(dispatch))
    root = tmp_path / "synthetic-private-receipts"
    root.mkdir()
    receipt = P0NormalReceipt(root, token_hex(32))
    grant.update(request_sha256=sha(raw), request_bytes=len(raw), preparation_sha256=sha(canonical(dispatch)),
        context_sha256=dispatch["context_sha256"], reference_set_sha256=sha(canonical(dispatch["references"])),
        receipt_root_sha256=receipt.root_sha256, namespace_sha256=receipt.namespace,
        output_schema_sha256=sha(canonical(build_p0_content_request(dispatch).output_schema)))
    tokenizer["request_sha256"] = sha(raw)
    identities = {key: grant[key] for key in HASH_FIELDS | {"baseline_commit", "request_bytes"}}
    resolver, transport = SyntheticResolver(), SyntheticTransport(response)
    configuration = {"grant": grant, "identity_source": lambda request, body: identities,
        "tariff": tariff, "tokenizer": lambda body: tokenizer, "receipt_root": root,
        "resolver": resolver, "credential_ref": ProviderCredentialRef("synthetic-logical-ref"),
        "transport": transport, "clock": lambda: NOW}
    return configuration, app, prepared, dispatch, identities, tokenizer, resolver, transport


@pytest.mark.parametrize("kind,mode", [("COURSE", None), ("EXERCISE", None),
    ("QUESTION_SET", "OPEN_QUESTIONS"), ("QUESTION_SET", "QCM"), ("QUESTION_SET", "QUIZ"), ("ASSESSMENT", None)])
def test_six_families_pass_real_canonical_agent_guard_and_binding_once(tmp_path, kind, mode):
    config, app, prepared, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path, kind, mode)
    adapter = NormalP0GenerationAdapter(**config)
    assert resolver.calls == transport.build_calls == transport.calls == 0
    app.generation = adapter
    result = app.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"]})
    assert result["state"] == "CANDIDATE"
    assert resolver.calls == transport.build_calls == transport.calls == 1
    assert result["view"]["production_ref"] == dispatch["production_ref"]
    assert result["view"]["version_ref"] == dispatch["version_ref"]
    assert adapter.receipt.read("CONSUMED")["observed_cost_status"] == "NOT_ESTABLISHED"
    with pytest.raises(ValueError, match="ALREADY_USED"):
        adapter.authorize(request=dispatch)
    assert transport.calls == 1


def test_absent_normal_composition_has_no_hidden_provider_or_content():
    app = service(None)
    prepared = app.execute("prepare", {"command_id": token_hex(16),
        "context": context("BTS_CG_YEAR_2", "ASSESSMENT", None), "reference": {}})
    result = app.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"]})
    assert result["state"] == "AUTHORIZATION_REQUIRED" and result["provider_attempts"] == 0 and not app.records


@pytest.mark.parametrize("key", sorted(HASH_FIELDS | {"baseline_commit", "request_bytes"}))
def test_all_factory_identity_mutations_refuse_before_resolver_or_transport(tmp_path, key):
    config, _, _, dispatch, identities, _, resolver, transport = synthetic_configuration(tmp_path)
    identities[key] = 1 if key == "request_bytes" else "9" * len(identities[key])
    adapter = NormalP0GenerationAdapter(**config)
    with pytest.raises(ValueError):
        adapter.authorize(request=dispatch)
    assert resolver.calls == transport.build_calls == transport.calls == 0
    assert not adapter.receipt.exists("RESERVED")


@pytest.mark.parametrize("mutation", ["expired", "COUNT", "REVIEW", "MODIFY", "tariff_period", "tokenizer", "cost", "tokens"])
def test_preflight_and_permissions_fail_without_provider_effect(tmp_path, mutation):
    config, _, _, dispatch, _, tokens, resolver, transport = synthetic_configuration(tmp_path)
    if mutation == "expired":
        config["clock"] = lambda: NOW + timedelta(hours=2)
    elif mutation in {"COUNT", "REVIEW", "MODIFY"}:
        config["grant"]["operation"] = mutation
    elif mutation == "tariff_period":
        config["tariff"]["retrieved_at_utc"] = "2026-10-11T11:00:01+00:00"
        config["grant"]["tariff_sha256"] = sha(canonical(config["tariff"]))
    elif mutation == "tokenizer":
        tokens["recognition"] = "ASSUMED"
    elif mutation == "cost":
        tokens["serialized_json_tokens"] = 26340
    elif mutation == "tokens":
        tokens["serialized_json_tokens"] = 30001
    adapter = NormalP0GenerationAdapter(**config)
    with pytest.raises(ValueError):
        adapter.authorize(request=dispatch)
    assert resolver.calls == transport.build_calls == transport.calls == 0


def test_late_expiry_after_reservation_keeps_zero_provider_and_consumed_namespace(tmp_path):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    now = [NOW]
    config["clock"] = lambda: now[0]
    adapter = NormalP0GenerationAdapter(**config)
    resolver.before = lambda: now.__setitem__(0, NOW + timedelta(hours=2))
    assert adapter.authorize(request=dispatch)
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.generate(request=dispatch)
    assert resolver.calls == 1 and transport.build_calls == transport.calls == 0
    assert adapter.receipt.read("UNKNOWN")["provider_attempts"] == 0
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.confirmed_dispatch()


def test_timeout_is_durable_unknown_and_never_retried(tmp_path):
    config, _, _, dispatch, _, _, _, transport = synthetic_configuration(tmp_path)
    transport.failure = TimeoutError("SYNTHETIC_PRIVATE_DIAGNOSTIC_MUST_NOT_LEAK")
    adapter = NormalP0GenerationAdapter(**config)
    adapter.authorize(request=dispatch)
    with pytest.raises(ValueError, match="^P0_NORMAL_OUTCOME_UNKNOWN$"):
        adapter.generate(request=dispatch)
    assert transport.calls == 1
    assert adapter.receipt.exists("UNKNOWN") and adapter.receipt.exists("RESERVED")
    with pytest.raises(ValueError):
        adapter.generate(request=dispatch)
    assert transport.calls == 1


@pytest.mark.parametrize("mutation", ["incomplete", "malformed", "duplicate", "usage"])
def test_response_capture_precedes_parsing_and_failed_outputs_stay_unpublished(tmp_path, mutation):
    config, app, prepared, _, _, _, _, transport = synthetic_configuration(tmp_path)
    output = transport.response.output_text
    status = OpenAIResponseStatus.COMPLETED
    usage = transport.response.usage
    if mutation == "incomplete":
        status = OpenAIResponseStatus.INCOMPLETE
    elif mutation == "malformed":
        output = "{broken"
    elif mutation == "duplicate":
        output = output[:-1] + ',"title":"duplicate"}'
    else:
        usage = OpenAIResponseUsage(1000, 2000, 100, 1100)
    transport.response = OpenAIResponsesResponse(status, output, usage, service_tier="default")
    adapter = NormalP0GenerationAdapter(**config)
    app.generation = adapter
    with pytest.raises(ValueError):
        app.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"]})
    assert transport.calls == 1 and not app.records
    assert adapter.receipt.exists("RESPONSE_CAPTURED") and adapter.receipt.exists("RESULT")
    assert adapter.receipt.exists("PARSING_REJECTED")
    with pytest.raises(ValueError):
        adapter.confirmed_dispatch()


def test_confirmed_capture_recovers_after_restart_and_expiry_without_new_effect(tmp_path):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    adapter.authorize(request=dispatch)
    output = adapter.generate(request=dispatch)
    before = {path.name: path.read_bytes() for path in config["receipt_root"].glob("*.json")}
    config["clock"] = lambda: NOW + timedelta(days=7)
    # The recovery path cannot even consult identity/tokenizer or credential.
    config["identity_source"] = lambda *args: (_ for _ in ()).throw(AssertionError("IDENTITIES_NOT_CALLED"))
    config["tokenizer"] = lambda *args: (_ for _ in ()).throw(AssertionError("TOKENIZER_NOT_CALLED"))
    recovered = NormalP0GenerationAdapter(**config)
    assert recovered.confirmed_dispatch() == dispatch
    assert recovered.recover_confirmed(request=dispatch) == output
    assert resolver.calls == transport.build_calls == transport.calls == 1
    assert {path.name: path.read_bytes() for path in config["receipt_root"].glob("*.json")} == before
    substituted = copy.deepcopy(dispatch)
    substituted["lineage"]["source_request_id"] = "request:" + "9" * 32
    with pytest.raises(ValueError, match="RECOVERY_BINDING"):
        recovered.recover_confirmed(request=substituted)


def test_capture_before_application_publication_can_be_recovered(tmp_path, monkeypatch):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    adapter.authorize(request=dispatch)
    def interrupted(*args, **kwargs):
        raise SystemExit("SYNTHETIC_PROCESS_TERMINATION_AFTER_CAPTURE")
    monkeypatch.setattr("backend.adapters.outbound.generation.openai.p0_normal.guard_and_bind", interrupted)
    with pytest.raises(SystemExit):
        adapter.generate(request=dispatch)
    assert adapter.receipt.exists("RESPONSE_CAPTURED") and not adapter.receipt.exists("PARSED")
    assert not adapter.receipt.exists("PARSING_REJECTED")
    monkeypatch.undo()
    recovered = NormalP0GenerationAdapter(**config)
    assert recovered.confirmed_dispatch() == dispatch
    assert recovered.recover_confirmed(request=dispatch)["production_ref"] == dispatch["production_ref"]
    assert transport.calls == resolver.calls == 1


def test_missing_captured_artifact_refuses_without_provider_call(tmp_path):
    config, _, _, dispatch, _, _, _, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    adapter.authorize(request=dispatch)
    adapter.generate(request=dispatch)
    artifact = adapter.receipt._path("RESULT")
    artifact.rename(artifact.with_suffix(".preserved"))
    with pytest.raises(LocalFileSecurityError):
        NormalP0GenerationAdapter(**config).confirmed_dispatch()
    assert transport.calls == 1


def test_namespace_concurrency_allows_only_one_synthetic_effect(tmp_path):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    first, second = NormalP0GenerationAdapter(**config), NormalP0GenerationAdapter(**config)
    first.authorize(request=dispatch)
    second.authorize(request=dispatch)
    barrier = threading.Barrier(2)
    results = []
    def run(adapter):
        barrier.wait()
        try:
            adapter.generate(request=dispatch)
            results.append("OK")
        except Exception:
            results.append("REFUSED")
    workers = [threading.Thread(target=run, args=(adapter,)) for adapter in (first, second)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(10)
    assert sorted(results) == ["OK", "REFUSED"]
    assert resolver.calls == transport.build_calls == transport.calls == 1


def test_root_substitution_is_rejected_before_any_resolver_or_provider(tmp_path):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    root = config["receipt_root"]
    root.rename(root.with_name("preserved-original-root"))
    root.mkdir()
    with pytest.raises(ValueError, match="ROOT_CHANGED"):
        adapter.authorize(request=dispatch)
    assert resolver.calls == transport.build_calls == transport.calls == 0


def test_pinned_parent_cannot_be_renamed_during_effect_publication(tmp_path):
    from backend.adapters.outbound.generation.openai.p0_normal_receipt import pinned_receipt_root
    config, *_ = synthetic_configuration(tmp_path)
    root = config["receipt_root"]
    with pinned_receipt_root(root):
        with pytest.raises(PermissionError):
            root.rename(root.with_name("not-permitted-during-pin"))
    assert root.is_dir()


def test_failed_receipt_publication_stops_before_secret_or_transport(tmp_path, monkeypatch):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    adapter.authorize(request=dispatch)
    def refused(*args, **kwargs):
        raise OSError("SYNTHETIC_PUBLICATION_FAILED")
    monkeypatch.setattr("backend.adapters.outbound.generation.openai.p0_normal_receipt.atomic_publish_fresh", refused)
    with pytest.raises(OSError):
        adapter.generate(request=dispatch)
    assert resolver.calls == transport.build_calls == transport.calls == 0


def test_secret_unavailable_preserves_reserved_unknown_without_attempt(tmp_path):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    resolver.before = lambda: (_ for _ in ()).throw(RuntimeError("SYNTHETIC_SECRET_UNAVAILABLE"))
    adapter.authorize(request=dispatch)
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.generate(request=dispatch)
    assert resolver.calls == 1 and transport.build_calls == transport.calls == 0
    assert adapter.receipt.read("UNKNOWN")["provider_attempts"] == 0


def test_supplied_sources_are_not_falsely_declared_used_and_guard_warnings_survive(tmp_path):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    content = __import__("json").loads(transport.response.output_text)
    content["title"] = "Source officielle — déjà validé"  # scanner must remain active
    transport.response = OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, canonical(content).decode(),
                                                transport.response.usage, service_tier="default")
    adapter = NormalP0GenerationAdapter(**config)
    adapter.authorize(request=dispatch)
    output = adapter.generate(request=dispatch)
    from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
    bundle = P0Production(output)
    controls = adapter.control_evidence(request=dispatch, bundle_sha256=bundle.sha256)
    assert controls["source_status"] == "RESERVE" and controls["declared_evidence_refs_used"] == []
    assert controls["provided_evidence_refs"] == [ref["evidence_id"] for ref in dispatch["references"]]
    assert controls["source_usage_declaration"] == "NOT_IN_OUTPUT_SCHEMA" and controls["review_state"] == "NOT_RUN"
    assert controls["guard_disposition"] == "ALLOW_WITH_WARNINGS"
    assert any(row["code"] == "AUTHORITY_CLAIM_TEXT" for row in controls["guard_warnings"])
    with pytest.raises(ValueError, match="CONTROLS_BINDING"):
        adapter.control_evidence(request=dispatch, bundle_sha256="0" * 64)


def test_receipt_root_retained_across_resolver_and_transport_latency(tmp_path):
    config, _, _, dispatch, _, _, resolver, transport = synthetic_configuration(tmp_path)
    adapter = NormalP0GenerationAdapter(**config)
    attempted_renames = []

    def rename_attempt():
        with pytest.raises(PermissionError):
            config["receipt_root"].rename(config["receipt_root"].with_name("substituted"))
        attempted_renames.append("denied")

    resolver.before = rename_attempt
    original = transport.create

    def delayed_create(*, request):
        rename_attempt()
        return original(request=request)

    transport.create = delayed_create
    adapter.authorize(request=dispatch)
    adapter.generate(request=dispatch)
    assert attempted_renames == ["denied", "denied"]
    assert resolver.calls == transport.calls == 1
    assert adapter.receipt.read("CONSUMED")["state"] == "CONSUMED"
    assert resolver.calls == transport.calls == 1
