"""Native synthetic campaign: acquired UNKNOWN plus one explicitly authorized distinct COURSE."""
import copy
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, preflight, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_unknown_continuation_contract import (
    COMPONENT_FIELDS,
    OPERATION,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    P0UnknownOffReader,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
)
from backend.infrastructure.composition.factories.p0_unknown_continuation import (
    P0UnknownContinuationComposition,
)
from backend.infrastructure.composition.factories.p0_unknown_off import P0UnknownOffComposition
from backend.infrastructure.config.secrets.provider import ProviderCredentialRef
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.work_orchestration.contracts.dto.p1_operation_intent import distinct_operation
from backend.shared_kernel.correlation import CorrelationId
from tests.integration.test_p0_product_rejected_continuity_native import (
    adoption,
    artifact,
    composed,
    create_successor,
)
from tests.integration.test_p0_product_unknown_off_native import build, facts
from tests.unit.test_p0_normal_generation import SyntheticResolver, SyntheticTransport
from tests.unit.test_p0_normal_policy import fixture as financial_fixture
from tests.unit.test_p0_rich_course_content import rich_content

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Original Windows LOCK required")


class DeclaredConstructionResolver(SyntheticResolver):
    """Constructed instead of a credential-capable resolver, before composition."""
    def __init__(self, ref):
        super().__init__()
        self.ref = ref

    def close(self):
        pass


@pytest.fixture(scope="module")
def baseline(tmp_path_factory, request):
    patch = pytest.MonkeyPatch()
    from backend.adapters.outbound import openai
    from backend.infrastructure.composition.factories import p0_normal_profile, p0_rejected_profile
    from tests.unit import test_p0_normal_profile as profile_fixture
    original_configuration = profile_fixture.configured_product

    def initial_campaign_configuration(*args, **kwargs):
        values = original_configuration(*args, **kwargs)
        # A fresh declared campaign starts with these root limits. Never edit
        # an existing permission, LOCK, event, slot or historical test fixture.
        values[0]["permission"].update(max_calls=14, cumulative_ceiling_usd="1.960000")
        return values

    patch.setattr(profile_fixture, "configured_product", initial_campaign_configuration)
    patch.setattr(p0_normal_profile, "MaskedLocalSecretResolver", DeclaredConstructionResolver)
    patch.setattr(p0_rejected_profile, "MaskedLocalSecretResolver", DeclaredConstructionResolver)
    patch.setattr(openai, "OpenAISDKResponsesTransportFactory", lambda **kwargs: SyntheticTransport(None))
    data = build(tmp_path_factory.mktemp("SYNTHETIC-three-historical"), patch, actual_source=getattr(request, "param", False))
    off = P0UnknownOffComposition(**data["args"])
    result = off.inbound.inspect(request=off.request, correlation_id=CorrelationId("SYNTHETIC_HISTORY_ONLY"))
    assert result.success
    report = {"schema": "LU-P1-ACTUAL-APPLICATION-UNKNOWN-OFF-INSPECTION-1.0",
        "timestamp_utc": datetime.now(UTC).isoformat(), "source_commit": data["plan"]["baseline_commit"],
        "source_tree": data["plan"]["source_tree"], "package_sha256": data["plan"]["package"]["sha256"],
        "plan_sha256": data["plan_desc"]["sha256"], "book_sha256": data["book_desc"]["sha256"],
        "binding_sha256": "d" * 64, "expected_owner_sha256": data["args"]["expected_owner_sha256"],
        "provider_calls": 0, "sql_queries": 0, "original_mutations": 0, "new_grants": 0,
        "quota_reset": False, "on_activation": False, "course_qualification": "NOT_COMPLETED",
        "teaching_acceptance": "NOT_ENGAGED_NOT_SIGNED", "stage": "APPLICATION_INBOUND_INSPECT",
        "state": "APPLICATION_OFF_INSPECTION_SUCCEEDED_NO_EFFECT_AUTHORITY", "observation": result.data.as_dict()}
    # The retained witness is deliberately indented, like the real acquired receipt.
    data["acquired"] = artifact(data["tmp_path"], "SYNTHETIC-acquired-result.json", json.dumps(report, indent=2).encode())
    yield data, patch
    off.close()
    data["current"].close()
    patch.undo()


