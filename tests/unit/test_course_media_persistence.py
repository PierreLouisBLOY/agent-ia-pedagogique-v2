"""Illustrated successors retain historical bounds and all immutable ancestors."""

import pytest

from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore
from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.unit.test_course_media import media_chapter


def record_version(parent, chapter, number, illustrated=True):
    data = parent.mutable_copy()
    bundle = parent.p0_bundle.mutable_copy()
    bundle["version_ref"] = "ver:" + f"{number:032x}"
    if illustrated:
        bundle["course_chapter"] = as_plain(chapter.data)
    value = P0Production(bundle)
    data.update(
        bundle=value.mutable_copy(),
        view=as_plain(P0ProductionReadView.from_bundle(value).data),
        validations=[],
        reviews=[],
    )
    return SavedProduction(data)


def test_fourth_illustrated_version_preserves_ancestors_and_thirty_third_is_rejected(tmp_path):
    parent, chapter, _, _ = media_chapter()
    store = LocalSavedProductionStore(tmp_path / "store", create=True)
    originals = [record_version(parent, chapter, n, False) for n in range(1, 4)]
    for record in originals:
        store.save(record)
    with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
        store.save(record_version(parent, chapter, 4, False))
    for n in range(4, 33):
        store.save(record_version(parent, chapter, n))
    final = record_version(parent, chapter, 32)
    assert store.save(final) is False
    before = {r.version_ref: r.sha256 for r in store.list_versions()}
    with pytest.raises(ValueError, match="R4_VERSION_LIMIT"):
        store.save(record_version(parent, chapter, 33))
    reopened = build_saved_application(tmp_path / "store")
    assert len(reopened.execute("list", correlation="media.list")["versions"]) == 32
    for record in (*originals, final):
        view = reopened.execute(
            "open", record.production_ref, record.version_ref, correlation="media.open"
        )
        assert view["record_sha256"] == before[record.version_ref]
        assert view["active_authority"] == "NONE_RESTORED"
    first = reopened.execute(
        "word", final.production_ref, final.version_ref, kind="student", correlation="media.export"
    )
    again = build_saved_application(tmp_path / "store")
    assert first == again.execute(
        "word", final.production_ref, final.version_ref, kind="student", correlation="media.restart"
    )
    changed = final.mutable_copy()
    changed["reservations"].append("substitution")
    with pytest.raises(ValueError, match="IDENTITY_CONFLICT"):
        store.save(SavedProduction(changed))
