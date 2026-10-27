"""Declared synthetic P1 grants/admission/tokenizer/transport, zero real calls."""
import json
import subprocess
import sys
from datetime import timedelta
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_product_policy import P1_HASHES
from tests.unit.test_p0_normal_generation import NOW, synthetic_configuration


def configured_product(tmp_path, kind="ASSESSMENT", mode=None):
    config, app, prepared, dispatch, gids, tokenizer, resolver, transport = synthetic_configuration(tmp_path, kind, mode)
    grant = config["grant"]
    permission = {key: grant.get(key, "b" * 64) for key in P1_HASHES}
    permission.update(schema="P0-PRODUCT-CREATE-PERMISSION-1.0", baseline_commit=grant["baseline_commit"],
        issued_at_utc=grant["issued_at_utc"], expires_at_utc=(NOW + timedelta(days=1)).isoformat(),
        allowed_families=["COURSE", "EXERCISE", "OPEN_QUESTIONS", "QCM", "QUIZ", "ASSESSMENT"],
        allowed_levels=["FIRST_STMG", "FINAL_STMG", "BTS_CG_YEAR_1", "BTS_CG_YEAR_2"],
        selected_admitted_sources_only=True, excluded_oracles_and_private_evidence=True, require_exact_local_consent=True,
        local_operator_delegation_accepted=True, provider="OPENAI", model=grant["model"], endpoint=grant["endpoint"],
        reasoning="low", tier="default", max_output_tokens=4096, max_calls=3, count_calls=0, review_calls=0,
        modify_calls=0, retry=0, fallback="NONE", parallelism=1, per_call_ceiling_usd="0.140000",
        cumulative_ceiling_usd="0.300000", live_authorized=True, transfer_authorized=True)
    pids = {key: permission[key] for key in P1_HASHES | {"baseline_commit"}}

    def identities(request, body):
        return {**gids, "request_sha256": sha(body), "request_bytes": len(body), "context_sha256": request["context_sha256"],
            "preparation_sha256": sha(canonical(request)), "reference_set_sha256": sha(canonical(request["references"])),
            "output_schema_sha256": sha(canonical(build_p0_content_request(request).output_schema))}

    def tokenized(body):
        return {**tokenizer, "request_sha256": sha(body)}

    receipt = {"schema": "P0-SOURCE-ADMISSION-RECEIPT-1.0", "reference": dispatch["references"][0],
        "available_authority": "UNKNOWN", "provenance": {"content_trust": "UNTRUSTED_CONTENT"},
        "source_status": {"identity_status": "UNKNOWN"}, "admission_manifest_sha256": permission["source_admission_manifest_sha256"],
        "admission_scope_sha256": "b" * 64, "owner_admission_sha256": permission["owner_decision_sha256"],
        "institutional_resolution_sha256": "c" * 64, "source_scope_status": "CANONICAL_NOTION_ONLY",
        "transmission_admission": "OWNER_ADMITTED_LOCAL_CONTENT_ONLY"}
    settings = {"permission": permission, "permission_identities": lambda: pids, "identity_source": identities,
        "tariff": config["tariff"], "tokenizer": tokenized, "receipt_root": config["receipt_root"],
        "resolver": resolver, "credential_ref": config["credential_ref"], "transport": transport, "clock": lambda: NOW}
    return settings, app, prepared, dispatch, [receipt], pids, tokenizer, resolver, transport


def preview(adapter, prepared, dispatch, receipts):
    return adapter.preview(request=dispatch, preparation_ref=prepared["preparation_ref"],
        preparation_sha256=prepared["preparation_sha256"], source_receipts=receipts)


def consent(prepared, shown):
    return {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"], "preview_sha256": shown["preview_sha256"],
        "transfer_accepted": True, "cost_bound_accepted": True}


@pytest.mark.parametrize("kind,mode", [("COURSE", None), ("EXERCISE", None), ("QUESTION_SET", "OPEN_QUESTIONS"),
    ("QUESTION_SET", "QCM"), ("QUESTION_SET", "QUIZ"), ("ASSESSMENT", None)])
def test_exact_operator_consent_derives_g1_and_application_candidate_once(tmp_path, kind, mode):
    settings, app, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path, kind, mode)
    adapter = P0ProductGenerationAdapter(**settings)
    app.generation = adapter
    shown = preview(adapter, prepared, dispatch, receipts)
    assert resolver.calls == transport.calls == 0 and adapter.ledger.slots() == []
    assert shown["preview"]["source_receipts"][0]["available_authority"] == "UNKNOWN"
    accepted = consent(prepared, shown)
    adapter.accept(request=dispatch, consent=accepted, source_receipts=receipts)
    assert resolver.calls == transport.calls == 0 and len(adapter.ledger.slots()) == 1
    result = app.execute("generate", {key: accepted[key] for key in ("command_id", "preparation_ref", "preparation_sha256")})
    assert result["state"] == "CANDIDATE" and resolver.calls == transport.calls == 1
    with pytest.raises(ValueError, match="UNKNOWN_OR_CONSUMED"):
        adapter.accept(request=dispatch, consent={**accepted, "command_id": token_hex(16)}, source_receipts=receipts)
    assert transport.calls == 1


