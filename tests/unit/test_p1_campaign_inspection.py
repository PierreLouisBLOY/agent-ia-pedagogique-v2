"""Synthetic metadata only: no file access, real receipt, SDK or provider."""
from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping

import pytest

from backend.adapters.inbound.application.p1_campaign_inspection import P1CampaignInspectionInbound
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, recover_binding
from backend.core_contracts.outcome import ApplicationFailureKind, OutcomeStatus
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.work_orchestration.application.queries.inspect_p1_campaign import (
    InspectP1Campaign,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    EVENTS,
    P1CampaignInspectionPortError,
    P1CampaignInspectionRequest,
    P1CampaignInspectionView,
)
from backend.shared_kernel.correlation import CorrelationId

HASH = "a" * 64
REF = "p1-inspection:synthetic"
STAMP = "2000-01-01T00:01:00+00:00"


def evidence() -> dict[str, object]:
    fields = {"campaign_namespace_sha256", "root_permission_sha256", "origin_permission_sha256", "namespace_sha256",
        "request_sha256", "slot_sha256", "grant_sha256", "preview_sha256", "dispatch_capture_sha256",
        "dispatch_payload_sha256", "preflight_sha256", "result_sha256", "output_text_sha256", "inspection_plan_sha256"}
    return {**{key: HASH for key in fields}, "schema": "P0-PRODUCT-KNOWN-REJECTED-EVIDENCE-1.0",
        "observation_state": "OBSERVED_NOT_ADOPTED", "request_bytes": 100, "reserved_usd": "0.01",
        "command_id": "b" * 32, "response_status": "completed", "provider_attempts": 1,
        "event_sha256s": {state: HASH for state in EVENTS}, "event_timestamps": {state: STAMP for state in EVENTS},
        "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 20,
            "reasoning_tokens": 3, "total_tokens": 30, "cache_write_input_tokens": 0},
        "disposition": "TENTATIVE_CAPTUREE_REJETEE_A_CONSERVER_ET_COMPTER",
        "local_rejection_code": "P0_RICH_COURSE_NOTION_UNKNOWN",
        "owner_orientation_adoption": {"path": "Q:/SYNTHETIC/contrôle/orientation.json", "sha256": HASH},
        "owner_diagnostic": {"path": "Q:/SYNTHETIC/diagnostic.json", "sha256": HASH},
        "transport_metadata_scope": "NOT_RETAINED_TIER_AND_INCOMPLETE_REASON",
        "qualification": "REJECTED_NOT_CONSUMED", "timestamp_utc": STAMP}


def observation() -> dict[str, object]:
    witness = evidence()
    return {"schema": "P0-PRODUCT-REJECTED-OBSERVATION-1.0", "state": "OBSERVED_NOT_ADOPTED", "timestamp_utc": STAMP,
        "observed_evidence": witness, "observed_evidence_sha256": fingerprint(witness), "campaign_namespace_sha256": HASH,
        "root_permission_sha256": HASH, "observed_slots_reserved": 2, "observed_reserved_budget_usd": "0.02",
        "consumed_count": 1, "known_rejected_count": 1, "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
        "live_enabled": False, "provider_calls": 0, "ledger_mutations": 0, "inspection_plan_sha256": HASH}


def snapshot() -> dict[str, object]:
    return {"schema": "P0-PRODUCT-CAMPAIGN-SNAPSHOT-2.0", "state": "CURRENT_RESERVATIONS_RECONCILED", "timestamp_utc": STAMP,
        "root_permission_sha256": HASH, "current_permission_sha256": HASH, "campaign_namespace_sha256": HASH,
        "slots_reserved": 2, "reserved_budget_usd": "0.02", "remaining_calls": 1, "remaining_reserved_budget_usd": "0.01",
        "financial_basis": "RESERVATIONS_NOT_BILLED_COST", "live_enabled": False, "known_rejected_count": 1,
        "consumed_count": 1, "disposition_sha256": HASH, "inspection_scope": "READ_ONLY_RECONCILIATION",
        "historic_transport_scope": "NOT_RETAINED_TIER_AND_INCOMPLETE_REASON", "course_qualification": "NOT_COMPLETED",
        "current_context_contract_scope": "P0-CONTEXT-COURSE-4.0", "observation_plan_sha256": HASH}


class Reader:
    def __init__(self, data: dict[str, object]) -> None:
        self.data = data
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None

    def inspect(self, *, inspection_ref: str, expected_plan_or_profile_sha256: str) -> Mapping[str, object]:
        self.calls.append((inspection_ref, expected_plan_or_profile_sha256))
        if self.error is not None:
            raise self.error
        return self.data


def inbound(reader: Reader) -> P1CampaignInspectionInbound:
    return P1CampaignInspectionInbound(InspectP1Campaign(reader, inspection_ref=REF, expected_plan_or_profile_sha256=HASH))


