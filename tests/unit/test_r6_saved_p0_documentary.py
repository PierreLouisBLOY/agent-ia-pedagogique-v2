from pathlib import Path

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.infrastructure.composition.factories.saved_p0_documentary import (
    admit_p0_documentary_record,
    admit_saved_p0_documentary,
)
from tests.unit.test_r6_p0_contract import candidate, saved_record


def test_application_payload_handoff_checks_owner_pin_before_admission(tmp_path):
    record = saved_record(candidate())
    target = tmp_path / "handoff"
    with pytest.raises(ValueError, match="P0_DOCUMENTARY_SOURCE_IDENTITY"):
        admit_p0_documentary_record(record.mutable_copy(), target,
                                    expected_record_sha256="0" * 64, create=True)
    assert not target.exists()
    result = admit_p0_documentary_record(record.mutable_copy(), target,
        expected_record_sha256=record.sha256, create=True)
    assert result["bundle_sha256"] == record.p0_bundle.sha256
    assert result["active_authority"] == "NONE_RESTORED"
    assert result["historical_reports_copied"] is False


def test_documentary_p0_preserves_bundle_and_refuses_authority(tmp_path: Path) -> None:
    record = saved_record(candidate("ASSESSMENT"))
    source_root = tmp_path / "source"
    source = build_saved_application(source_root, create=True, source=lambda p,v:record)
    source.execute("save",body={"production_ref":record.production_ref,
                   "version_ref":record.version_ref},correlation="test.source.save")
    target_root = tmp_path / "target"
    proof = admit_saved_p0_documentary(source_root,target_root,
        production_ref=record.production_ref,version_ref=record.version_ref,
        expected_record_sha256=record.sha256,create=True)
    assert proof["active_authority"] == "NONE_RESTORED"
    assert proof["historical_reports_copied"] is False
    app = build_saved_application(target_root)
    opened = app.execute("open",record.production_ref,record.version_ref,correlation="test.open")
    assert opened["record"]["bundle"] == record.mutable_copy()["bundle"]
    assert opened["record"]["origin"] == "IMPORTED_DOCUMENTARY"
    assert opened["new_actions"] == []
    for kind in ("student","correction","marking"):
        assert app.execute("word",record.production_ref,record.version_ref,
                           kind=kind,correlation="test.word").startswith(b"PK")
    with pytest.raises(ValueError,match="R4_DOCUMENTARY_IMPORT_READ_ONLY"):
        app.execute("validate",record.production_ref,record.version_ref,
            body={"action_id":"action:"+"1"*32,"record_sha256":proof["record_sha256"]},
            correlation="test.no.authority")
    assert source.execute("open",record.production_ref,record.version_ref,
                          correlation="test.source.unchanged")["record_sha256"] == record.sha256


def test_wrong_historical_pin_refused_before_target_creation(tmp_path: Path) -> None:
    record = saved_record(candidate("EXERCISE"))
    source_root = tmp_path / "source"
    source = build_saved_application(source_root,create=True,source=lambda p,v:record)
    source.execute("save",body={"production_ref":record.production_ref,
                   "version_ref":record.version_ref},correlation="test.source.save")
    target = tmp_path / "target"
    with pytest.raises(ValueError,match="P0_DOCUMENTARY_SOURCE_IDENTITY"):
        admit_saved_p0_documentary(source_root,target,production_ref=record.production_ref,
            version_ref=record.version_ref,expected_record_sha256="0"*64,create=True)
    assert not target.exists()
