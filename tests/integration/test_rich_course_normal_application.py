"""Normal rich COURSE Application lifecycle over declared synthetic provider output."""

import io
import json
import threading
import zipfile
from secrets import token_hex

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.api.read15 import Read15Endpoint
from backend.adapters.inbound.api.saved_production import SavedProductionEndpoint
from backend.adapters.inbound.api.server import LocalRead15Server, LocalRead15Service
from backend.infrastructure.composition.factories.local_browser import (
    bind_confirmed_p0_publication,
    build_saved_application,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.integration.test_r4_local_http import available_port, request
from tests.unit.test_course_notion_contract import notion_content, notion_synthetic_configuration
from tests.unit.test_integrated_saved_p0_resume import resume_with
from tests.unit.test_local_browser_http_contract import RecordingObservability
from tests.unit.test_p0_agentic_routing import identity
from tests.unit.test_p0_rich_course_content import rich_content, rich_synthetic_configuration


def xml_parts(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert not any("vbaProject" in name for name in archive.namelist())
        parts = [
            archive.read(name) for name in archive.namelist() if name.endswith((".xml", ".rels"))
        ]
        assert not any(b'TargetMode="External"' in part for part in parts)
        return b"\n".join(parts)


@pytest.mark.parametrize("configuration,content_factory", [(rich_synthetic_configuration, rich_content),
                                                         (notion_synthetic_configuration, notion_content)])
def test_rich_normal_receive_save_restart_export_and_local_revision(tmp_path, configuration, content_factory):
    _, service, prepared, dispatch, resolver, transport = configuration(tmp_path)
    supplied_content = content_factory(dispatch)
    library_root = tmp_path / "synthetic-course-library"
    library = build_saved_application(
        library_root, create=True, source=service.saved_source, word_profile="product-v7"
    )
    service.saved_reader = library.read_local_p0
    bind_confirmed_p0_publication(service, library, service.generation)
    result = service.execute(
        "generate",
        {
            "command_id": token_hex(16),
            "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"],
        },
    )
    assert result["state"] == "CANDIDATE"
    assert result["publication"]["state"] == "APPLICATION_SAVED"
    assert resolver.calls == transport.build_calls == transport.calls == 1
    view = result["view"]
    parent = service.saved_source(view["production_ref"], view["version_ref"])
    chapter = as_plain(parent.p0_bundle.data["course_chapter"])
    for field, value in supplied_content["course_chapter"].items():
        if field not in {"documents", "concepts"}:
            assert chapter[field] == value
    for provided, received in zip(supplied_content["course_chapter"]["concepts"], chapter["concepts"], strict=True):
        assert {k: v for k, v in provided.items() if k not in {"notion_id", "notion"}} == {
            k: v for k, v in received.items() if k != "notion"}
    assert chapter["chapter_number"] == 7
    assert parent.p0_bundle.data["questions"] == parent.p0_bundle.data["corrections"] == ()
    assert parent.p0_bundle.data["context"]["course_format"] == "CHAPTER"

    restarted = build_saved_application(library_root, word_profile="product-v7")
    reopened_parent = restarted.read_local_p0(parent.production_ref, parent.version_ref)
    assert reopened_parent.sha256 == parent.sha256
    reopened = resume_with({parent.version_ref: reopened_parent})
    assert reopened.read(parent.production_ref, parent.version_ref) == view
    for public in ("student", "correction"):
        raw = restarted.execute(
            "word",
            parent.production_ref,
            parent.version_ref,
            kind=public,
            correlation="synthetic.rich.normal.export",
        )
        parts = xml_parts(raw)
        assert (b"SENTINELLE_PROFESSEUR" in parts) == (public == "correction")
        assert b"Situation construite" in parts
        assert dispatch["references"][0]["evidence_id"].encode() not in parts
        assert raw == restarted.execute(
            "word",
            parent.production_ref,
            parent.version_ref,
            kind=public,
            correlation="synthetic.rich.export.repeat",
        )

    changed = reopened.execute(
        "revise",
        {
            "command_id": token_hex(16),
            **identity(view),
            "edits": {
                "title": "Chapitre riche modifié localement",
                "course_edits": {
                    "context": {
                        "text": "Situation construite : observer une répartition des rôles."
                    }
                },
            },
        },
    )
    assert changed["provider_attempts"] == 0
    child = reopened.saved_source(parent.production_ref, changed["view"]["version_ref"])
    assert (
        child.p0_bundle.data["course_chapter"]["teacher_answers"]
        == parent.p0_bundle.data["course_chapter"]["teacher_answers"]
    )
    assert (
        child.p0_bundle.data["course_chapter"]["program_header"]
        == parent.p0_bundle.data["course_chapter"]["program_header"]
    )
    child_writer = build_saved_application(
        library_root, source=reopened.saved_source, word_profile="product-v7"
    )
    child_writer.execute(
        "save",
        body={"production_ref": child.production_ref, "version_ref": child.version_ref},
        correlation="synthetic.rich.child.save",
    )
    again = build_saved_application(library_root, word_profile="product-v7")
    assert again.read_local_p0(child.production_ref, child.version_ref).sha256 == child.sha256
    assert again.read_local_p0(parent.production_ref, parent.version_ref).sha256 == parent.sha256
    assert transport.calls == resolver.calls == 1


@pytest.mark.parametrize("configuration", [rich_synthetic_configuration, notion_synthetic_configuration])
def test_rich_http_generate_save_fresh_server_open_and_export(tmp_path, configuration):
    _, application, prepared, _, resolver, transport = configuration(tmp_path)
    root = tmp_path / "rich-http-library"
    library = build_saved_application(
        root, create=True, source=application.saved_source, word_profile="product-v7"
    )
    application.saved_reader = library.read_local_p0
    bind_confirmed_p0_publication(application, library, application.generation)

    def forbidden(*args, **kwargs):
        raise AssertionError("NO_SQL_OR_UNBOUND_BUSINESS_ACCESS")

    nonce = "synthetic-rich-http"
    port = available_port()
    endpoint = P0CreationEndpoint(
        application.execute, application.read, [], nonce=nonce, generation_bound=True
    )
    server = LocalRead15Server(
        LocalRead15Service(
            LocalBrowserHttpConfiguration(port=port),
            Read15Endpoint(forbidden),
            RecordingObservability(),
            {"index.html": b"", "app.js": b"", "styles.css": b""},
            p0_endpoint=endpoint,
            saved_endpoint=SavedProductionEndpoint(library.execute, nonce=nonce),
        )
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        command = {
            "command_id": token_hex(16),
            "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"],
        }
        assert request(port, "POST", "/api/v2/p0/generate", body=command)[0] == 403
        assert resolver.calls == transport.calls == 0
        status, _, raw = request(port, "POST", "/api/v2/p0/generate", body=command, nonce=nonce)
        assert status == 200, raw
        result = json.loads(raw)["data"]
        assert result["publication"]["state"] == "APPLICATION_SAVED"
        view = result["view"]
    finally:
        server.stop()
        worker.join(5)
        assert not worker.is_alive()

    restarted = build_saved_application(root, word_profile="product-v7")
    port = available_port()
    server = LocalRead15Server(
        LocalRead15Service(
            LocalBrowserHttpConfiguration(port=port),
            Read15Endpoint(forbidden),
            RecordingObservability(),
            {"index.html": b"", "app.js": b"", "styles.css": b""},
            saved_endpoint=SavedProductionEndpoint(restarted.execute, nonce=nonce),
        )
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"/api/v2/productions/{view['production_ref']}/versions/{view['version_ref']}"
    try:
        status, _, raw = request(port, "GET", base + "/saved")
        assert status == 200, raw
        assert json.loads(raw)["data"]["record"]["view"]["bundle_sha256"] == view["bundle_sha256"]
        for public in ("student", "correction"):
            status, media, raw = request(port, "GET", base + "/word/" + public)
            assert status == 200 and media.endswith("wordprocessingml.document")
            assert (b"SENTINELLE_PROFESSEUR" in xml_parts(raw)) == (public == "correction")
    finally:
        server.stop()
        worker.join(5)
        assert not worker.is_alive()
    assert resolver.calls == transport.calls == 1
