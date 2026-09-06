from pathlib import Path

from tests.architecture.test_local_browser_product_boundary import frontend_violations

ROOT = Path(__file__).resolve().parents[2]


def test_r3_ui_has_explicit_version_actions_and_no_implicit_post_retry():
    source = (ROOT / "frontend/app.js").read_text("utf-8")
    html = (ROOT / "frontend/index.html").read_text("utf-8")
    assert source.startswith('"use strict";')
    assert frontend_violations(ROOT) == []
    for name in ("load", "prepare", "review", "validate", "modify", "version", "identities"):
        assert 'id="r3-' + name + '"' in html
    for required in ("REVIEW_NOT_RUN", "base_version_ref", "base_bundle_sha256",
                     "subject_sha256", "r3Uncertain", "crypto.randomUUID()", "90000"):
        assert required in source
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "innerHTML",
                      "console.", "document.cookie", "sendBeacon"):
        assert forbidden not in source
    command = source[source.index("async function r3Command"):]
    assert command.count('r3Fetch("/api/v2/conversation/" + operation, body)') == 1
    assert 'r3Fetch("/api/v2/conversation/operations/" + result.operation_ref)' in command
    assert "NON VALIDÉE" in source
    reader = source[source.index("async function showR3"):source.index('document.getElementById("r3-load")')]
    assert "sequence !== r3ReadSequence" in reader
    assert reader.index("sequence !== r3ReadSequence") < reader.index("r3State = data")
    assert reader.index("await conversationFetch(base)") < reader.index("r3Content.replaceChildren()")
    assert reader.count("await ") == 2