@pytest.fixture
def case(baseline, tmp_path):
    data, patch = baseline
    root = data["root"]
    before = {p: p.read_bytes() for p in root.iterdir() if p.is_file()}
    yield data, patch, tmp_path
    archive = tmp_path / "SYNTHETIC_ADDED_RECEIPTS_RETAINED"
    archive.mkdir()
    for path in root.iterdir():
        if path.is_file() and path not in before:
            path.rename(archive / path.name)
    for path, raw in before.items():
        if not path.exists() or path.read_bytes() != raw:
            path.write_bytes(raw)


def configured(case, *, mode="on", mutate_owner=None, mutate_intent=None):
    b, patch, tmp = case
    app, endpoint, _, selection, reference, *_ = composed(patch, "FIRST_STMG")
    # Prepare through the same admitted Application resolver as the retained campaign.
    app.generation = b["current"].generation
    b["current"].bind(app, endpoint)
    old = P0NormalReceipt(b["root"], b["selected"]["namespace_sha256"]).read("DISPATCH")
    context = copy.deepcopy(old["dispatch"]["context"])
    context.update(objectives=["Comparer une seconde situation de coordination pédagogique indépendante"], institutional_resolution=None)
    prepared = app.execute("prepare", {"command_id": token_hex(16), "context": context,
        "reference": {"notion_id": reference["notion_id"], "passage_ref": reference["passage_ref"]}})
    request = as_plain(app.prepared[prepared["preparation_ref"]])
    base = b["f"]
    current_source = {k: b["plan"][k] for k in ("baseline_commit", "source_manifest", "package")}
    off = create_successor(tmp, b["current"], base["root"], base["saved"], anchor=base["anchor2"],
        anchor_desc=base["anchor2_desc"], witness=base["witness"], name="operation-off", enabled=False,
        disposition_desc=base["disp_desc"], output_schema=b["current"].permission["output_schema_sha256"],
        source_rebind=current_source)
    on = create_successor(tmp, off, base["root"], base["saved"], anchor=base["anchor2"],
        anchor_desc=base["anchor2_desc"], witness=base["witness"], name="operation-on", enabled=True,
        disposition_desc=base["disp_desc"], output_schema=off.permission["output_schema_sha256"],
        source_rebind={k: off.profile[k] for k in ("baseline_commit", "source_manifest", "package")})
    components4 = {"observed_evidence_sha256": base["evidence_desc"]["sha256"], "disposition_sha256": base["disp_desc"]["sha256"],
        "anchor2_sha256": base["anchor2_desc"]["sha256"], "manifest2_sha256": {"off": off.profile["continuity_manifest"]["sha256"],
        "on": on.profile["continuity_manifest"]["sha256"]}, "profile4_OFF_sha256": off.permission["profile_sha256"],
        "profile4_ON_sha256": on.permission["profile_sha256"], "source_manifest_sha256": off.profile["source_manifest"]["sha256"],
        "package_sha256": off.profile["package"]["sha256"]}
    control4 = adoption(tmp, components4, operation="OFF_ON_COMPONENT_REBIND", name="operation-v4", envelopes={
        "off": {"path": str(off.path), "sha256": sha(off.path.read_bytes())},
        "on": {"path": str(on.path), "sha256": sha(on.path.read_bytes())}})
    history = {"schema": "P1-UNKNOWN-CONTINUITY-HISTORY-1.0", "off_plan": b["plan_desc"], "off_book": b["book_desc"],
        "off_adoption": b["control_desc"], "off_expected_owner_sha256": b["args"]["expected_owner_sha256"],
        "off_result": b["acquired"], "policy": "PRESERVE_COUNT_NO_REPLAY", "frozen_inventory": [
            {"name": name, "sha256": row[0], "device": row[1], "inode": row[2]}
            for name, row in P0UnknownOffReader._inventory(b["root"]).items()]}
    hist = artifact(tmp, "SYNTHETIC-history.json", canonical(history))
    raw = NormalP0GenerationAdapter.body(build_p0_content_request(request))
    tokenizer_data = financial_fixture()[5]

    def tokenizer(body):
        return {**tokenizer_data, "request_sha256": sha(body), "manifest_sha256": on.permission["tokenizer_manifest_sha256"]}

    financial = {**on.permission, "request_sha256": sha(raw), "request_bytes": len(raw),
        "ceiling_usd": on.permission["per_call_ceiling_usd"]}
    proof = preflight(raw, financial, b["current"].tariff, tokenizer(raw), now=datetime.now(UTC))
    intention = {"schema": "P1-UNKNOWN-CONTINUITY-INTENT-1.0", **distinct_operation(old["dispatch"], request),
        "preparation_sha256": sha(canonical(request)), "request_sha256": sha(raw), "request_bytes": len(raw),
        "context_sha256": request["context_sha256"], "reference_set_sha256": sha(canonical(request["references"])),
        "cost_bound_usd": proof["cost_bound_usd"]}
    if mutate_intent:
        mutate_intent(intention)
    intention_desc = artifact(tmp, "SYNTHETIC-intent.json", canonical(intention))
    plan = {"schema": "P1-UNKNOWN-CONTINUITY-OPERATION-1.0", "history": hist, "intent": intention_desc,
        "profile_envelopes": {"off": {"path": str(off.path), "sha256": sha(off.path.read_bytes())},
            "on": {"path": str(on.path), "sha256": sha(on.path.read_bytes())}},
        "profile_adoption": {"path": str(control4), "sha256": sha(control4.read_bytes())},
        "issued_at_utc": datetime.now(UTC).isoformat(), "expires_at_utc": on.permission["expires_at_utc"],
        "operation": OPERATION, "max_new_operations": 1, "retry": 0, "fallback": "NONE", "parallelism": 1}
    plan_desc = artifact(tmp, "SYNTHETIC-operation.json", canonical(plan))
    components = {"plan_sha256": plan_desc["sha256"], "history_sha256": hist["sha256"], "intent_sha256": intention_desc["sha256"],
        "source_manifest_sha256": off.profile["source_manifest"]["sha256"], "package_sha256": off.profile["package"]["sha256"],
        "profile_off_sha256": off.permission["profile_sha256"], "profile_on_sha256": on.permission["profile_sha256"]}
    assert set(components) == COMPONENT_FIELDS
    book = artifact(tmp, "SYNTHETIC-operation-book.json", canonical({"schema": "P1-UNKNOWN-CONTINUITY-BOOK-1.0",
        "operation": OPERATION, "components": components}))
    owner = {"schema": "P1-UNKNOWN-CONTINUITY-OWNER-1.0", "operation": OPERATION, "book_sha256": book["sha256"],
        "components": components, "new_need_confirmed": True, "unknown_risk_acknowledged": True, "not_a_retry": True}
    if mutate_owner:
        mutate_owner(owner)
    owner_desc = artifact(tmp, "SYNTHETIC_NOT_OWNER.json", canonical(owner))
    control = artifact(tmp, "SYNTHETIC-operation-control.json", canonical({"schema": "P1-UNKNOWN-CONTINUITY-ADOPTION-1.0",
        "book": book, "owner_evidence": owner_desc}))
    args = dict(plan_path=Path(plan_desc["path"]), adoption_path=Path(control["path"]), expected_owner_sha256=owner_desc["sha256"],
        target=base["target"], saved_root=base["saved"], application_root=b["off_code"], mode=mode)
    if mode == "on":
        # Only the declared response template needs this display label; the
        # exact prepared request/context is never altered or re-enriched.
        template = copy.deepcopy(request)
        template["context"]["institutional_resolution"]["question"] = {"official_label": "Synthetic local question"}
        content = rich_content(template)
        content["course_chapter"]["concepts"][0].pop("notion")
        content["course_chapter"]["concepts"][0]["notion_id"] = "N1"
        resolver = DeclaredConstructionResolver(ProviderCredentialRef(str(on.profile["credential_ref"])))
        transport = SyntheticTransport(OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, canonical(content).decode(),
            OpenAIResponseUsage(1000, 0, 100, 1100, reasoning_tokens=0), service_tier="default"))
        from backend.adapters.outbound import openai
        from backend.infrastructure.composition.factories import p0_rejected_profile
        with patch.context() as construction:
            construction.setattr(p0_rejected_profile, "MaskedLocalSecretResolver", lambda ref: resolver)
            construction.setattr(openai, "OpenAISDKResponsesTransportFactory", lambda **kwargs: transport)
            construction.setattr(p0_rejected_profile, "LocalTokenizerHelper", lambda *args, **kwargs: tokenizer)
            comp = P0UnknownContinuationComposition(**args)
        assert comp.resolver is resolver and comp.generation.resolver is resolver
        assert comp.generation.transport is transport
        app.generation = comp.generation
    else:
        comp = P0UnknownContinuationComposition(**args)
    comp.bind(app, endpoint)
    return locals()


