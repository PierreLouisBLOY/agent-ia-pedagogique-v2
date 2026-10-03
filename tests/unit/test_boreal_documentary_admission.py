import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.support.r4_synthetic import record


def test_documentary_admission_saves_exact_record_without_authority(tmp_path):
    application = build_saved_application(tmp_path / "saved", create=True)
    source = record()
    data = source.mutable_copy()
    data.update(origin="IMPORTED_DOCUMENTARY", bundle=None, reviews=[], validations=[],
                provenance={"ORIGINAL_OUTPUT": "a" * 64})
    value = SavedProduction(data)
    saved = application.admit_documentary(value)
    assert saved["created"] is True
    assert application.admit_documentary(value)["created"] is False
    reopened = application.execute("open", value.production_ref, value.version_ref,
                                   correlation="documentary-test")
    assert reopened["record_sha256"] == value.sha256
    assert reopened["active_authority"] == "NONE_RESTORED"
    assert reopened["new_actions"] == []
    for operation in ("validate", "gate"):
        with pytest.raises(ValueError, match="R4_DOCUMENTARY_IMPORT_READ_ONLY"):
            application.execute(operation, value.production_ref, value.version_ref,
                body={"action_id": "action:" + "1" * 32, "record_sha256": value.sha256},
                correlation="documentary-test")


def test_local_origin_cannot_enter_documentary_admission(tmp_path):
    application = build_saved_application(tmp_path / "saved", create=True)
    with pytest.raises(ValueError, match="R4_DOCUMENTARY_IMPORT_REQUIRED"):
        application.admit_documentary(record())


def test_reports_cannot_be_attached_as_implicitly_admitted(tmp_path):
    application = build_saved_application(tmp_path / "saved", create=True)
    data = record().mutable_copy()
    data.update(origin="IMPORTED_DOCUMENTARY", provenance={"ORIGINAL_OUTPUT": "a" * 64})
    data["reviews"] = [{"production_ref": data["view"]["production_ref"],
                        "version_ref": data["view"]["version_ref"],
                        "bundle_sha256": record().bundle.sha256}]
    value = SavedProduction(data)
    with pytest.raises(ValueError, match="R4_DOCUMENTARY_REPORT_ADMISSION_REQUIRED"):
        application.admit_documentary(value)
