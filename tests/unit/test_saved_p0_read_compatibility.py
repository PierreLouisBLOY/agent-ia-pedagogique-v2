"""Exact historical COURSE operation variants and immutable authenticated reads."""
from dataclasses import FrozenInstanceError

import pytest

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, fingerprint
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.application.queries.verify_saved_p0_lineage import (
    verify_saved_parent,
)
from backend.modules.work_orchestration.application.services.saved_production import (
    SavedProductionService,
)
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.support.r4_synthetic import record as legacy_record
from tests.unit.test_course_chapter import child_fixture
from tests.unit.test_integrated_saved_p0_resume import resume_with, stored_parent


def historical(version):
    parent, rich = child_fixture()
    envelope = rich.mutable_copy()
    data = rich.p0_bundle.mutable_copy()
    if version in {"V0", "V1_GENERIC"}:
        data.pop("course_chapter")
        data["contract_id"] = "R6-P0-PRODUCTION-1.0"
        data["sections"] = as_plain(parent.p0_bundle.data["sections"])
    bundle = P0Production(data)
    operation = {"mode": "EXPLICIT_LOCAL_CONTEXT_SUCCESSOR", "parent": parent.sha256,
                 "context": bundle.context.sha256, "title": data["title"], "sections": data["sections"]}
    if version != "V0":
        operation["course_chapter"] = data.get("course_chapter")
    envelope["bundle"] = bundle.mutable_copy()
    envelope["view"] = as_plain(P0ProductionReadView.from_bundle(bundle).data)
    envelope["validations"] = [ValidateP0Command().execute(bundle, parent=parent.p0_bundle)]
    envelope["provenance"].pop("LOCAL_REFERENCE_SUCCESSOR_SHA256")
    envelope["provenance"]["LOCAL_EDIT_OPERATION_SHA256"] = fingerprint(operation)
    return parent, SavedProduction(envelope)


def rebuild(envelope):
    bundle = P0Production(envelope["bundle"])
    envelope["view"] = as_plain(P0ProductionReadView.from_bundle(bundle).data)
    for report in envelope["validations"]:
        report["bundle_sha256"] = bundle.sha256
    return SavedProduction(envelope)


@pytest.mark.parametrize("version", ["V0", "V1_GENERIC", "V1_RICH"])
def test_exact_historical_variants_resume_without_restoring_source_authority(version):
    parent, child = historical(version)
    verify_saved_parent(child, parent)
    service = resume_with({parent.version_ref: parent, child.version_ref: child})
    assert service.read(child.production_ref, child.version_ref)["bundle_sha256"] == child.p0_bundle.sha256
    assert service._local_quality(child.p0_bundle, {})["sources"] == "RESERVE"
    assert service.evidence[child.version_ref] == {}
    assert service.saved_source(parent.production_ref, parent.version_ref).sha256 == parent.sha256


@pytest.mark.parametrize("version", ["V0", "V1_GENERIC", "V1_RICH"])
@pytest.mark.parametrize("mutation", ["references", "reference_witness", "parent_record", "parent_bundle",
    "operation", "conversation", "evidence_set", "failed_validation", "missing_validation"])
def test_historical_variant_does_not_bypass_exact_witnesses(version, mutation):
    parent, child = historical(version)
    envelope = child.mutable_copy()
    if mutation == "references":
        envelope["bundle"]["references"][0]["locator"] = "unit:substituted-locator"
    elif mutation == "reference_witness":
        envelope["provenance"]["LOCAL_REFERENCE_SUCCESSOR_SHA256"] = "9" * 64
    elif mutation in {"parent_record", "parent_bundle", "operation"}:
        key = {"parent_record": "LOCAL_EDIT_PARENT_RECORD_SHA256", "parent_bundle": "LOCAL_EDIT_PARENT_BUNDLE_SHA256",
               "operation": "LOCAL_EDIT_OPERATION_SHA256"}[mutation]
        envelope["provenance"][key] = "9" * 64
    elif mutation in {"conversation", "evidence_set"}:
        key, prefix = ("conversation_id", "conv:") if mutation == "conversation" else ("evidence_set_ref", "evidence:")
        envelope["bundle"]["lineage"][key] = prefix + "9" * 32
    elif mutation == "failed_validation":
        envelope["validations"][0]["status"] = "FAIL"
    else:
        envelope["validations"] = []
    changed = rebuild(envelope)
    service = resume_with({parent.version_ref: parent, changed.version_ref: changed})
    with pytest.raises(ValueError, match="P0_SAVED_LINEAGE_BINDING"):
        service.read(changed.production_ref, changed.version_ref)
    assert service.records == service.plans == service.resumed == {}


