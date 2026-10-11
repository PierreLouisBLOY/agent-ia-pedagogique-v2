"""Continue unaffected scopes; preserve M01 review security refusal, no report laundering."""
from __future__ import annotations

import argparse
import json
import re
import sys
from secrets import token_hex
from typing import Any

import mega_no_count_continuation as prior
import mega_no_count_runner as BASE
from mega_f02_windows_handles import Reservation, directory_identity
from mega_no_count_gate import (
    ARTIFACT,
    BASELINE,
    CAMPAIGN,
    ROOT,
    canonical,
    preflight,
    sha,
    stamp,
)
from mega_retained_inputs import RetainedInputs

from backend.infrastructure.composition.factories.local_browser import build_saved_application

PREVIOUS_PROOF = prior.PROOF
PREVIOUS_SHA = "c201a377f97520a56a3eedbfb2bc6add5274a649373d6145b6a30a46e2901804"
PREVIOUS = BASE.PRIVATE / PREVIOUS_SHA
PROOF = ARTIFACT / "B_REMAINING_SCOPES_20261004"


def history(pins: dict[str, str] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    actual = {p.name: sha(p.read_bytes()) for p in PREVIOUS.iterdir() if p.is_file()}
    if pins is not None and actual != pins:
        raise ValueError("SECOND_RESERVATION_EVIDENCE_CHANGED")
    if sha((PREVIOUS / "campaign_grant.json").read_bytes()) != PREVIOUS_SHA:
        raise ValueError("SECOND_GRANT_CHANGED")
    stopped = json.loads((PREVIOUS / "campaign_stopped.json").read_bytes())
    receipt = json.loads((PREVIOUS / "M01_REVIEW_receipt.json").read_bytes())
    if (stopped["consumed_operations"] != [["M01", "CREATE"], ["M01", "REVIEW"]]
        or receipt["scenario"] != "M01" or receipt["operation"] != "REVIEW" or receipt["http_status"] != 200
        or receipt["baseline"] != BASELINE or receipt["campaign"] != CAMPAIGN
        or receipt["authorization_sha256"] != PREVIOUS_SHA or receipt["reservation_namespace_sha256"] != PREVIOUS_SHA
        or receipt["provider_attempts"] != 1 or receipt["count_calls"] != 0 or receipt["retry"] != 0 or receipt["fallback"] != "NONE"):
        raise ValueError("SECOND_SINGLE_CONFIRMED_REVIEW_REQUIRED")
    for kind in ("request", "response", "output"):
        if sha((PREVIOUS / ("M01_REVIEW_" + kind + ".json")).read_bytes()) != receipt[kind + "_sha256"]:
            raise ValueError("SECOND_RECEIPT_HASH_CHANGED")
    proof_raw = (PREVIOUS / "M01_REVIEW_preflight.json").read_bytes()
    proof = json.loads(proof_raw)
    if sha(proof_raw) != receipt["financial_preflight_sha256"] or proof["max_cost_usd"] != receipt["reserved_cost_usd"]:
        raise ValueError("SECOND_FINANCIAL_RESERVATION_CHANGED")
    from decimal import Decimal
    original, _, _ = prior.parent_evidence()
    total = Decimal(original["reserved_cost_usd"]) + Decimal(receipt["reserved_cost_usd"])
    if Decimal(stopped["reserved_cost_usd"]) != total or Decimal(receipt["campaign_reserved_cost_usd"]) != total:
        raise ValueError("SECOND_CUMULATIVE_RESERVATION_CHANGED")
    return receipt, actual


def grant_check() -> dict[str, Any]:
    grant = prior.ORIGINAL_CHECK()
    first = json.loads((prior.PARENT / "campaign_grant.json").read_bytes())
    if (grant["issued_at"] != first["issued_at"] or grant["expires_at"] != first["expires_at"]
        or grant["parent_authorization_sha256"] != PREVIOUS_SHA
        or grant["remaining_operations"] != [[f"M{i:02}", op] for i in range(2, 8) for op in ("CREATE", "REVIEW")]):
        raise ValueError("REMAINING_OPERATION_OR_DURATION_CHANGED")
    prior.parent_evidence(grant["first_parent_artifact_sha256"])
    history(grant["second_parent_artifact_sha256"])
    return grant


class Controller(prior.Controller):
    def __init__(self, proposal: dict[str, Any]) -> None:
        super().__init__(proposal)
        receipt, _ = history()
        self.budget.reserve("M01", "REVIEW", {"max_cost_usd": receipt["reserved_cost_usd"]})
        self.budget.finish("M01", "REVIEW", confirmed=True)
        self.receipts.append(receipt)

    def send(self, sid: str, operation: str, raw: bytes, expected: str | None) -> tuple[dict[str, Any], str]:
        if sid == "M01":
            raise ValueError("M01_CREATE_AND_REVIEW_ALREADY_CONSUMED")
        return super().send(sid, operation, raw, expected)


def install() -> None:
    prior.install()
    BASE.PROOF = PROOF
    BASE.__dict__.update({"Controller": Controller})
    BASE.grant_check = grant_check


def one_case(controller: Any, generation: Any, review: Any, endpoint: Any, saved: Any, sid: str, ready: dict[str, Any]) -> dict[str, Any]:
    generation.scenario = review.scenario = sid
    generated = BASE.p0_call(endpoint, "generate", {"command_id": token_hex(16), "preparation_ref": ready["preparation_ref"],
        "preparation_sha256": ready["preparation_sha256"]})
    controller.publish(sid + "_application_generation.json", canonical(generated))
    view = generated["view"]
    identity = {key: view[key] for key in ("production_ref", "version_ref", "bundle_sha256")}
    if sid == "M01":
        reviewed = {"state": "REVIEW_REFUSED_BY_CANONICAL_SECURITY", "review_sha256": None,
            "historical_provider_receipt_sha256": sha((PREVIOUS / "M01_REVIEW_receipt.json").read_bytes()),
            "original_review_target": "PRESERVED_IN_ORIGINAL_FROZEN_REQUEST", "application_report": "NOT_MATERIALIZED",
            "binding_of_recovered_copy": "REVIEW_NOT_REBOUND_OR_REPLAYED", "local_correction": "BLOCKED_NO_CANONICAL_REPORT",
            "security_guard": "UNCHANGED", "provider_calls_this_recovery": 0}
    else:
        count_before = len(controller.receipts)
        try:
            reviewed = BASE.p0_call(endpoint, "review", {"command_id": token_hex(16), **identity})
        except ValueError as error:
            # Only a CONFIRMED exact response may have a local report defect isolated.
            # HTTP/usage/financial/uncertain errors have no confirmed receipt and stop.
            if len(controller.receipts) != count_before + 1 or controller.receipts[-1]["operation"] != "REVIEW":
                raise
            symbolic = str(error) if re.fullmatch(r"[A-Z0-9_]{1,90}", str(error)) else "LOCAL_REPORT_REJECTED"
            reviewed = {"state": "APPLICATION_REVIEW_REJECTED", "review_sha256": None, "error_code": symbolic,
                "application_report": "NOT_MATERIALIZED", "security_guard": "UNCHANGED", "provider_retry": 0,
                "local_correction": "BLOCKED_NO_CANONICAL_REPORT"}
    controller.publish(sid + "_application_review_disposition.json", canonical(reviewed))
    saved_receipt = saved.execute("save", body={key: identity[key] for key in ("production_ref", "version_ref")}, correlation="mega.remaining.save")
    controller.publish(sid + "_saved_receipt.json", canonical(saved_receipt))
    return {"scenario_id": sid, "production": identity, "generation": "CONFIRMED", "review": reviewed["state"],
        "review_sha256": reviewed["review_sha256"], "saved": saved_receipt}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-live", action="store_true")
    args = parser.parse_args()
    install()
    proposal = BASE.sources()
    controller, generation, review, p0, endpoint, preparations, target = BASE.prepare(proposal)
    grant = grant_check()
    tariff = json.loads((ROOT / "MEGA_TOKENIZER_ACQUISITION_20261004/03_CURRENT_OFFICIAL_TARIFF.json").read_text())
    proofs = [{"scenario_id": sid, **preflight(raw, tariff, expected_sha=controller.scopes[sid]["generation_sha256"])}
        for sid, raw in generation.captured.items()]
    if not args.native_live:
        controller.publisher = lambda name, raw: None
        generation.armed, generation.scenario = True, "M01"
        saved_root = BASE.PRIVATE / ("saved-offline-disposition-" + token_hex(8))
        saved = build_saved_application(saved_root, create=True, source=p0.saved_source)
        checked = one_case(controller, generation, review, endpoint, saved, "M01", preparations["M01"])
        target.validate()
        (PROOF / "OFFLINE_PREFLIGHT.json").write_bytes(canonical({"state": "PASS_EXECUTED", "provider_calls": 0, "count_calls": 0,
            "historical_confirmed_operations": sorted(controller.budget.consumed), "inherited_reserved_cost_usd": str(controller.budget.reserved),
            "M01_REVIEW": "SECURITY_REFUSAL_PRESERVED_NOT_REBOUND", "M01_application_save_check": checked,
            "remaining_operations_max": 12, "preflights": proofs}))
        print("OFFLINE_REMAINING_SCOPES_PASS; PAST_CREATE_REVIEW_PRESERVED; NEW_PROVIDER=0")
        return 0
    reservation = BASE.PRIVATE / sha((PROOF / "CURRENT_GRANT.json").read_bytes())
    pins = [ROOT / name for name in grant["code_pins"]]
    pins += [PROOF / "CURRENT_GRANT.json", PROOF / "CURRENT_GRANT.sha256", ARTIFACT / "A6_OWNER_LIVE_GATE.json"]
    pins += [prior.PARENT / name for name in grant["first_parent_artifact_sha256"]]
    pins += [PREVIOUS / name for name in grant["second_parent_artifact_sha256"]]
    pins += list((ARTIFACT / "live-payloads").glob("*_GENERATE.json")) + list(BASE.SOURCE.rglob("*.py"))
    helper = ROOT / "MEGA_TOKENIZER_ACQUISITION_20261004"
    pins += [helper / "01_ACQUISITION_MANIFEST.json", helper / "02_HELPER_INPUT_MANIFEST.json", helper / "o200k_base.tiktoken"]
    pins += list((helper / "encoding-cache").iterdir())
    pins += [p for p in (helper / "venv/Lib/site-packages").rglob("*") if p.is_file() and p.suffix in {".py", ".pyd"}]
    with RetainedInputs(ROOT, pins), Reservation(reservation, BASE.PRIVATE, directory_identity(BASE.PRIVATE)) as held:
        if grant_check() != grant:
            raise ValueError("REMAINING_GRANT_SUBSTITUTED")
        controller.publisher, controller.grant = held.write, grant
        controller.publish("campaign_grant.json", canonical(grant))
        controller.publish("before_credential.json", canonical({"timestamp_utc": stamp(), "count_calls": 0, "inherited_operations": sorted(controller.budget.consumed),
            "inherited_reserved_cost_usd": str(controller.budget.reserved), "remaining_operations_max": 12}))
        saved_root = BASE.PRIVATE / ("saved-" + reservation.name)
        saved = build_saved_application(saved_root, create=True, source=p0.saved_source)
        try:
            generation.armed = True
            results = [one_case(controller, generation, review, endpoint, saved, "M01", preparations["M01"])]
            controller.key = BASE.masked_key()
            for sid in (f"M{i:02}" for i in range(2, 8)):
                results.append(one_case(controller, generation, review, endpoint, saved, sid, preparations[sid]))
            target.validate()
            summary = {"baseline": BASELINE, "campaign": CAMPAIGN, "state": "AUTHORIZED_PROVIDER_ATTEMPTS_COMPLETED_WITH_EXPLICIT_REVIEW_DISPOSITIONS",
                "timestamp_utc": stamp(), "count_calls": 0, "create_calls": 7, "review_calls": 7, "retry": 0, "fallback": "NONE",
                "reserved_cost_usd": str(controller.budget.reserved), "maximum_campaign_usd": "1.960000", "saved_root": str(saved_root),
                "results": results, "receipts": controller.receipts, "local_corrections": "ONLY_CANONICALLY_MATERIALIZED_REQUIRED_REVIEWS",
                "pedagogical_acceptance": "NOT_PERFORMED", "promotion": "NOT_PERFORMED"}
            controller.publish("campaign_completed.json", canonical(summary))
            (PROOF / "LIVE_RESULT_MINIMIZED.json").write_bytes(canonical({k: v for k, v in summary.items() if k not in {"results", "receipts"}}))
            print("PHASE FOURNISSEUR TERMINÉE ; refus locaux conservés ; COUNT=0 ; aucun autre appel.", flush=True)
            BASE.local_phase(controller, generation, p0, endpoint, target, saved, summary)
        except BaseException as error:  # noqa: BLE001 -- never expose credential-bearing errors
            symbolic = str(error) if re.fullmatch(r"[A-Z0-9_]{1,90}", str(error)) else type(error).__name__
            stopped = {"state": "STOP_NO_RETRY", "timestamp_utc": stamp(), "error_code": symbolic, "consumed_operations": sorted(controller.budget.consumed),
                "reserved_cost_usd": str(controller.budget.reserved), "count_calls": 0, "retry": 0, "fallback": "NONE"}
            controller.publish("campaign_stopped.json", canonical(stopped))
            (PROOF / "LIVE_RESULT_MINIMIZED.json").write_bytes(canonical(stopped))
            print("STOP : " + symbolic + " ; preuves conservées, aucun retry.", flush=True)
            return 1
        finally:
            generation.armed = False
            controller.key = ""
    return 0


if __name__ == "__main__":
    try:
        status = main()
    except BaseException as error:  # noqa: BLE001 -- redact all exception details
        symbolic = str(error) if re.fullmatch(r"[A-Z0-9_]{1,90}", str(error)) else type(error).__name__
        print("STOP avant exécution : " + symbolic, flush=True)
        status = 2
    if "--native-live" in sys.argv and sys.stdin.isatty():
        input("Appuyez sur Entrée pour fermer. ")
    raise SystemExit(status)
