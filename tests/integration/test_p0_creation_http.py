"""24 real HTTP/Application lifecycles; the only double is the external dispatch."""
import json
import os
import threading
from pathlib import Path
from secrets import token_hex

import pytest

from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    build_local_read15,
    build_local_saved,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from tests.integration.test_r4_local_http import available_port, request
from tests.integration.test_r6_p0_matrix_application import CELLS, _source_scenario, _text
from tests.support.p0_generation_double import P0GenerationDouble


def context(level, kind, mode):
    return {"contract_id": "R6-P0-CONTEXT-1.0", "resource_type": kind, "question_mode": mode,
        "level": level, "discipline": "gestion et comptabilité", "topics": ["Application locale"],
        "objectives": ["Justifier la méthode"], "difficulty": "STANDARD", "language": "fr",
        "duration_minutes": 60 if kind == "ASSESSMENT" else None,
        "total_points": 20 if kind == "ASSESSMENT" else None}


def start(tmp_path, double):
    configured = os.environ.get("PROJET_V2_CANONICAL_DB")
    assert configured, "P0_REAL_SOURCE_PRECONDITION_REQUIRED"
    seed = Path(configured)
    target = Read15RuntimeTarget(seed, seed.parent,
        "9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1")
    port = available_port()
    app = build_local_read15(LocalBrowserHttpConfiguration(port), target, saved_root=tmp_path / "saved",
                            create_saved=True, p0_generation=double, observability_root=tmp_path)
    thread = threading.Thread(target=app.serve_forever)
    thread.start()
    return app, thread, port


def call(port, operation, body=None, nonce=None):
    status, _, raw = request(port, "POST" if body else "GET", "/api/v2/p0" + operation,
                            body=body, nonce=nonce)
    envelope = json.loads(raw)
    assert status == 200, envelope
    assert envelope["meta"]["contract_id"] == "R6-P0-HTTP-LOCAL-1.0"
    return envelope["data"]


def prepare(port, ctx, scenario="R6-S06"):
    meta = call(port, "")
    binding = next(b for b in meta["references"] if scenario in b["scenarios"])
    nonce = meta["transport_nonce"]
    body = {"command_id": token_hex(16), "context": ctx, "reference": {
        key: binding[key] for key in ("resource_ref", "resource_version_ref")}}
    prepared = call(port, "/prepare", body, nonce)
    assert prepared["state"] == "PREPARATION_READY"
    assert prepared["provider_attempts"] == 0 and prepared["context"] == ctx
    return prepared, nonce


@pytest.mark.parametrize("index,level,kind,mode", CELLS, ids=[f"matrix_{c[0]:02d}" for c in CELLS])
def test_http_p0_matrix_create_revise_save_restart_export(tmp_path, index, level, kind, mode):
    double = P0GenerationDouble()
    app, thread, port = start(tmp_path, double)
    try:
        prepared, nonce = prepare(port, context(level, kind, mode), _source_scenario(level, kind, mode))
        payload = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
                   "preparation_sha256": prepared["preparation_sha256"]}
        result = call(port, "/generate", payload, nonce)
        assert call(port, "/generate", payload, nonce) == result
        assert len(double.requests) == 1
        assert double.requests[0]["context"] == prepared["context"]
        assert double.requests[0]["references"] == prepared["references"]
        view = result["view"]
        assert "TEACHER_ONLY_SENTINEL" not in json.dumps(view)
        assert {"corrections", "marking"}.isdisjoint(view)
        parent_path = "/versions/" + view["production_ref"] + "/" + view["version_ref"]
        assert call(port, parent_path) == view
        teacher = call(port, parent_path + "/teacher")
        assert bool(teacher["corrections"]) == (kind != "COURSE")
        child = call(port, "/revise", {"command_id": token_hex(16), "production_ref": view["production_ref"],
            "version_ref": view["version_ref"], "bundle_sha256": view["bundle_sha256"],
            "edits": {"title": "Titre relu par le harnais", "sections": [dict(view["sections"][0], text="Texte révisé.")]}}, nonce)["view"]
        assert child["lineage"]["parent_version_ref"] == view["version_ref"]
        assert call(port, parent_path) == view
        validation = call(port, "/validate", {"command_id": token_hex(16), "production_ref": child["production_ref"],
            "version_ref": child["version_ref"], "bundle_sha256": child["bundle_sha256"]}, nonce)
        assert validation["status"] == "PASS" and validation["promotion"] == "NOT_PERFORMED"
        r4_nonce = json.loads(request(port, "GET", "/api/v2/conversation/saved")[2])["data"]["transport_nonce"]
        save = {"production_ref": child["production_ref"], "version_ref": child["version_ref"]}
        assert request(port, "POST", "/api/v2/conversation/saved", body=save, nonce=r4_nonce)[0] == 200
        base = f'/api/v2/productions/{child["production_ref"]}/versions/{child["version_ref"]}'
        initial = json.loads(request(port, "GET", base + "/saved")[2])["data"]
    finally:
        app.close()
        thread.join(5)
    port = available_port()
    reopened = build_local_saved(LocalBrowserHttpConfiguration(port), tmp_path / "saved")
    thread = threading.Thread(target=reopened.serve_forever)
    thread.start()
    try:
        assert json.loads(request(port, "GET", base + "/saved")[2])["data"] == initial
        assert initial["active_authority"] == "NONE_RESTORED"
        kinds = ["student"] + ([] if kind == "COURSE" else ["correction"])
        if kind == "ASSESSMENT":
            kinds.append("marking")
        for role in kinds:
            status, _, raw = request(port, "GET", base + "/word/" + role)
            assert status == 200
            text = _text(raw)
            assert ("TEACHER_ONLY_SENTINEL" in text) == (role == "correction")
        assert len(double.requests) == 1
    finally:
        reopened.close()
        thread.join(5)


@pytest.mark.parametrize("mode", ("unbound", "refused", "failed"))
def test_no_authority_refusal_and_unknown_dispatch_never_retry(tmp_path, mode):
    double = None if mode == "unbound" else P0GenerationDouble(allowed=mode != "refused", failure=mode == "failed")
    app, thread, port = start(tmp_path, double)
    try:
        prepared, nonce = prepare(port, context("BTS_CG_YEAR_2", "ASSESSMENT", None))
        body = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
                "preparation_sha256": prepared["preparation_sha256"]}
        status, _, raw = request(port, "POST", "/api/v2/p0/generate", nonce=nonce, body=body)
        assert "PRIVATE_TRANSPORT" not in raw.decode()
        if mode == "failed":
            assert status == 409 and json.loads(raw)["error"]["code"] == "P0_OUTCOME_UNKNOWN"
            assert call(port, "/generate", body, nonce)["state"] == "OUTCOME_UNKNOWN"
            assert len(double.requests) == 1
        else:
            assert status == 200 and json.loads(raw)["data"]["state"] == "AUTHORIZATION_REQUIRED"
            assert double is None or not double.requests
        assert request(port, "POST", "/api/v2/p0/generate", body=body)[0] == 403
        assert request(port, "POST", "/api/v2/p0/generate", body=body, nonce=nonce, origin="http://foreign.invalid")[0] == 403
        assert request(port, "GET", "/api/v2/p0?latest=true")[0] != 200
    finally:
        app.close()
        thread.join(5)
