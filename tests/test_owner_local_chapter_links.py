"""Owner-local scope, unchanged native evidence and real CLI with fake effects."""

import copy
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.modules.knowledge_reference.application.queries.owner_local_chapter_links import (
    ReadOwnerLocalChapterLinks,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.pedagogical_design.contracts.dto.program_authority import (
    alignment_axes,
    bounded_institutional_evidence,
    require_supported_claims,
)
from tests import normal_on_323a_fixture as f
from tests.support.progressive_course_fixture import progressive_course_fixture
from tests.test_manual_provider_tests import Control, running
from tests.test_normal_on_323a import call, terminal, text

LINKS = [
    {"notion_ref": "notion:code", "source_wording": "codes"},
    {"notion_ref": "notion:culture-organisationnelle", "source_wording": "cultures"},
    {"notion_ref": "notion:representation", "source_wording": "représentations"},
]


def decision(context, native):
    clean = copy.deepcopy(context)
    clean["institutional_resolution"] = None
    return {
        "schema": "OWNER-LOCAL-CHAPTER-LINKS-1.0",
        "status": "OWNER_ADOPTED",
        "context_sha256": fingerprint(clean),
        "reference_scope_sha256": fingerprint(native["reference_scope"]),
        "native_qualification_sha256": native["qualification_sha256"],
        "native_owner_admission_sha256": native["owner_admission_sha256"],
        "program_version": native["program_version"],
        "question_ref": native["question"]["id"],
        "links": copy.deepcopy(LINKS),
        "owner_statement": "SYNTHETIC owner adoption, not official.",
    }


def native_fixture():
    context = {
        "chapter": "4",
        "institutional": {"notion_refs": [r["notion_ref"] for r in LINKS]},
        "institutional_resolution": None,
    }
    native = {
        "status": "CONTENT_GAP",
        "gaps": ["NOTION_ATTACHMENT_NOT_ADMITTED:" + r["notion_ref"] for r in LINKS],
        "qualification_sha256": "a" * 64,
        "owner_admission_sha256": "b" * 64,
        "program_version": "synthetic:v1",
        "question": {
            "id": "synthetic:q1",
            "official_text": "cultures, normes, codes, rituels et représentations",
        },
        "reference_scope": {"status": "CANONICAL_NOTION_ONLY"},
        "attachments": [],
    }
    return context, native


def test_local_admission_preserves_native_and_never_creates_official_claim():
    context, native = native_fixture()
    before = copy.deepcopy(native)
    admitted = ReadOwnerLocalChapterLinks(decision(context, native)).execute(context, native)
    assert native == before
    assert admitted["status"] == "RESOLVED_ADMITTED" and admitted["gaps"] == []
    assert admitted["native_institutional_resolution"] == native
    assert len(admitted["attachments"]) == 3
    assert all(
        r["disposition"] == "OWNER_LOCAL_ADMITTED" and r["official"] is False
        for r in admitted["attachments"]
    )
    assert alignment_axes(admitted)["institutional_alignment"] == "UNVERIFIED"
    with pytest.raises(ValueError, match="PROGRAM_ALIGNMENT_UNVERIFIED"):
        require_supported_claims("Ce cours est conforme au programme officiel.", admitted)


@pytest.mark.parametrize("change", ["chapter", "proof", "source", "extra_gap", "wording"])
def test_scope_substitution_and_additional_gaps_never_disappear(change):
    context, native = native_fixture()
    query = ReadOwnerLocalChapterLinks(decision(context, native))
    if change == "chapter":
        context["chapter"] = "5"
        assert query.execute(context, native) == native
        return
    if change == "proof":
        native["qualification_sha256"] = "f" * 64
    elif change == "source":
        native["reference_scope"] = {"status": "OTHER"}
    elif change == "extra_gap":
        native["gaps"].append("PROGRAMME_PROVENANCE_NOT_ADMITTED")
    else:
        native["question"]["official_text"] = "words not present"
    with pytest.raises(ValueError):
        query.execute(context, native)


def test_real_cli_prepares_generates_saves_and_exports_local_chapter(tmp_path, monkeypatch):
    from backend.adapters.outbound.openai.contracts import (
        OpenAIResponsesResponse,
        OpenAIResponseStatus,
        OpenAIResponseUsage,
    )
    from backend.infrastructure.composition.factories import institutional_catalog as factory
    from tests.unit.test_course_notion_contract import notion_content

    base = f.Catalog

    class Catalog(base):
        def __init__(self):
            super().__init__()
            self.data["notion"].extend(
                {
                    "id": r["notion_ref"],
                    "canonical_label": r["source_wording"],
                    "identity_status": "CANONICAL",
                }
                for r in LINKS
            )
            for row in self.data["official_framework_element"]:
                if row["element_type"] == "QUESTION":
                    row["official_text"] = "SYNTHETIC cultures, codes et représentations"

    monkeypatch.setattr(f, "Catalog", Catalog)

    def setup(patch):
        original = factory.stmg_alignment

        def qualified(*args, **kwargs):
            data = original(*args, **kwargs)
            if kwargs.get("selection") is not None:
                data.update(qualification_sha256="a" * 64, owner_admission_sha256="b" * 64)
            return data

        patch.setattr(factory, "stmg_alignment", qualified)

    selected = f.context()
    selected.update(
        resource_type="COURSE", contract_id="P0-CONTEXT-COURSE-4.0", course_format="CHAPTER"
    )
    selected["local_progression"]["chapter"] = "4"
    selected["institutional"]["notion_refs"] += [r["notion_ref"] for r in LINKS]

    def prepare(port):
        nonce = call(port, "GET", "/api/v2/p0")[1]["data"]["transport_nonce"]
        status, shown = call(
            port,
            "POST",
            "/api/v2/p0/prepare",
            {
                "command_id": token_hex(16),
                "context": selected,
                "reference": {"notion_id": "notion:shared", "passage_ref": f.SOURCE["passage_ref"]},
            },
            nonce,
        )
        assert status == 200, shown
        return nonce, shown["data"]

    with running(tmp_path / "case", monkeypatch, Control(), setup=setup) as (port, config):
        _, prepared = prepare(port)
        native = prepared["context"]["institutional_resolution"]
        assert native["status"] == "CONTENT_GAP"
        adopted = decision(prepared["context"], native)
    path = tmp_path / "SYNTHETIC-local-admission.json"
    raw = canonical(adopted)
    path.write_bytes(raw)

    class RichControl(Control):
        def create(self, *, request):
            self.calls += 1
            dispatch = self.owner.commands.generation_dispatch
            content = notion_content(dispatch)
            chapter = content["course_chapter"]
            for number in range(2, 5):
                chapter["concepts"].append(
                    {
                        **chapter["concepts"][0],
                        "id": "CONCEPT" + str(number),
                        "notion_id": "N" + str(number),
                    }
                )
                chapter["parts"][0]["concept_ids"].append("CONCEPT" + str(number))
            return OpenAIResponsesResponse(
                OpenAIResponseStatus.COMPLETED,
                canonical(progressive_course_fixture(content)).decode(),
                OpenAIResponseUsage(1000, 0, 1000, 2000),
            )

    control = RichControl()
    with running(
        tmp_path / "case",
        monkeypatch,
        control,
        existing=config,
        setup=setup,
        extra_args=[
            "--manual-local-admission",
            str(path),
            "--manual-local-admission-sha256",
            sha(raw),
        ],
    ) as (port, _):
        nonce, prepared = prepare(port)
        context = prepared["context"]
        resolution = context["institutional_resolution"]
        assert resolution["status"] == "RESOLVED_ADMITTED"
        assert resolution["native_institutional_resolution"]["gaps"] == native["gaps"]
        assert alignment_axes(resolution)["institutional_alignment"] == "UNVERIFIED"
        assert (
            bounded_institutional_evidence(resolution)["local_attachment_admission"]["official"]
            is False
        )
        control.owner.commands.generation_dispatch = control.owner.commands.prepared(
            prepared["preparation_ref"], prepared["preparation_sha256"]
        )
        command = {
            "command_id": token_hex(16),
            "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"],
        }
        status, started = call(port, "POST", "/api/v2/p0/generate", command, nonce)
        assert status == 202, started
        done = terminal(port, command["command_id"])
        assert done["state"] == "LOCAL_COMMAND_COMPLETED", done
        assert control.calls == 1
        view = done["result"]["view"]
        base = "/api/v2/productions/" + view["production_ref"] + "/versions/" + view["version_ref"]
        assert call(port, "GET", base + "/saved")[0] == 200
        for kind in ("student", "correction"):
            status, doc = f.request(port, "GET", base + "/word/" + kind)
            assert status == 200
            assert ("SENTINELLE_PROFESSEUR" in text(doc)) == (kind == "correction")