def test_bootstrap_projection_preserves_full_witness_hash_without_private_paths() -> None:
    raw = observation()
    before = copy.deepcopy(raw)
    reader = Reader(raw)
    result = inbound(reader).inspect(request=P1CampaignInspectionRequest(REF, HASH), correlation_id=CorrelationId("synthetic"))
    assert result.success and result.data is not None and result.side_effects == () and result.operation_ref is None
    projected = result.data.as_dict()
    assert projected["schema"] == "P1-CAMPAIGN-INSPECTION-OBSERVATION-1.0"
    assert projected["state"] == "OBSERVED_NOT_ADOPTED" and projected["live_enabled"] is False
    assert projected["evidence_hash_basis"] == "UNDERLYING_FULL_EVIDENCE_RAW_BYTES"
    assert projected["observed_evidence_sha256"] == fingerprint(before["observed_evidence"])
    safe = object_data(projected["observed_evidence"])
    assert safe["schema"] == "P1-KNOWN-REJECTED-EVIDENCE-METADATA-1.0"
    assert safe["owner_orientation_adoption"] == {"ref": "p1-evidence:" + HASH, "sha256": HASH}
    assert safe["owner_diagnostic"] == {"ref": "p1-evidence:" + HASH, "sha256": HASH}
    assert projected["observed_evidence_sha256"] != fingerprint(safe)
    assert "Q:/" not in json.dumps(projected) and "path" not in object_data(safe["owner_diagnostic"])
    assert "remaining_calls" not in projected and "current_permission_sha256" not in projected
    assert raw == before and reader.calls == [(REF, HASH)]
    assert canonical(before["observed_evidence"]).decode("utf-8").find("contrôle") >= 0
    assert fingerprint(before["observed_evidence"]) == hashlib.sha256(canonical(before["observed_evidence"])).hexdigest()


def test_snapshot_is_unchanged_frozen_and_still_not_course_qualification() -> None:
    raw = snapshot()
    result = inbound(Reader(raw)).inspect(request=P1CampaignInspectionRequest(REF, HASH).as_dict(), correlation_id=CorrelationId("synthetic"))
    assert result.success and result.data is not None and result.data.as_dict() == raw
    raw["course_qualification"] = "QUALIFIED"
    assert result.data.data["course_qualification"] == "NOT_COMPLETED"
    with pytest.raises(TypeError):
        result.data.data["live_enabled"] = True  # type: ignore[index]


@pytest.mark.parametrize("key,value", [
    ("observed_evidence_sha256", "b" * 64), ("known_rejected_count", True), ("provider_calls", False),
    ("live_enabled", 0), ("state", "CURRENT_RESERVATIONS_RECONCILED"), ("financial_basis", "BILLED_COST"),
    ("timestamp_utc", "2000-01-01T00:01:00"), ("observed_slots_reserved", 3), ("remaining_calls", 12),
    ("inspection_plan_sha256", "b" * 64), ("observed_reserved_budget_usd", "NaN"),
    ("observed_reserved_budget_usd", "0.001"), ("ledger_mutations", 1),
])
def test_bootstrap_mutations_are_rejected(key: str, value: object) -> None:
    data = observation()
    data[key] = value
    with pytest.raises((TypeError, ValueError)):
        P1CampaignInspectionView.from_mapping(data)


@pytest.mark.parametrize("key,value", [
    ("output_text", "not permitted"), ("provider_attempts", True), ("qualification", "QUALIFIED"),
    ("transport_metadata_scope", "RECONSTRUCTED"), ("command_id", "a" * 64),
    ("owner_diagnostic", {"path": "Q:/SYNTHETIC/example.json", "sha256": "invalid"}),
    ("request_bytes", True), ("response_status", "incomplete"),
])
def test_invalid_full_witness_is_refused_even_with_its_updated_hash(key: str, value: object) -> None:
    data = observation()
    full = object_data(data["observed_evidence"])
    full[key] = value
    data.update(observed_evidence=full, observed_evidence_sha256=fingerprint(full))
    with pytest.raises((TypeError, ValueError)):
        P1CampaignInspectionView.from_mapping(data)


@pytest.mark.parametrize("key,value", [
    ("schema", "P0-PRODUCT-CAMPAIGN-SNAPSHOT-1.0"), ("known_rejected_count", True), ("live_enabled", 1),
    ("remaining_calls", -1), ("consumed_count", 2), ("reserved_budget_usd", "Infinity"),
    ("course_qualification", "QUALIFIED"), ("inspection_scope", "Q:/SYNTHETIC/private.json"),
    ("output_text", "unexpected"), ("disposition_sha256", "INVALID"),
])
def test_snapshot_mutations_do_not_return_a_success(key: str, value: object) -> None:
    data = snapshot()
    data[key] = value
    reader = Reader(data)
    result = inbound(reader).inspect(request=P1CampaignInspectionRequest(REF, HASH), correlation_id=CorrelationId("synthetic"))
    assert not result.success and result.data is None and result.side_effects == ()
    assert result.application_failure is not None and result.application_failure.kind is ApplicationFailureKind.AF_MAPPING_CORRUPTION
    assert len(reader.calls) == 1


@pytest.mark.parametrize("kind", [ApplicationFailureKind.AF_MAPPING_CORRUPTION, ApplicationFailureKind.AF_CONCURRENCY,
    ApplicationFailureKind.AF_PORT_UNAVAILABLE, ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN])
