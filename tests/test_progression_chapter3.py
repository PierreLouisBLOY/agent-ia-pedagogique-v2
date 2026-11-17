"""Check the normal manual launcher with a synthetic supplier."""
from secrets import token_hex

from tests import normal_on_323a_fixture as f
from tests.test_manual_provider_tests import Control, running
from tests.test_normal_on_323a import call, terminal, text
from tests.unit.test_progressive_chapter3 import PARTS, TASKS, replay, selection


def test_chapter_three_manual_http_saved_reopens_and_both_words(tmp_path, monkeypatch):
    class WireCheck(Control):
        def create(self, *, request):
            schema = request.output_schema["properties"]["course_chapter"]["properties"]
            assert schema["transfer"]["minItems"] == schema["transfer"]["maxItems"] == 2
            assert schema["parts"]["items"]["properties"]["document_ids"]["maxItems"] == 2
            assert "formalization" in request.instructions
            return super().create(request=request)

    control = WireCheck()
    root = tmp_path / "chapter3"
    with running(root, monkeypatch, control) as (port, config):
        nonce = call(port, "GET", "/api/v2/p0")[1]["data"]["transport_nonce"]
        status, prep = call(port, "POST", "/api/v2/p0/prepare", {"command_id": token_hex(16),
            "context": selection(), "reference": {"notion_id": "notion:shared", "passage_ref": f.SOURCE["passage_ref"]}}, nonce)
        assert status == 200, prep
        cmd = {"command_id": token_hex(16), **{k: prep["data"][k] for k in ("preparation_ref", "preparation_sha256")}}
        monkeypatch.setattr(f, "CONTENT", replay())
        assert call(port, "POST", "/api/v2/p0/generate", cmd, nonce)[0] == 202
        done = terminal(port, cmd["command_id"])
        assert done["state"] == "LOCAL_COMMAND_COMPLETED", done
        view = done["result"]["view"]
        path = "/api/v2/productions/"+view["production_ref"]+"/versions/"+view["version_ref"]
        assert control.calls == 1
    fresh = Control()
    with running(root, monkeypatch, fresh, existing=config) as (port, _):
        status, opened = call(port, "GET", path+"/saved")
        assert status == 200
        sections = opened["data"]["record"]["bundle"]["sections"]
        assert [s["heading"] for s in sections][2:] == [p[0] for p in PARTS]+["À retenir", "Tester ses connaissances", *TASKS]
        for kind in ("student", "correction"):
            status, data = f.request(port, "GET", path+"/word/"+kind)
            assert status == 200
            body = text(data)
            markers = ["DAT SECURITY", PARTS[0][0], "Observer la situation 1.", "Notion — "+PARTS[0][1],
                       "Analyser les indices 1.", PARTS[1][0], "Notion — "+PARTS[1][1], "Observer la situation 2.",
                       PARTS[2][0], "Analyser les indices 3.", "Notion — "+PARTS[2][1], "Réinvestir la notion 3.",
                       PARTS[3][0], "À retenir", "Tester ses connaissances", *TASKS]
            positions = [body.index(marker) for marker in markers]
            assert positions == sorted(positions)
            assert ("CORRIGE_PROF_15" in body) == (kind == "correction")
            (tmp_path / f"validation_ch3_{kind}.docx").write_bytes(data)
        assert fresh.calls == 0
