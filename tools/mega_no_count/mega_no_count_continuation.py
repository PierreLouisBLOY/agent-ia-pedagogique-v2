"""One protected continuation: recover received M01 locally, never CREATE M01 again.

The application source and approved provider bodies remain exact d7bae43.
Only technical identifier casing is adapted, with explicit mapping evidence.
Parent reservation/evidence remain immutable; their pessimistic charge is inherited.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from secrets import token_hex
from typing import Any

import mega_no_count_runner as base
from mega_content_ids import bind_candidate_status, normalize_ids
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
    unique,
)
from mega_retained_inputs import RetainedInputs

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
)
from backend.infrastructure.composition.factories.conversation import r2_request_parameters
from backend.infrastructure.composition.factories.local_browser import build_saved_application

PARENT_SHA = "7508566cfe0f767e56db4b86564d05d389832a468322371075dfbb154828cc94"
PARENT = base.PRIVATE / PARENT_SHA
PROOF = ARTIFACT / "B_M01_LOCAL_RECOVERY_20261004" / "QUALIFIED_V2"
ORIGINAL_CHECK = base.grant_check


def parent_evidence(pins: dict[str, str] | None = None) -> tuple[dict[str, Any], str, dict[str, str]]:
    actual = {p.name: sha(p.read_bytes()) for p in PARENT.iterdir() if p.is_file()}
    if pins is not None and actual != pins:
        raise ValueError("PARENT_EVIDENCE_CHANGED")
    grant_raw = (PARENT / "campaign_grant.json").read_bytes()
    if sha(grant_raw) != PARENT_SHA:
        raise ValueError("PARENT_GRANT_CHANGED")
    grant = json.loads(grant_raw)
    receipt = json.loads((PARENT / "M01_CREATE_receipt.json").read_bytes())
    proof_raw = (PARENT / "M01_CREATE_preflight.json").read_bytes()
    proof = json.loads(proof_raw)
    stopped = json.loads((PARENT / "campaign_stopped.json").read_bytes())
    if (stopped["consumed_operations"] != [["M01", "CREATE"]]
        or stopped["count_calls"] != 0 or stopped["retry"] != 0
        or receipt["baseline"] != BASELINE or receipt["campaign"] != CAMPAIGN
        or receipt["authorization_sha256"] != PARENT_SHA or receipt["reservation_namespace_sha256"] != PARENT_SHA
        or receipt["scenario"] != "M01" or receipt["operation"] != "CREATE"
        or receipt["http_status"] != 200 or receipt["response_status"] != "completed"
        or receipt["provider_attempts"] != 1 or receipt["count_calls"] != 0 or receipt["retry"] != 0
        or receipt["fallback"] != "NONE" or receipt["financial_preflight_sha256"] != sha(proof_raw)):
        raise ValueError("PARENT_CONFIRMED_SINGLE_CREATE_REQUIRED")
    scope = grant["scopes"][0]
    if receipt["scope_sha256"] != scope["scope_sha256"]:
        raise ValueError("PARENT_SCOPE_CHANGED")
    for kind in ("request", "response", "output"):
        if sha((PARENT / ("M01_CREATE_" + kind + ".json")).read_bytes()) != receipt[kind + "_sha256"]:
            raise ValueError("PARENT_RECEIPT_HASH_CHANGED")
    if receipt["request_sha256"] != scope["generation_sha256"] or proof["request_sha256"] != receipt["request_sha256"]:
        raise ValueError("PARENT_REQUEST_CHANGED")
    if not (receipt["reserved_cost_usd"] == proof["max_cost_usd"] == receipt["campaign_reserved_cost_usd"] == stopped["reserved_cost_usd"]):
        raise ValueError("PARENT_FINANCIAL_RESERVATION_CHANGED")
    response = json.loads((PARENT / "M01_CREATE_response.json").read_bytes())
    text = (PARENT / "M01_CREATE_output.json").read_text("utf-8")
    messages = [part["text"] for item in response["output"] if item["type"] == "message" for part in item["content"] if part["type"] == "output_text"]
    if ("".join(messages) != text or response["usage"] != receipt["usage"]
        or response["model"] != grant["model"] or response["status"] != "completed"):
        raise ValueError("PARENT_RESPONSE_LINK_CHANGED")
    return receipt, text, actual


def continuation_check() -> dict[str, Any]:
    grant = ORIGINAL_CHECK()
    if grant["parent_authorization_sha256"] != PARENT_SHA:
        raise ValueError("CONTINUATION_PARENT_CHANGED")
    parent = json.loads((PARENT / "campaign_grant.json").read_bytes())
    if grant["issued_at"] != parent["issued_at"] or grant["expires_at"] != parent["expires_at"]:
        raise ValueError("CONTINUATION_DURATION_WAS_NOT_RENEWED")
    remaining = [[f"M{i:02}", op] for i in range(1, 8) for op in ("CREATE", "REVIEW") if (i, op) != (1, "CREATE")]
    if grant["remaining_operations"] != remaining:
        raise ValueError("CONTINUATION_OPERATIONS_CHANGED")
    receipt, _, _ = parent_evidence(grant["parent_artifact_sha256"])
    if receipt["reserved_cost_usd"] != grant["inherited_reserved_cost_usd"]:
        raise ValueError("CONTINUATION_INHERITED_BUDGET_CHANGED")
    return grant


class Controller(base.Controller):
    def __init__(self, proposal: dict[str, Any]) -> None:
        super().__init__(proposal)
        receipt, self.recovered_text, _ = parent_evidence()
        self.budget.reserve("M01", "CREATE", {"max_cost_usd": receipt["reserved_cost_usd"]})
        self.budget.finish("M01", "CREATE", confirmed=True)
        self.receipts.append(receipt)
        self.recovered = False

    def send(self, sid: str, operation: str, raw: bytes, expected: str | None) -> tuple[dict[str, Any], str]:
        if (sid, operation) == ("M01", "CREATE"):
            raise ValueError("M01_CREATE_ALREADY_CONSUMED_NO_PROVIDER_REPLAY")
        return super().send(sid, operation, raw, expected)


class Generation(base.Generation):
    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        if not self.armed:
            raise ValueError("P0_CAMPAIGN_NOT_ARMED")
        raw = canonical(r2_request_parameters(build_p0_content_request(request)))
        if self.scenario == "M01":
            if self.controller.recovered or sha(raw) != self.controller.receipts[0]["request_sha256"]:
                raise ValueError("M01_RECOVERY_ALREADY_BOUND_OR_SCOPE_CHANGED")
            text = self.controller.recovered_text
            self.controller.recovered = True
            self.controller.publish("M01_REAL_RECEIPT_RECOVERY.json", canonical({"source_receipt_sha256": sha((PARENT / "M01_CREATE_receipt.json").read_bytes()),
                "parent_namespace_sha256": PARENT_SHA, "provider_calls_this_recovery": 0,
                "historical_provider_attempts": 1, "request_sha256": sha(raw), "original_output_sha256": sha(text.encode()),
                "mode": "REAL_CONFIRMED_RESPONSE_RECOVERY_NOT_SYNTHETIC_TRANSPORT"}))
        else:
            _, text = self.controller.send(self.scenario, "CREATE", raw, self.controller.scopes[self.scenario]["generation_sha256"])
        content, mapping = normalize_ids(json.loads(text, object_pairs_hook=unique))
        content, status_annotation = bind_candidate_status(content)
        production = bind_p0_content(request, content)
        self.controller.publish(self.scenario + "_ID_CASE_MAPPING.json", canonical({"original_output_sha256": sha(text.encode()),
            "normalized_content_sha256": sha(canonical(content)), "mapping": mapping,
            "scope": "TECHNICAL_IDENTIFIERS_AND_EXPLICIT_LOCAL_CANDIDATE_STATUS", "subject_answer_marking_changes": 0,
            "local_status_annotation": status_annotation, "status_annotation_provenance": "LOCAL_APPLICATION_LIFECYCLE_NOT_PROVIDER_CONTENT",
            "canonical_contract": "UNCHANGED", "provider_calls_for_normalization": 0}))
        self.controller.publish(self.scenario + "_structured_content.json", canonical(content))
        return production.mutable_copy()


def install() -> None:
    base.PROOF = PROOF
    # Explicit pilot composition; the pinned historical module stays byte-identical.
    base.__dict__.update({"Controller": Controller, "Generation": Generation})
    base.grant_check = continuation_check


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-live", action="store_true")
    args = parser.parse_args()
    install()
    proposal = base.sources()
    controller, generation, review, p0, endpoint, preparations, target = base.prepare(proposal)
    grant = continuation_check()
    tariff = json.loads((ROOT / "MEGA_TOKENIZER_ACQUISITION_20261004/03_CURRENT_OFFICIAL_TARIFF.json").read_text())
    proofs = [{"scenario_id": sid, **preflight(raw, tariff, expected_sha=controller.scopes[sid]["generation_sha256"])}
              for sid, raw in generation.captured.items()]
    if not args.native_live:
        evidence = {}
        controller.publisher = lambda name, raw: evidence.update({name: json.loads(raw)})
        generation.armed = True
        generation.scenario = "M01"
        ready = preparations["M01"]
        recovered = base.p0_call(endpoint, "generate", {"command_id": token_hex(16), "preparation_ref": ready["preparation_ref"], "preparation_sha256": ready["preparation_sha256"]})
        generation.armed = False
        target.validate()
        report = {"state": "REAL_M01_APPLICATION_RECOVERY_PASS_EXECUTED", "provider_calls_this_run": 0,
            "credentials_resolved": 0, "parent_namespace_sha256": PARENT_SHA, "evidence": evidence,
            "application_result": recovered, "inherited_reserved_cost_usd": str(controller.budget.reserved), "preflights": proofs}
        (PROOF / "01_OFFLINE_RECOVERY_PROOF.json").write_bytes(canonical(report))
        print("REAL_M01_APPLICATION_RECOVERY_PASS; NEW_PROVIDER=0; COUNT=0")
        return 0
    reservation = base.PRIVATE / sha((PROOF / "CURRENT_GRANT.json").read_bytes())
    pins = [ROOT / name for name in grant["code_pins"]]
    pins += [PROOF / "CURRENT_GRANT.json", PROOF / "CURRENT_GRANT.sha256", ARTIFACT / "A6_OWNER_LIVE_GATE.json"]
    pins += [PARENT / name for name in grant["parent_artifact_sha256"]]
    pins += list((ARTIFACT / "live-payloads").glob("*_GENERATE.json")) + list(base.SOURCE.rglob("*.py"))
    helper = ROOT / "MEGA_TOKENIZER_ACQUISITION_20261004"
    pins += [helper / "01_ACQUISITION_MANIFEST.json", helper / "02_HELPER_INPUT_MANIFEST.json", helper / "o200k_base.tiktoken"]
    pins += list((helper / "encoding-cache").iterdir())
    pins += [p for p in (helper / "venv/Lib/site-packages").rglob("*") if p.is_file() and p.suffix in {".py", ".pyd"}]
    with RetainedInputs(ROOT, pins), Reservation(reservation, base.PRIVATE, directory_identity(base.PRIVATE)) as held:
        if continuation_check() != grant:
            raise ValueError("CONTINUATION_GRANT_SUBSTITUTED")
        controller.publisher, controller.grant = held.write, grant
        controller.publish("campaign_grant.json", canonical(grant))
        controller.publish("before_credential.json", canonical({"state": "CONTINUATION_NAMESPACE_CONSUMED", "timestamp_utc": stamp(),
            "parent_namespace_sha256": PARENT_SHA, "historical_provider_attempts": 1, "remaining_provider_attempts_max": 13, "count_calls": 0, "preflights": proofs}))
        saved_root = base.PRIVATE / ("saved-" + reservation.name)
        saved = build_saved_application(saved_root, create=True, source=p0.saved_source)
        try:
            generation.armed = True
            results = []
            # M01 is recovered and contract-validated BEFORE asking for a credential.
            for sid, ready in preparations.items():
                generation.scenario = review.scenario = sid
                if sid != "M01" and not controller.key:
                    raise ValueError("CAMPAIGN_KEY_ABSENT")
                produced = base.p0_call(endpoint, "generate", {"command_id": token_hex(16), "preparation_ref": ready["preparation_ref"], "preparation_sha256": ready["preparation_sha256"]})
                controller.publish(sid + "_application_generation.json", canonical(produced))
                if sid == "M01":
                    controller.key = base.masked_key()
                view = produced["view"]
                identity = {k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")}
                reviewed = base.p0_call(endpoint, "review", {"command_id": token_hex(16), **identity})
                controller.publish(sid + "_application_review.json", canonical(reviewed))
                saved_receipt = saved.execute("save", body={k: identity[k] for k in ("production_ref", "version_ref")}, correlation="mega.continuation.save")
                controller.publish(sid + "_saved_receipt.json", canonical(saved_receipt))
                results.append({"scenario_id": sid, "production": identity, "generation": "CONFIRMED", "review": reviewed["state"],
                    "review_sha256": reviewed["review_sha256"], "saved": saved_receipt})
            target.validate()
            summary = {"baseline": BASELINE, "campaign": CAMPAIGN, "state": "AUTHORIZED_PROVIDER_PHASE_COMPLETED", "timestamp_utc": stamp(),
                "parent_namespace_sha256": PARENT_SHA, "count_calls": 0, "create_calls": 7, "review_calls": 7, "retry": 0, "fallback": "NONE",
                "reserved_cost_usd": str(controller.budget.reserved), "maximum_campaign_usd": "1.960000", "saved_root": str(saved_root),
                "results": results, "receipts": controller.receipts, "local_corrections": "NOT_YET_EVALUATED", "pedagogical_acceptance": "NOT_PERFORMED", "promotion": "NOT_PERFORMED"}
            controller.publish("campaign_completed.json", canonical(summary))
            (PROOF / "LIVE_RESULT_MINIMIZED.json").write_bytes(canonical({k: v for k, v in summary.items() if k not in {"results", "receipts"}}))
            print("PHASE_B_PROVIDER_COMPLETED — aucun autre appel autorisé.", flush=True)
            base.local_phase(controller, generation, p0, endpoint, target, saved, summary)
        except BaseException as error:  # noqa: BLE001 -- redact credential-bearing exception text
            symbolic = str(error) if re.fullmatch(r"[A-Z0-9_]{1,90}", str(error)) else type(error).__name__
            stopped = {"state": "STOP_NO_RETRY", "timestamp_utc": stamp(), "error_code": symbolic,
                "parent_namespace_sha256": PARENT_SHA, "consumed_operations": sorted(controller.budget.consumed),
                "reserved_cost_usd": str(controller.budget.reserved), "count_calls": 0, "retry": 0, "fallback": "NONE"}
            controller.publish("campaign_stopped.json", canonical(stopped))
            (PROOF / "LIVE_RESULT_MINIMIZED.json").write_bytes(canonical(stopped))
            print("STOP : " + symbolic + " ; preuves conservées, aucune relance.", flush=True)
            return 1
        finally:
            generation.armed = False
            controller.key = ""
    return 0


if __name__ == "__main__":
    try:
        status = main()
    except BaseException as error:  # noqa: BLE001 -- redact all credential-bearing exception text
        symbolic = str(error) if re.fullmatch(r"[A-Z0-9_]{1,90}", str(error)) else type(error).__name__
        print("STOP avant exécution : " + symbolic + " ; aucune relance.", flush=True)
        status = 2
    if "--native-live" in sys.argv and sys.stdin.isatty():
        input("Appuyez sur Entrée pour fermer. ")
    raise SystemExit(status)