def test_typed_port_failures_preserve_their_kind_without_exposing_raw_values(kind: ApplicationFailureKind) -> None:
    reader = Reader(snapshot())
    reader.error = P1CampaignInspectionPortError(kind)
    result = inbound(reader).inspect(request=P1CampaignInspectionRequest(REF, HASH), correlation_id=CorrelationId("synthetic"))
    assert not result.success and result.data is None and result.side_effects == ()
    assert result.application_failure is not None and result.application_failure.kind is kind
    assert (result.outcome_status is OutcomeStatus.INDETERMINATE) == (kind is ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN)
    assert result.application_failure.reconciliation_required == (kind is ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN)


@pytest.mark.parametrize("error,kind", [(ValueError("Q:/SYNTHETIC/private"), ApplicationFailureKind.AF_MAPPING_CORRUPTION),
    (OSError("Q:/SYNTHETIC/private"), ApplicationFailureKind.AF_PORT_UNAVAILABLE),
    (RuntimeError("Q:/SYNTHETIC/private"), ApplicationFailureKind.AF_PORT_UNAVAILABLE)])
def test_untyped_port_errors_are_minimized(error: Exception, kind: ApplicationFailureKind) -> None:
    reader = Reader(snapshot())
    reader.error = error
    result = inbound(reader).inspect(request=P1CampaignInspectionRequest(REF, HASH), correlation_id=CorrelationId("synthetic"))
    assert result.application_failure is not None and result.application_failure.kind is kind
    assert "Q:/" not in repr(result)


@pytest.mark.parametrize("inspection_request", [P1CampaignInspectionRequest("p1-inspection:other", HASH),
    P1CampaignInspectionRequest(REF, "b" * 64)])
def test_binding_mismatch_never_calls_the_reader(inspection_request: P1CampaignInspectionRequest) -> None:
    reader = Reader(snapshot())
    result = inbound(reader).inspect(request=inspection_request, correlation_id=CorrelationId("synthetic"))
    assert not result.success and reader.calls == []


@pytest.mark.parametrize("key,value", [("path", "Q:/SYNTHETIC/private"), ("inspection_ref", "Q:/SYNTHETIC/private"),
    ("expected_plan_or_profile_sha256", True), ("contract_id", "WRONG")])
def test_request_cannot_acquire_a_path_or_authority(key: str, value: object) -> None:
    raw = P1CampaignInspectionRequest(REF, HASH).as_dict()
    raw[key] = value
    with pytest.raises(ValueError):
        P1CampaignInspectionRequest.from_mapping(raw)


def test_invalid_correlation_never_calls_the_reader() -> None:
    reader = Reader(snapshot())
    with pytest.raises(ValueError):
        inbound(reader).inspect(request=P1CampaignInspectionRequest(REF, HASH), correlation_id=CorrelationId("Q:/SYNTHETIC/private"))
    assert reader.calls == []


@pytest.mark.parametrize("invalid", [None, "invalid", 1])
def test_invalid_inbound_type_never_calls_the_reader(invalid: object) -> None:
    reader = Reader(snapshot())
    with pytest.raises(ValueError):
        inbound(reader).inspect(request=invalid, correlation_id=CorrelationId("synthetic"))  # type: ignore[arg-type]
    assert reader.calls == []


def test_plain_string_cannot_be_used_as_typed_port_failure_kind() -> None:
    with pytest.raises(ValueError):
        P1CampaignInspectionPortError("AF_MAPPING_CORRUPTION")  # type: ignore[arg-type]


@pytest.mark.parametrize("cached,written", [(8, 8), (None, 8), (8, None)])
def test_usage_compatibility_with_v1_exact_predicates(cached: int | None, written: int | None) -> None:
    data = observation()
    full = object_data(data["observed_evidence"])
    usage = object_data(full["usage"])
    usage.update(cached_input_tokens=cached, cache_write_input_tokens=written)
    artifact = {"schema": "P0-NORMAL-CONFIRMED-RESULT-1.0", "grant_sha256": HASH,
        "request_sha256": HASH, "dispatch_sha256": HASH, "response_status": "completed",
        "output_text": "SYNTHETIC_RESULT_DO_NOT_PROMOTE", "usage": usage}
    assert recover_binding(artifact=artifact, grant_sha256=HASH, request_sha256=HASH, dispatch_sha256=HASH) == artifact["output_text"]
    full.update(usage=usage, result_sha256=fingerprint(artifact),
        output_text_sha256=hashlib.sha256(str(artifact["output_text"]).encode()).hexdigest())
    data.update(observed_evidence=full, observed_evidence_sha256=fingerprint(full))
    assert canonical(full) == json.dumps(full, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    result = inbound(Reader(data)).inspect(request=P1CampaignInspectionRequest(REF, HASH), correlation_id=CorrelationId("synthetic"))
    assert result.success and result.data is not None
    safe = object_data(result.data.as_dict()["observed_evidence"])
    assert safe["usage"] == usage and "output_text" not in safe