@pytest.mark.parametrize("mutation", ["delegate", "profile", "cost", "tokens", "source", "clock", "unknown_field"])
def test_fresh_recompute_and_identity_changes_stop_before_slot_or_provider(tmp_path, mutation):
    settings, _, prepared, dispatch, receipts, pids, tokenizer, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    shown = preview(adapter, prepared, dispatch, receipts)
    accepted = consent(prepared, shown)
    if mutation == "delegate":
        pids["operator_delegation_sha256"] = "0" * 64
    elif mutation == "profile":
        pids["profile_sha256"] = "0" * 64
    elif mutation == "cost":
        stored = adapter.previews.pop(shown["preview_sha256"])
        stored["cost_bound_usd"] = "0.001000"
        stored["preflight"]["cost_bound_usd"] = "0.001000"
        key = sha(canonical(stored))
        adapter.previews[key] = stored
        accepted["preview_sha256"] = key
    elif mutation == "tokens":
        tokenizer["serialized_json_tokens"] += 1
    elif mutation == "source":
        receipts[0]["available_authority"] = "OFFICIAL"
    elif mutation == "clock":
        adapter.clock = lambda: NOW + timedelta(minutes=16)
    else:
        accepted["grant"] = {}
    with pytest.raises(ValueError):
        adapter.accept(request=dispatch, consent=accepted, source_receipts=receipts)
    assert adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0


def test_no_exact_consent_authorizes_no_dispatch_or_fake_result(tmp_path):
    settings, _, _, dispatch, _, _, _, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    assert not adapter.authorize(request=dispatch)
    with pytest.raises(ValueError, match="CONSENT_REQUIRED"):
        adapter.generate(request=dispatch)
    assert resolver.calls == transport.calls == 0 and adapter.ledger.slots() == []


def test_preview_consumption_survives_second_instance_and_new_command_entropy(tmp_path):
    settings, _, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    first, second = P0ProductGenerationAdapter(**settings), P0ProductGenerationAdapter(**settings)
    shown = preview(first, prepared, dispatch, receipts)
    preview(second, prepared, dispatch, receipts)
    first.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=receipts)
    with pytest.raises(ValueError, match="PREVIEW_CONSUMED"):
        second.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=receipts)
    assert len(second.ledger.slots()) == 1 and resolver.calls == transport.calls == 0


def test_failed_g1_publication_preserves_budget_pessimistically(tmp_path, monkeypatch):
    settings, _, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    settings["permission"].update(max_calls=1, cumulative_ceiling_usd="0.140000")
    adapter = P0ProductGenerationAdapter(**settings)
    shown = preview(adapter, prepared, dispatch, receipts)
    adapter.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=receipts)
    actual = next(iter(adapter.pending.values()))
    monkeypatch.setattr(actual.receipt, "reserve", lambda **_: (_ for _ in ()).throw(ValueError("SYNTHETIC_PUBLICATION_STOP")))
    adapter.authorize(request=dispatch)
    with pytest.raises(ValueError, match="PUBLICATION_STOP"):
        adapter.generate(request=dispatch)
    assert len(adapter.ledger.slots()) == 1 and resolver.calls == transport.calls == 0


def test_timeout_retains_slot_and_stops_recovery_without_second_effect(tmp_path):
    settings, _, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    shown = preview(adapter, prepared, dispatch, receipts)
    adapter.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=receipts)
    transport.failure = TimeoutError("SYNTHETIC_TIMEOUT")
    adapter.authorize(request=dispatch)
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        adapter.generate(request=dispatch)
    reopened = P0ProductGenerationAdapter(**settings)
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        reopened.confirmed_dispatches()
    assert resolver.calls == transport.calls == 1 and len(reopened.ledger.slots()) == 1


def test_confirmed_restart_recovery_is_read_only_and_never_reauthorizes(tmp_path):
    settings, _, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    shown = preview(adapter, prepared, dispatch, receipts)
    adapter.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=receipts)
    adapter.authorize(request=dispatch)
    original = adapter.generate(request=dispatch)
    settings["clock"] = lambda: NOW + timedelta(days=2)
    settings["identity_source"] = lambda *args: (_ for _ in ()).throw(AssertionError("NO_CURRENT_IDENTITY_FOR_REAUTH"))
    settings["tokenizer"] = lambda *args: (_ for _ in ()).throw(AssertionError("NO_TOKENIZER_FOR_REAUTH"))
    reopened = P0ProductGenerationAdapter(**settings)
    assert reopened.confirmed_dispatches() == (dispatch,)
    assert reopened.recover_confirmed(request=dispatch) == original
    assert not reopened.authorize(request=dispatch)
    assert resolver.calls == transport.calls == 1
    controls = reopened.control_evidence(request=dispatch, bundle_sha256=sha(canonical(original)))
    assert controls["source_status"] == "RESERVE"


