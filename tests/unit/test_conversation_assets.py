from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_conversation_assets_preserve_read15_search_and_safe_dom():
    html = (ROOT / "frontend/index.html").read_text("utf-8")
    js = (ROOT / "frontend/app.js").read_text("utf-8")
    for identity in ("resource-form", "search-form", "conversation-form", "context-form",
                     "conversation-generate", "production-read", "conversation-stop-wait"):
        assert 'id="' + identity + '"' in html
    for forbidden in ("innerHTML", "localStorage", "sessionStorage", "console.", "history.", "WebSocket", "EventSource"):
        assert forbidden not in js
    assert "textContent" in js and "replaceChildren" in js
    assert "searchSequence" in js and "form.requestSubmit()" in js
    assert "commandUncertain = true" in js and "clearTimeout(pollTimer)" in js
    assert '"X-R2-Nonce": transportNonce' in js
    assert '"X-Local-Intent": "conversation-v1"' in js
    assert "NON VALIDÉE" in html and "Tout est perdu à l’arrêt" in html
    assert "encodeURIComponent(refs.version_ref)" in js
    assert "facturation ne sont pas annulés" in js
