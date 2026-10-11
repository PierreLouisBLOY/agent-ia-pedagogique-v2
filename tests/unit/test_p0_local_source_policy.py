import copy

import pytest

from backend.adapters.outbound.generation.openai import p0_product_policy as policy
from tests.unit import test_p0_local_reference_context as fixture


def local_receipts():
    manifest, sources, selection, reference, passages, native = fixture.fixture()
    query = fixture.query(manifest, sources)
    bound = fixture.resolve(query, selection, reference, passages, native)
    receipts = query.execute(request=fixture.request(selection, reference, passages, bound), passages=[passages[1]], resolution=bound)
    permission = {"source_admission_manifest_sha256": "e" * 64, "owner_decision_sha256": "f" * 64, "profile_sha256": "8" * 64}
    adoption = {"profile_schema": "P0-NORMAL-PROFILE-2.0", "owner_decision_schema": "P0-NORMAL-OWNER-DECISION-2.0",
        "profile_sha256": "8" * 64, "owner_decision_sha256": "f" * 64, "local_reference_context_manifest_sha256": query.manifest_sha256}
    return permission, receipts, adoption


def test_local_receipt_needs_exact_explicit_successor_adoption():
    permission, receipts, adoption = local_receipts()
    policy.validate_source_receipts(permission, receipts, local_context_adoption=adoption)
    assert receipts[0]["available_authority"] == "UNKNOWN"
    with pytest.raises(ValueError):
        policy.validate_source_receipts(permission, receipts)


@pytest.mark.parametrize("key", ["profile_schema", "owner_decision_schema", "profile_sha256", "owner_decision_sha256", "local_reference_context_manifest_sha256"])
def test_mutated_local_adoption_refuses(key):
    permission, receipts, adoption = local_receipts()
    adoption[key] = "0" * 64
    with pytest.raises(ValueError):
        policy.validate_source_receipts(permission, receipts, local_context_adoption=adoption)


@pytest.mark.parametrize("key", ["local_reference_context_manifest_sha256", "selection_sha256", "canonical_notion_entry_scope_sha256", "canonical_institutional_resolution_sha256", "source_scope_status", "unexpected"])
def test_mutated_closed_local_receipt_refuses(key):
    permission, receipts, adoption = local_receipts()
    receipts = copy.deepcopy(receipts)
    receipts[0][key] = "short"
    with pytest.raises(ValueError):
        policy.validate_source_receipts(permission, receipts, local_context_adoption=adoption)


def test_local_status_cannot_be_smuggled_in_legacy_receipt():
    permission, receipts, adoption = local_receipts()
    legacy = {key: value for key, value in receipts[0].items() if key in policy.SOURCE_FIELDS}
    legacy["schema"] = "P0-SOURCE-ADMISSION-RECEIPT-1.0"
    with pytest.raises(ValueError):
        policy.validate_source_receipts(permission, [legacy], local_context_adoption=adoption)


@pytest.mark.parametrize("kind,mode", [("COURSE", None), ("EXERCISE", None), ("QUESTION_SET", "OPEN_QUESTIONS"),
    ("QUESTION_SET", "QCM"), ("QUESTION_SET", "QUIZ"), ("ASSESSMENT", None)])
def test_broker_uses_bound_successor_for_six_families_with_no_effect_before_consent(tmp_path, kind, mode):
    from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
    from tests.unit.test_p0_product_permission import configured_product, consent, preview
    settings, app, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path, kind, mode)
    adoption = {"profile_schema": "P0-NORMAL-PROFILE-2.0", "owner_decision_schema": "P0-NORMAL-OWNER-DECISION-2.0",
        "profile_sha256": settings["permission"]["profile_sha256"], "owner_decision_sha256": settings["permission"]["owner_decision_sha256"],
        "local_reference_context_manifest_sha256": "7" * 64}
    receipts = [{**receipts[0], "schema": "P0-SOURCE-ADMISSION-RECEIPT-2.0", "source_scope_status": "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT",
        "local_reference_context_manifest_sha256": "7" * 64, "selection_sha256": "6" * 64,
        "canonical_notion_entry_scope_sha256": "5" * 64, "canonical_institutional_resolution_sha256": "4" * 64}]
    adapter = P0ProductGenerationAdapter(**settings, local_context_adoption=adoption)
    app.generation = adapter
    shown = preview(adapter, prepared, dispatch, receipts)
    accepted = consent(prepared, shown)
    assert resolver.calls == transport.calls == 0 and adapter.ledger.slots() == []
    adapter.accept(request=dispatch, consent=accepted, source_receipts=receipts)
    assert resolver.calls == transport.calls == 0 and len(adapter.ledger.slots()) == 1
    result = app.execute("generate", {key: accepted[key] for key in ("command_id", "preparation_ref", "preparation_sha256")})
    assert result["state"] == "CANDIDATE" and resolver.calls == transport.calls == 1