@pytest.mark.parametrize("limit", ["calls", "budget"])
def test_new_preview_cannot_exceed_pessimistic_shared_limits(tmp_path, limit):
    settings, _, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    if limit == "calls":
        settings["permission"].update(max_calls=1, cumulative_ceiling_usd="0.140000")
    else:
        settings["permission"].update(cumulative_ceiling_usd="0.100000")
    adapter = P0ProductGenerationAdapter(**settings)
    shown = preview(adapter, prepared, dispatch, receipts)
    adapter.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=receipts)
    adapter.clock = lambda: NOW + timedelta(seconds=1)
    newer = preview(adapter, prepared, dispatch, receipts)
    assert newer["preview_sha256"] != shown["preview_sha256"]
    with pytest.raises(ValueError, match="BUDGET"):
        adapter.accept(request=dispatch, consent=consent(prepared, newer), source_receipts=receipts)
    assert len(adapter.ledger.slots()) == 1 and resolver.calls == transport.calls == 0


def test_windows_retained_budget_lock_excludes_a_second_process(tmp_path):
    settings, _, _, _, _, _, _, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    config = tmp_path / "synthetic-permission.json"
    config.write_text(json.dumps(settings["permission"]), encoding="utf-8")
    code = """
import json, sys
from pathlib import Path
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
ledger=P0ProductLedger(root=Path(sys.argv[1]), permission=json.loads(Path(sys.argv[2]).read_text()))
try:
    with ledger.locked(): print('SYNTHETIC_LOCK_ACQUIRED')
except ValueError as exc:
    print(str(exc))
    raise SystemExit(23)
"""
    args = [sys.executable, "-B", "-c", code, str(settings["receipt_root"]), str(config)]
    with adapter.ledger.locked():
        blocked = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
        assert blocked.returncode == 23 and blocked.stdout.strip() == "P0_PRODUCT_CONCURRENT_DISPATCH", blocked.stderr
    released = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
    assert released.returncode == 0 and released.stdout.strip() == "SYNTHETIC_LOCK_ACQUIRED", released.stderr
    assert adapter.ledger.slots() == [] and resolver.calls == transport.calls == 0


def test_permission_lock_covers_provider_effect_between_independent_brokers(tmp_path, monkeypatch):
    settings, _, prepared, dispatch, receipts, _, _, _, transport = configured_product(tmp_path)
    adapter, competitor = P0ProductGenerationAdapter(**settings), P0ProductGenerationAdapter(**settings)
    shown = preview(adapter, prepared, dispatch, receipts)
    adapter.accept(request=dispatch, consent=consent(prepared, shown), source_receipts=receipts)
    original = transport.build
    checked = []
    def competing_build(**kwargs):
        with pytest.raises(ValueError, match="CONCURRENT_DISPATCH"):
            with competitor.ledger.locked():
                raise AssertionError("PARALLEL_PROVIDER_EFFECT_ALLOWED")
        checked.append(True)
        return original(**kwargs)
    monkeypatch.setattr(transport, "build", competing_build)
    assert adapter.authorize(request=dispatch)
    adapter.generate(request=dispatch)
    assert checked == [True] and transport.calls == 1


@pytest.mark.parametrize("earlier", ["unknown", "confirmed"])
def test_controls_bind_exact_confirmed_result_and_refuse_duplicate_confirmations(tmp_path, earlier):
    settings, _, prepared, dispatch, receipts, _, _, _, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    first = preview(adapter, prepared, dispatch, receipts)
    adapter.accept(request=dispatch, consent=consent(prepared, first), source_receipts=receipts)
    assert adapter.authorize(request=dispatch)
    if earlier == "unknown":
        transport.failure = TimeoutError("SYNTHETIC_PRIOR_UNKNOWN")
        with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
            adapter.generate(request=dispatch)
        transport.failure = None
    else:
        adapter.generate(request=dispatch)
    adapter.clock = lambda: NOW + timedelta(seconds=1)
    second = preview(adapter, prepared, dispatch, receipts)
    adapter.accept(request=dispatch, consent=consent(prepared, second), source_receipts=receipts)
    assert adapter.authorize(request=dispatch)
    result = adapter.generate(request=dispatch)
    if earlier == "unknown":
        controls = adapter.control_evidence(request=dispatch, bundle_sha256=sha(canonical(result)))
        assert controls["source_status"] == "RESERVE" and transport.calls == 2
        first_adapter = next(iter(adapter.adapters.values()))
        assert first_adapter.receipt.exists("UNKNOWN")
    else:
        with pytest.raises(ValueError, match="CONFIRMATION_AMBIGUOUS"):
            adapter.control_evidence(request=dispatch, bundle_sha256=sha(canonical(result)))
        with pytest.raises(ValueError, match="CONFIRMATION_AMBIGUOUS"):
            adapter.confirmed_dispatches()
    # Two separately accepted synthetic grants are not an automatic retry.
    assert transport.calls == 2 and len(adapter.ledger.slots()) == 2
