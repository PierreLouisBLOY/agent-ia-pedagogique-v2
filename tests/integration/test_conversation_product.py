import time

from tests.support.conversation_fakes import (
    PILOT,
    http_call,
    http_command,
    process_job,
    running_conversation,
    wait_terminal,
)


def test_complete_synthetic_http_process_agents_candidate_and_r3_refusal(tmp_path):
    job = process_job(tmp_path / "worker")
    with running_conversation(tmp_path / "http", jobs=job) as (composition, target):
        (_, _, data), _ = http_command(composition, 1, text=PILOT)
        assert data["data"]["missing_fields"] == ["level", "discipline", "objectives", "difficulty"]
        (_, _, data), _ = http_command(composition, 2, text="BTS CG deuxième année ; analyse financière ; identifier les emplois et ressources stables, calculer le FRNG et le BFR, interpréter la trésorerie nette ; difficulté standard.")
        assert data["data"]["missing_fields"] == []
        assert data["data"]["context"]["values"]["topics"] == ["bilan fonctionnel", "BFR"]
        (status, _, data), _ = http_command(composition, 3, text="Je confirme", confirm_context=True)
        assert status == 200
        started = time.monotonic()
        (status, _, accepted), body = http_command(composition, 4, operation="generations",
                            confirmed_context_sha256=data["data"]["confirmed_context_sha256"])
        assert status == 202 and time.monotonic() - started < 2
        assert http_call(composition, "/api/v2/conversation/generations", body=body)[2]["data"] == accepted["data"]
        view = wait_terminal(composition)
        assert view["active_generation"]["state"] == "CANDIDATE_READY"
        refs = view["current_candidate"]
        route = "/api/v2/productions/" + refs["production_ref"] + "/versions/" + refs["version_ref"]
        status, _, first = http_call(composition, route)
        assert status == 200 and first["data"]["validation_state"] == "CANDIDATE"
        assert first["data"] == http_call(composition, route)[2]["data"]
        assert len(first["data"]["sections"]) == 5
        assert sum(ref["declared_used"] for ref in first["data"]["references"]) == 1
        (status, _, data), _ = http_command(composition, 5, text="Modifie le dossier 3")
        assert status == 200 and data["data"]["messages"][-1]["response_kind"] == "OUT_OF_SCOPE"
        assert data["data"]["current_candidate"] == refs
        # Reading the library remains an independent application operation.
        assert http_call(composition, "/api/v2/search?q=bilan&limit=10")[0] == 200
        assert http_call(composition, "/api/v2/resources/resource:r2.synth.bilan")[0] == 200
        assert target.runtime_path.read_bytes()
    logs = "".join(p.read_text("utf-8") for p in (target.data_root / "logs").glob("*.ndjson"))
    for private in (PILOT, "Atelier Horizon", "r2.synth.bilan", str(target.runtime_path), "transport_nonce"):
        assert private not in logs
    assert job._child.poll() is not None
