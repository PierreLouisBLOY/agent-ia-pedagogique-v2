"""Differential local proposals, chapter retention, search and path boundaries."""

import os

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.infrastructure.filesystem import security
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from tests.test_codesign_global_324 import simple
from tests.test_organization_evidence_325 import official_identity


def local_service(text=None):
    dispatch, _ = simple()
    ref = dispatch["references"][0]
    text = dispatch["evidence"][ref["evidence_id"]] if text is None else text
    from hashlib import sha256

    ref["excerpt_sha256"] = sha256(text.encode()).hexdigest()
    service = P0CreationService(lambda _: {"reference": ref, "excerpt": text})
    prepared = service.execute(
        "prepare", {"command_id": "1" * 32, "context": dispatch["context"], "reference": {}}
    )
    return service, {
        "command_id": "2" * 32,
        **{k: prepared[k] for k in ("preparation_ref", "preparation_sha256")},
    }


def test_complete_native_proposal_edit_save_new_session_and_no_reuse(tmp_path):
    service, command = local_service()
    result = service.execute("local-propose", command)
    assert result["provider_attempts"] == 0 and result["state"] == "CANDIDATE"
    view = result["view"]
    parent = service.records[view["version_ref"]]
    assert len(parent.data["questions"]) == len(parent.data["corrections"]) == 2
    assert service.execute("local-propose", command) == result
    with pytest.raises(ValueError, match="PREPARATION_CHANGED"):
        service.execute("local-propose", {**command, "command_id": "3" * 32})
    changed = service.execute(
        "revise",
        {
            "command_id": "4" * 32,
            **{k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")},
            "edits": {"title": "Lecture du passage et prudence documentaire"},
        },
    )
    app = build_saved_application(
        tmp_path / "SYNTHETIC-native",
        create=True,
        source=service.saved_source,
        word_profile="product-v7",
    )
    child = changed["view"]
    for v in (view, child):
        app.execute(
            "save", body={k: v[k] for k in ("production_ref", "version_ref")}, correlation="327"
        )
    reopened = build_saved_application(tmp_path / "SYNTHETIC-native", word_profile="product-v7")
    for v in (view, child):
        assert (
            reopened.read_local_p0(v["production_ref"], v["version_ref"]).p0_bundle.sha256
            == v["bundle_sha256"]
        )
        for kind in ("student", "correction"):
            assert (
                reopened.execute(
                    "word", v["production_ref"], v["version_ref"], kind=kind, correlation="327"
                )[:2]
                == b"PK"
            )
    assert parent.sha256 == view["bundle_sha256"]


def test_local_proposal_does_not_convert_course_or_accept_divergent_preparation():
    service, command = local_service()
    with pytest.raises(ValueError, match="PREPARATION_CHANGED"):
        service.execute("local-propose", {**command, "preparation_sha256": "f" * 64})
    dispatch, _ = simple("COURSE")
    ref = dispatch["references"][0]
    service = P0CreationService(
        lambda _: {"reference": ref, "excerpt": next(iter(dispatch["evidence"].values()))}
    )
    p = service.execute(
        "prepare", {"command_id": "1" * 32, "context": dispatch["context"], "reference": {}}
    )
    with pytest.raises(ValueError, match="PROFILE_UNSUPPORTED"):
        service.execute(
            "local-propose",
            {
                "command_id": "2" * 32,
                **{k: p[k] for k in ("preparation_ref", "preparation_sha256")},
            },
        )


def test_four_local_exercise_versions_then_refusal_preserves_exact_records(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction

    service, command = local_service()
    view = service.execute("local-propose", command)["view"]
    views = [view]
    for i in range(1, 6):
        view = service.execute("revise", {
            "command_id": f"{i + 100:032x}",
            **{k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")},
            "edits": {"title": f"Finition locale {i}"},
        })["view"]
        views.append(view)
    root = tmp_path / "SYNTHETIC-four-versions"
    app = build_saved_application(root, create=True, source=service.saved_source)

    def save(v):
        return app.execute("save", body={k: v[k] for k in ("production_ref", "version_ref")},
                           correlation="327-capacity")

    for v in views[:3]:
        assert save(v)["created"] is True
    # Competing fourth/fifth saves still share the actual R4 transaction/LOCK.
    def attempt(v):
        try:
            return save(v)
        except PermissionError:
            return "R4_LOCK_BUSY_REFUSED"
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, views[3:5]))
    # The Application saves missing ancestors too. Both callers may report a
    # refusal while one ancestor has filled the fourth place; no success result
    # is required from a competing request denied by the non-blocking LOCK.
    assert all(isinstance(r, dict) or r in {"R4_VERSION_LIMIT", "R4_LOCK_BUSY_REFUSED"}
               for r in results)
    reopened = build_saved_application(root)
    raced = reopened.execute("list", correlation="327-capacity")
    assert 3 <= len(raced["versions"]) <= 4
    save(views[3])  # finish the same local fourth identity, or observe idempotence
    before = reopened.execute("list", correlation="327-capacity")
    assert len(before["versions"]) == 4
    for row in before["versions"]:
        current = reopened.read_local_p0(row["production_ref"], row["version_ref"])
        assert current.sha256 == service.saved_source(row["production_ref"], row["version_ref"]).sha256
        assert save(next(v for v in views if v["version_ref"] == row["version_ref"]))["created"] is False
    with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
        save(views[5])
    raw = service.saved_source(views[0]["production_ref"], views[0]["version_ref"]).mutable_copy()
    raw["provenance"]["SYNTHETIC_CONFLICT"] = "a" * 64
    conflict = build_saved_application(root, source=lambda *_: SavedProduction(raw))
    with pytest.raises(ValueError, match="R4_IDENTITY_CONFLICT"):
        conflict.execute("save", body={k: views[0][k] for k in ("production_ref", "version_ref")},
                         correlation="327-capacity")
    assert reopened.execute("list", correlation="327-capacity") == before


@pytest.mark.parametrize("family", ["COURSE", "ASSESSMENT", "QCM", "QUIZ"])
def test_fourth_place_does_not_expand_other_local_families(family, tmp_path):
    from tests.test_codesign_global_324 import composition

    dispatch, content = simple(family)
    service, _, _ = composition(dispatch, content)
    view = service.read(dispatch["production_ref"], dispatch["version_ref"])
    app = build_saved_application(tmp_path / "SYNTHETIC-other-family", create=True,
                                  source=service.saved_source)
    for i in range(4):
        if i:
            view = service.execute("revise", {"command_id": f"{i + 200:032x}",
                **{k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")},
                "edits": {"title": f"Autre famille {i}"}})["view"]
        args = {k: view[k] for k in ("production_ref", "version_ref")}
        if i == 3:
            with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
                app.execute("save", body=args, correlation="327-other")
        else:
            app.execute("save", body=args, correlation="327-other")


def test_concurrent_local_claims_materialize_one_version(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from backend.modules.pedagogical_design.application.commands.propose_local_reading import (
        ProposeLocalReading,
    )

    service, command = local_service()
    barrier = Barrier(2)
    original = ProposeLocalReading.execute

    def synchronized(owner, request):
        result = original(owner, request)
        barrier.wait(5)
        return result

    monkeypatch.setattr(ProposeLocalReading, "execute", synchronized)

    def attempt(n):
        try:
            return service.execute("local-propose", {**command, "command_id": str(n) * 32})["state"]
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(2) as executor:
        outcomes = list(executor.map(attempt, (3, 4)))
    assert sorted(outcomes) == ["CANDIDATE", "P0_PREPARATION_CHANGED"]
    assert len(service.records) == 1


def test_local_claim_during_generation_authorization_stops_before_effect():
    service, command = local_service()

    class Generation:
        calls = 0

        def authorize(self, *, request):
            service.execute("local-propose", command)
            return True

        def generate(self, *, request):
            self.calls += 1
            raise AssertionError("NO_SECOND_MATERIALIZATION")

    generation = Generation()
    service.generation = generation
    with pytest.raises(ValueError, match="PREPARATION_CHANGED"):
        service.execute("generate", {**command, "command_id": "5" * 32})
    assert generation.calls == 0 and len(service.records) == 1




def indexed_captures():
    from backend.adapters.outbound.resource_library.organization_capture import (
        LocalOrganizationCaptures,
    )

    record = official_identity()
    row = {
        "organization_id": record.data["organization_id"],
        "capture_sha256": fingerprint(record.data),
        "notion_refs": ["notion:organisation"],
        "sector": "commerce",
        "organization_type": "ENTERPRISE",
        "selection_analysis": {
            "kind": "LOCAL_ANALYSIS_NOT_CANONICAL_RELATION",
            "text": "Classement local proposé pour un usage pédagogique, pas un fait canonique.",
            "source_url": record.data["source_url"],
            "retrieved_on": record.data["retrieved_on"],
        },
    }
    return LocalOrganizationCaptures((record,), index=(row,)), row


def test_search_exact_local_classification_without_admission_or_fiction():
    from backend.modules.resource_library.application.queries.search_organizations import (
        SearchOrganizations,
    )
    from backend.modules.resource_library.contracts.dto.organization_search import (
        OrganizationSearch,
    )

    captures, row = indexed_captures()
    query = SearchOrganizations(captures)
    criteria = OrganizationSearch("notion:organisation", "commerce", "ENTERPRISE")
    result = query.execute(criteria)
    assert len(result["items"]) == 1 and result["canonical_admission"] == "NOT_GRANTED"
    assert result["items"][0]["fiction"] == []
    for kind in ("ASSOCIATION", "ADMINISTRATION", "COOPERATIVE"):
        assert (
            query.execute(OrganizationSearch("notion:organisation", "commerce", kind))["items"]
            == []
        )
    assert (
        query.execute(OrganizationSearch("notion:perception", "commerce", "ENTERPRISE"))["items"]
        == []
    )
    assert (
        query.execute(OrganizationSearch("notion:organisation", "autre", "ENTERPRISE"))["items"]
        == []
    )
    row["capture_sha256"] = "0" * 64
    from backend.adapters.outbound.resource_library.organization_capture import (
        LocalOrganizationCaptures,
    )

    with pytest.raises(ValueError, match="CAPTURE_CHANGED"):
        LocalOrganizationCaptures(captures.records, index=(row,))


def test_path_checks_access_error_and_broken_link_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "ordinary"
    path.write_text("original")
    assert security.hash_file_nofollow(path, allowed_root=tmp_path)
    real = os.lstat

    def denied(p, *a, **kw):
        if str(p) == str(tmp_path):
            raise PermissionError("SYNTHETIC_DENIED")
        return real(p, *a, **kw)

    with monkeypatch.context() as mp:
        mp.setattr(os, "lstat", denied)
        with pytest.raises(security.LocalFileSecurityError, match="PATH_RESOLUTION_FAILED"):
            security.hash_file_nofollow(path, allowed_root=tmp_path)

    # No OS symlink privilege required: reproduce an actual reparse stat result.
    from types import SimpleNamespace

    def redirected(p, *a, **kw):
        if str(p) == str(tmp_path):
            return SimpleNamespace(st_mode=0, st_file_attributes=0x400)
        return real(p, *a, **kw)

    with monkeypatch.context() as mp:
        mp.setattr(os, "lstat", redirected)
        with pytest.raises(security.LocalFileSecurityError, match="PATH_REDIRECTION_FORBIDDEN"):
            security.hash_file_nofollow(path, allowed_root=tmp_path)


def test_quoted_conditions_are_never_normalized_by_generic_word_writer(tmp_path):
    from io import BytesIO
    from xml.etree.ElementTree import fromstring
    from zipfile import ZipFile

    literal = "Citation exacte : Conditions : Conditions : cette répétition appartient à la source."
    service, command = local_service(literal)
    view = service.execute("local-propose", command)["view"]
    app = build_saved_application(
        tmp_path / "SYNTHETIC-quote",
        create=True,
        source=service.saved_source,
        word_profile="product-v7",
    )
    app.execute(
        "save", body={k: view[k] for k in ("production_ref", "version_ref")}, correlation="327"
    )
    for kind in ("student", "correction"):
        raw = app.execute(
            "word", view["production_ref"], view["version_ref"], kind=kind, correlation="327"
        )
        with ZipFile(BytesIO(raw)) as z:
            root = fromstring(z.read("word/document.xml"))
            assert literal in "".join(root.itertext())


@pytest.mark.parametrize("sector", [12, True, None])
def test_index_rejects_non_string_sector_before_search(sector):
    from backend.modules.resource_library.contracts.dto.organization_search import selection_row

    _, row = indexed_captures()
    with pytest.raises(ValueError, match="SEARCH_FIELDS"):
        selection_row({**row, "sector": sector})
