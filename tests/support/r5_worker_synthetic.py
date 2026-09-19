"""Artificial sources, grants, receipts and transport. No account or real authority."""
import hashlib
import json
import sqlite3
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.infrastructure.composition.factories.conversation import (
    r2_digest,
    r2_environment_identity,
)
from backend.infrastructure.composition.factories.r5_generation import (
    GRANT_SCHEMA,
    PACKET_SCHEMA,
    prepare_exact_selection,
    scope_from_preparation,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import SECTION_IDS
from tests.integration.test_r5_local_reference import request
from tests.support.conversation_synthetic import PASSAGES, synthetic_target

BASELINE = "f" * 40
FAKE = "SYNTHETIC_PRIVATE_CHANNEL_VALUE_NOT_A_CREDENTIAL"
METHOD = (
    "Convention du cas fictif : ressources stables = capitaux propres + dette financière ; "
    "emplois stables = immobilisations corporelles + incorporelles. FRNG = ressources - emplois. "
    "BFR = stocks + créances clients - dettes fournisseurs - dettes fiscales d'exploitation. "
    "Aucun élément hors exploitation ni retraitement additionnel. TN = FRNG - BFR ; "
    "contrôle TN = trésorerie active - trésorerie passive. Unité kEUR, même date."
)
CASE = (
    "Cas purement fictif, 31 décembre N, kEUR : capitaux propres 150, dette financière 70 ; "
    "immobilisations corporelles 120, incorporelles 60 ; stocks 35, créances clients 50 ; "
    "dettes fournisseurs 40, dettes fiscales d'exploitation 20 ; trésorerie active 18, passive 3. "
    "L'élève doit reconstruire les agrégats à partir de ces composants."
)
SOLUTION = (
    "Solution de fixture : RS=150+70=220 ; ES=120+60=180 ; FRNG=220-180=40 kEUR ; "
    "AC=35+50=85 ; PC=40+20=60 ; BFR=85-60=25 ; TN=40-25=15=18-3 kEUR. "
    "Le financement stable couvre le besoin de cycle et laisse 15 kEUR de trésorerie nette."
)


def fixture(root, *, source_texts=(METHOD, CASE)):
    target = synthetic_target(root)
    with sqlite3.connect(target.runtime_path) as connection:
        for (ref, _), text in zip(PASSAGES, (*source_texts, "Référence de test : vérifier les unités et les agrégats sans double comptage."), strict=True):
            connection.execute("UPDATE search_chunk SET text=?, chunk_hash=? WHERE id=?",
                               (text, hashlib.sha256(text.encode()).hexdigest(), ref))
    target = replace(target, expected_sha256=hashlib.sha256(target.runtime_path.read_bytes()).hexdigest())
    selection = [{"object_ref": "resource:" + ref, "object_kind": "RESOURCE", "passage_ref": ref,
                  "version_or_checksum": hashlib.sha256(text.encode()).hexdigest(),
                  "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
                 for (ref, _), text in zip(PASSAGES[:2], source_texts, strict=True)]
    prepared = prepare_exact_selection(target, request=request(), selection=selection)
    scope = scope_from_preparation(prepared, request=request(), target=target, selection=selection, baseline=BASELINE)
    return target, scope, prepared


def grant_for(scope, receipts):
    now = datetime.now(UTC)
    proof = {"schema": "R5-COUNT-RECEIPT-1.0", "status": "CONFIRMED",
        "scope_sha256": r2_digest(scope), "generation_sha256": scope["generation_sha256"],
        "count_sha256": scope["count_sha256"], "input_tokens": 3000,
        "count_authorization_sha256": "a" * 64, "cost_status": "KNOWN",
        "unknown_cost_explicitly_accepted": False}
    return {"schema": GRANT_SCHEMA, "baseline_commit": BASELINE, "scope_sha256": r2_digest(scope),
        "live_authorized": True, "transfer_authorized": True, "model_profile_approved": True,
        "pricing_approved": True, "provider": "OPENAI_ONLY", "max_calls": 1, "retry": 0,
        "fallback": "NONE", "issued_at": now.isoformat(), "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "ceiling_usd": "0.140000", "token_count_receipt": proof, "count_receipt_sha256": r2_digest(proof),
        "receipt_root_sha256": r2_digest(str(receipts.absolute()).casefold()), "environment": r2_environment_identity()}


def packet_for(target, scope, grant):
    return {"schema": PACKET_SCHEMA, "scope": scope, "grant": grant,
        "runtime_path": str(target.runtime_path), "data_root": str(target.data_root), "secret": FAKE}


class Factory:
    def __init__(self, mode="success"):
        self.mode, self.requests, self.builds = mode, [], 0

    def build(self, *, secret, timeout_seconds):
        assert secret.reveal_for_transport() == FAKE and timeout_seconds == 90
        self.builds += 1
        assert self.builds == 1
        return self

    def create(self, *, request):
        self.requests.append(request)
        assert len(self.requests) == 1
        if self.mode == "timeout":
            time.sleep(30)
        if self.mode == "error":
            raise OpenAITransportError(OpenAITransportErrorCode.CONNECTION)
        ids = json.loads(request.input_json)["evidence_refs"]
        payload = {"outcome": "OUTPUT", "sections": [{"code": code, "text": text} for code, text in zip(
            SECTION_IDS, ("Contrôle fictif 60 minutes /20, aucune production fournisseur.",
                "Reconstruire les grandeurs puis expliquer leur articulation financière.",
                CASE, METHOD, "Calculer RS/ES (4 pts), FRNG (4), BFR (6), TN et interprétation (6)."), strict=True)],
            "warnings": [], "uncertainties": [], "evidence_ids_used": ids}
        if self.mode == "insufficient":
            payload.update(outcome="INSUFFICIENT_EVIDENCE", sections=[], evidence_ids_used=[],
                uncertainties=[{"code": "MISSING_METHOD", "message": "Méthode nécessaire absente."}])
        if self.mode == "unknown-id":
            payload["evidence_ids_used"] = ["unknown"]
        return OpenAIResponsesResponse(status=OpenAIResponseStatus.INCOMPLETE if self.mode == "incomplete"
            else OpenAIResponseStatus.COMPLETED, output_text="{" if self.mode == "invalid" else json.dumps(payload),
            usage=OpenAIResponseUsage(input_tokens=3000, cached_input_tokens=0, cache_write_input_tokens=0,
                output_tokens=1000, total_tokens=4000, reasoning_tokens=100), service_tier="default")


def worker_main():
    import argparse

    from backend.adapters.outbound.system.conversation_job import encode_frame, result_payload
    from backend.infrastructure.composition.bootstrap.conversation_worker import (
        private_pipe,
        read_private_packet,
        read_request,
        run_authorized_generation,
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-read", type=int, required=True)
    parser.add_argument("--private-write", type=int, required=True)
    args = parser.parse_args(sys.argv[2:])
    mode = sys.argv[1]
    with private_pipe(args.private_read, "rb") as source, private_pipe(args.private_write, "wb") as sink:
        packet = read_private_packet(source)
        result = run_authorized_generation(packet, request=read_request(sys.stdin.buffer), sink=sink,
            material=(BASELINE, packet["scope"]), transport_factory=Factory(mode))
        if mode == "disconnect":
            return 1
        sys.stdout.buffer.write(encode_frame(result_payload(result)))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(worker_main())
