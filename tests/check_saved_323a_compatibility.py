"""Subprocess: the unchanged 323A R4 handlers read/export a synthetic derivative."""

from __future__ import annotations

import io
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

source, root, production, version, expected = sys.argv[1:]
sys.path.insert(0, source)


def denied(*args, **kwargs):
    raise RuntimeError("SYNTHETIC_NETWORK_FORBIDDEN")


socket.socket.connect = denied
def application_bindings():
    from backend.adapters.inbound.api.saved_production import SavedProductionEndpoint
    from backend.infrastructure.composition.factories.local_browser import build_saved_application

    return SavedProductionEndpoint, build_saved_application


SavedProductionEndpoint, build_saved_application = application_bindings()

saved = build_saved_application(Path(root), create=False, word_profile="product-v7")
endpoint = SavedProductionEndpoint(saved.execute, nonce="SYNTHETIC")
status, _, raw = endpoint.respond("open", production, version, "", b"", "synthetic")
assert status == 200
opened = json.loads(raw)["data"]
assert opened["record_sha256"] == expected and opened["status"] == "CANDIDATE"
for kind in ("student", "correction"):
    status, _, raw = endpoint.respond("word", production, version, kind, b"", "synthetic")
    assert status == 200
    with ZipFile(io.BytesIO(raw)) as z:
        xml = ET.fromstring(z.read("word/document.xml"))
    text = "".join(xml.itertext())
    assert ("REPONSE_PROF_323B_" in text) == (kind == "correction")
print(
    json.dumps(
        {
            "status": "OLD_SERVICE_R4_ROUTES_COMPATIBLE",
            "source": source,
            "provider_calls": 0,
            "server_started": False,
        }
    )
)
