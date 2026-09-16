import http.client
import json
import socket
import threading
from io import BytesIO
from zipfile import ZipFile

from backend.infrastructure.composition.factories.local_browser import build_local_saved
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from tests.support.r4_synthetic import record


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(port, method, path, *, nonce=None, body=None, origin=None):
    headers = {"X-Local-Intent": "conversation-v1"}
    if method == "POST":
        headers.update({"Content-Type": "application/json; charset=utf-8", "X-R2-Nonce": nonce or "",
                        "Origin": origin or f"http://127.0.0.1:{port}"})
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        conn.close()


def test_http_save_close_fresh_composition_reopen_preview_word_and_csrf(tmp_path):
    value = record()
    root = tmp_path / "r4"
    port = available_port()
    app = build_local_saved(LocalBrowserHttpConfiguration(port), root, create=True,
                            source=lambda p, v: value if (p, v) == (value.production_ref, value.version_ref) else None)
    thread = threading.Thread(target=app.serve_forever)
    thread.start()
    base = f"/api/v2/productions/{value.production_ref}/versions/{value.version_ref}"
    try:
        status, _, body = request(port, "GET", "/api/v2/conversation/saved")
        assert status == 200
        nonce = json.loads(body)["data"]["transport_nonce"]
        payload = {"production_ref": value.production_ref, "version_ref": value.version_ref}
        assert request(port, "POST", "/api/v2/conversation/saved", body=payload)[0] == 403
        assert request(port, "POST", "/api/v2/conversation/saved", body=payload, nonce=nonce,
                       origin="http://untrusted.invalid")[0] == 403
        assert request(port, "POST", "/api/v2/conversation/saved", body=payload, nonce=nonce)[0] == 200
        initial = json.loads(request(port, "GET", base + "/saved")[2])["data"]
        assert initial["status"] == "CANDIDATE" and initial["new_actions"] == []
    finally:
        app.close()
        thread.join(5)
    port = available_port()
    reopened = build_local_saved(LocalBrowserHttpConfiguration(port), root)
    thread = threading.Thread(target=reopened.serve_forever)
    thread.start()
    try:
        assert json.loads(request(port, "GET", base + "/saved")[2])["data"] == initial
        for kind in ("student", "correction", "marking"):
            assert request(port, "GET", base + "/preview/" + kind)[0] == 200
            status, media, raw = request(port, "GET", base + "/word/" + kind)
            assert status == 200 and media.endswith("wordprocessingml.document")
            with ZipFile(BytesIO(raw)) as archive:
                assert "word/document.xml" in archive.namelist()
        assert request(port, "GET", base + "/word/secret")[0] != 200
        assert request(port, "GET", base + "/saved?latest=true")[0] != 200
    finally:
        reopened.close()
        thread.join(5)