def test_v0_digest_cannot_omit_an_existing_rich_chapter():
    parent, child = historical("V1_RICH")
    envelope = child.mutable_copy()
    envelope["provenance"]["LOCAL_EDIT_OPERATION_SHA256"] = fingerprint({
        "mode": "EXPLICIT_LOCAL_CONTEXT_SUCCESSOR", "parent": parent.sha256,
        "context": child.p0_bundle.context.sha256, "title": child.p0_bundle.data["title"],
        "sections": as_plain(child.p0_bundle.data["sections"])})
    with pytest.raises(ValueError, match="P0_SAVED_LINEAGE_BINDING"):
        verify_saved_parent(SavedProduction(envelope), parent)


def test_cached_p0_bundle_is_immutable_and_outside_serialized_identity():
    original = stored_parent()
    raw = original.mutable_copy()
    saved = SavedProduction(raw)
    bundle, identity = saved.p0_bundle, saved.sha256
    assert bundle is saved.p0_bundle
    assert saved == original and saved.sha256 == fingerprint(saved.data)
    assert "_typed_p0_bundle" not in saved.data and "_typed_p0_bundle" not in repr(saved)
    raw["bundle"]["title"] = "Input mutation"
    copied = saved.mutable_copy()
    copied["bundle"]["title"] = "Mutable copy mutation"
    assert saved.p0_bundle is bundle and saved.sha256 == identity
    assert saved.mutable_copy() == original.mutable_copy()
    with pytest.raises(TypeError):
        bundle.data["title"] = "Forbidden"
    with pytest.raises(FrozenInstanceError):
        saved._typed_p0_bundle = None
    invalid = saved.mutable_copy()
    invalid["bundle"]["context_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        SavedProduction(invalid)


def test_cached_legacy_record_still_has_no_p0_bundle():
    saved = legacy_record()
    assert saved.p0_bundle is None and saved.bundle is not None
    assert saved.mutable_copy() == SavedProduction(saved.mutable_copy()).mutable_copy()


class SyntheticStore:
    def __init__(self, record):
        self.record = record
        self.loaded = []

    def load(self, production, version):
        self.loaded.append((production, version))
        return self.record

    def actions(self, record):
        pytest.fail("Read query must not load or restore actions")


def test_application_read_returns_one_authenticated_record_without_actions():
    record = stored_parent()
    store = SyntheticStore(record)
    result = SavedProductionService(store).read_local_p0(record.production_ref, record.version_ref)
    assert result is record
    assert store.loaded == [(record.production_ref, record.version_ref)]
    assert result.sha256 == record.sha256


@pytest.mark.parametrize("mutation", ["imported", "legacy", "production", "version"])
def test_application_read_rejects_wrong_origin_family_and_requested_identity(mutation):
    original = stored_parent()
    data = original.mutable_copy()
    if mutation == "imported":
        data["origin"] = "IMPORTED_DOCUMENTARY"
        data["provenance"] = {"SYNTHETIC_SOURCE": "a" * 64}
        record = SavedProduction(data)
    elif mutation == "legacy":
        record = legacy_record()
    else:
        record = original
    production = "prod:" + "f" * 32 if mutation == "production" else record.production_ref
    version = "ver:" + "f" * 32 if mutation == "version" else record.version_ref
    code = "P0_SAVED_VERSION_BINDING" if mutation in {"production", "version"} else "P0_SAVED_SOURCE_REJECTED"
    with pytest.raises(ValueError, match=code):
        SavedProductionService(SyntheticStore(record)).read_local_p0(production, version)