@pytest.mark.parametrize("mutation", ["manifest", "profile", "owner", "preview_receipt", "new_receipt", "default"])
def test_changed_local_binding_stops_before_new_slot_secret_or_transport(tmp_path, mutation):
    from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
    from tests.unit.test_p0_product_permission import configured_product, consent, preview
    settings, _, prepared, dispatch, old_receipts, _, _, resolver, transport = configured_product(tmp_path)
    _, new_receipts, _ = local_receipts()
    receipts = [{**new_receipts[0], "reference": old_receipts[0]["reference"],
        "admission_manifest_sha256": settings["permission"]["source_admission_manifest_sha256"],
        "owner_admission_sha256": settings["permission"]["owner_decision_sha256"]}]
    adoption = {"profile_schema": "P0-NORMAL-PROFILE-2.0", "owner_decision_schema": "P0-NORMAL-OWNER-DECISION-2.0",
        "profile_sha256": settings["permission"]["profile_sha256"], "owner_decision_sha256": settings["permission"]["owner_decision_sha256"],
        "local_reference_context_manifest_sha256": receipts[0]["local_reference_context_manifest_sha256"]}
    if mutation == "default":
        adapter = P0ProductGenerationAdapter(**settings)
        with pytest.raises(ValueError):
            preview(adapter, prepared, dispatch, receipts)
    else:
        adapter = P0ProductGenerationAdapter(**settings, local_context_adoption=adoption)
        shown = preview(adapter, prepared, dispatch, receipts)
        accepted = consent(prepared, shown)
        if mutation in {"manifest", "profile", "owner"}:
            key = {"manifest": "local_reference_context_manifest_sha256", "profile": "profile_sha256", "owner": "owner_decision_sha256"}[mutation]
            adapter.local_context_adoption[key] = "0" * 64
        elif mutation == "preview_receipt":
            adapter.previews[shown["preview_sha256"]]["source_receipts"][0]["selection_sha256"] = "0" * 64
        else:
            receipts[0]["selection_sha256"] = "0" * 64
        with pytest.raises(ValueError):
            adapter.accept(request=dispatch, consent=accepted, source_receipts=receipts)
    assert adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0


def test_profile2_witness_refuses_legacy_receipt_without_changing_legacy_policy():
    permission, receipts, adoption = local_receipts()
    legacy = {key: value for key, value in receipts[0].items() if key in policy.SOURCE_FIELDS}
    legacy.update(schema="P0-SOURCE-ADMISSION-RECEIPT-1.0", source_scope_status="CANONICAL_NOTION_ONLY")
    policy.validate_source_receipts(permission, [legacy])
    with pytest.raises(ValueError, match="P1_LOCAL_CONTEXT_RECEIPT_REQUIRED"):
        policy.validate_source_receipts(permission, [legacy], local_context_adoption=adoption)


@pytest.mark.parametrize("phase", ["preview", "accept"])
def test_profile2_broker_refuses_legacy_receipt_before_slot_secret_and_transport(tmp_path, phase):
    from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
    from tests.unit.test_p0_product_permission import configured_product, consent, preview

    settings, _, prepared, dispatch, old_receipts, _, _, resolver, transport = configured_product(tmp_path)
    adoption = {"profile_schema": "P0-NORMAL-PROFILE-2.0", "owner_decision_schema": "P0-NORMAL-OWNER-DECISION-2.0",
        "profile_sha256": settings["permission"]["profile_sha256"], "owner_decision_sha256": settings["permission"]["owner_decision_sha256"],
        "local_reference_context_manifest_sha256": "7" * 64}
    adapter = P0ProductGenerationAdapter(**settings, local_context_adoption=adoption)
    if phase == "preview":
        with pytest.raises(ValueError, match="P1_LOCAL_CONTEXT_RECEIPT_REQUIRED"):
            preview(adapter, prepared, dispatch, old_receipts)
    else:
        receipts = [{**old_receipts[0], "schema": "P0-SOURCE-ADMISSION-RECEIPT-2.0", "source_scope_status": "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT",
            "local_reference_context_manifest_sha256": "7" * 64, "selection_sha256": "6" * 64,
            "canonical_notion_entry_scope_sha256": "5" * 64, "canonical_institutional_resolution_sha256": "4" * 64}]
        shown = preview(adapter, prepared, dispatch, receipts)
        with pytest.raises(ValueError, match="P1_LOCAL_CONTEXT_RECEIPT_REQUIRED"):
            adapter.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=old_receipts)
    assert adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0