def preview_and_send(data):
    endpoint, prepared = data["endpoint"], data["prepared"]
    command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"]}
    shown = endpoint.consent_execute("consent_preview", command)
    consent = {**command, "preview_sha256": shown["preview_sha256"], "transfer_accepted": True, "cost_bound_accepted": True}
    return endpoint.consent_execute("consent_generate", consent)


def test_native_distinct_creation_preserves_history_and_counts_one_added_slot(case):
    before = facts(case[0]["root"])
    data = configured(case)
    try:
        def retained_operation_read_set():
            protected = set(data["comp"].read_phases.protected_paths)
            required = {Path(data[key]["path"]) for key in
                ("plan_desc", "control", "hist", "intention_desc", "book", "owner_desc")}
            assert required <= protected
            with pytest.raises(OSError):
                Path(data["intention_desc"]["path"]).write_bytes(b"SYNTHETIC_MUTATION_REFUSED")
        data["resolver"].before = retained_operation_read_set
        result = preview_and_send(data)
        assert result["state"] == "CANDIDATE"
        assert data["resolver"].calls == data["transport"].calls == 1
        from backend.infrastructure.composition.factories.local_browser import (
            build_saved_application,
        )
        from tests.integration.test_r6_p0_matrix_application import _text
        saved_root = case[2] / "SYNTHETIC-normal-library"
        saved = build_saved_application(saved_root, create=True, source=data["app"].saved_source, word_profile="product-v7")
        view = result["view"]
        identities = {k: view[k] for k in ("production_ref", "version_ref")}
        validation = data["app"].execute("validate", {"command_id": token_hex(16), **identities,
            "bundle_sha256": view["bundle_sha256"]})
        assert validation["status"] == "PASS" and validation["promotion"] == "NOT_PERFORMED"
        stored = saved.execute("save", body=identities, correlation="SYNTHETIC.normal.save")
        reopened = build_saved_application(saved_root, word_profile="product-v7")
        opened = reopened.execute("open", *identities.values(), correlation="SYNTHETIC.normal.reopen")
        assert opened["record_sha256"] == stored["record_sha256"] and opened["active_authority"] == "NONE_RESTORED"
        for kind in ("student", "correction"):
            document = reopened.execute("word", *identities.values(), kind=kind, correlation="SYNTHETIC.normal.export")
            assert isinstance(document, bytes) and _text(document)
            assert ("SENTINELLE_PROFESSEUR_" in _text(document)) is (kind == "correction")
            (case[2] / ("SYNTHETIC-" + kind + ".docx")).write_bytes(document)
        assert data["transport"].calls == 1
        observed = data["comp"]._ledger().snapshot()
        assert observed["slots_reserved"] == 4 and observed["consumed_count"] == 2 and observed["unknown_count"] == 1
        assert Decimal(observed["reserved_budget_usd"]) == case[0]["total"] + Decimal(data["proof"]["cost_bound_usd"])
        assert all(origin.permission["max_calls"] == 14 and Decimal(origin.permission["cumulative_ceiling_usd"]) == Decimal("1.96")
            for origin in data["comp"].chain.origins)
        assert all(facts(case[0]["root"])[name] == value for name, value in before.items())
        with pytest.raises(ValueError, match="ALREADY_RESERVED"):
            preview_and_send(data)
        assert data["transport"].calls == 1
    finally:
        data["comp"].close()


def test_native_off_has_no_generation_resolver_or_new_slot(case):
    before = facts(case[0]["root"])
    data = configured(case, mode="off")
    try:
        assert data["app"].generation is None and data["endpoint"].consent_execute is None
        assert data["comp"].resolver is None
        assert facts(case[0]["root"]) == before
    finally:
        data["comp"].close()


@pytest.mark.parametrize("baseline", [True], indirect=True)
@pytest.mark.skipif((Path(__file__).resolve().parents[2] / ".git").exists(), reason="Exact extracted distribution required")
def test_native_actual_distributed_source_one_operation_and_conservation_cycle(case):
    """Exact current source/package, while historical source remains its own immutable witness."""
    test_native_distinct_creation_preserves_history_and_counts_one_added_slot(case)
