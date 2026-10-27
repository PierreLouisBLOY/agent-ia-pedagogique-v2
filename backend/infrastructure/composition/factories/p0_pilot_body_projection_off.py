"""Exact pilot body projection. No generation authority or historical store access."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService

_FIELDS = {"schema", "operation", "policy_sha256", "parent_unknown_request_sha256",
           "runtime_sha256", "context_sha256", "reference_set_sha256",
           "historical_slots", "historical_reserved_usd", "per_call_ceiling_usd",
           "cumulative_ceiling_usd"}
_PARENT = "176b136b4f80b11009d93713fa85e7805c851ad3c466b609a43e45c7fa84cf2b"
_POLICY = "d1ac715fa05ae5acc96d987178737f4a7694063048e68060124ef065ae938a72"


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


class P0PilotBodyProjectionOffComposition:
    """A visible local body, with no claim of current cost or ledger authority."""

    generation = None

    def __init__(self, *, scope: Mapping[str, object], runtime_sha256: str,
        historical_inspector: Callable[[], dict[str, object]] | None = None,
        read_scope_sha256: str | None = None,
        expected_preparation_sha256: str | None = None,
        expected_request_sha256: str | None = None,
        expected_request_bytes: int | None = None) -> None:
        data = object_data(scope, _FIELDS)
        if (data["schema"] != "P1-PILOT-BODY-SCOPE-OFF-1.0"
            or data["operation"] != "ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN"
            or data["policy_sha256"] != _POLICY
            or data["parent_unknown_request_sha256"] != _PARENT
            or data["runtime_sha256"] != runtime_sha256
            or data["historical_slots"] != 3
            or data["historical_reserved_usd"] != "0.2544660"
            or data["per_call_ceiling_usd"] != "0.1400000"
            or data["cumulative_ceiling_usd"] != "1.9600000"
            or any(not _digest(data[key]) for key in ("context_sha256", "reference_set_sha256"))):
            raise ValueError("P1_PILOT_OFF_SCOPE_REJECTED")
        self._scope = data
        if (historical_inspector is None) != (read_scope_sha256 is None) or (
            read_scope_sha256 is not None and not _digest(read_scope_sha256)):
            raise ValueError("P1_PILOT_READ_BINDING_REQUIRED")
        if historical_inspector is not None and (
            not _digest(expected_preparation_sha256) or not _digest(expected_request_sha256)
            or type(expected_request_bytes) is not int or not 0 < expected_request_bytes <= 512_000):
            raise ValueError("P1_PILOT_READ_BINDING_REQUIRED")
        self._historical_inspector = historical_inspector
        self._read_scope_sha256 = read_scope_sha256
        self._expected_preparation_sha256 = expected_preparation_sha256
        self._expected_request_sha256 = expected_request_sha256
        self._expected_request_bytes = expected_request_bytes

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        if service.generation is not None or endpoint.consent_execute is not None:
            raise ValueError("P1_PILOT_OFF_EFFECT_FORBIDDEN")
        endpoint.generation_bound = False
        endpoint.consent_execute = None
        # Historical verification is requested only with the exact preview;
        # metadata and ordinary preparation stay available without a long LOCK read.
        endpoint.campaign_snapshot = None

        def preview(payload: Mapping[str, object]) -> dict[str, object]:
            data = object_data(payload, {"command_id", "preparation_ref", "preparation_sha256"})
            ref, pin, command = data["preparation_ref"], data["preparation_sha256"], data["command_id"]
            if (type(command) is not str or len(command) != 32
                or any(char not in "0123456789abcdef" for char in command)
                or type(ref) is not str or not ref.startswith("prep:")
                or type(pin) is not str or len(pin) != 64):
                raise ValueError("P1_PILOT_OFF_PREVIEW_IDENTITY")
            request = service.prepared.get(ref)
            if request is None or fingerprint(request) != pin:
                raise ValueError("P0_PREPARATION_CHANGED")
            if (request["context_sha256"] != self._scope["context_sha256"]
                or sha(canonical(request["references"])) != self._scope["reference_set_sha256"]):
                raise ValueError("P1_PILOT_OFF_PREPARATION_CHANGED")
            wire = build_p0_content_request(request)
            raw = NormalP0GenerationAdapter.body(wire)
            if self._historical_inspector is not None and (
                pin != self._expected_preparation_sha256 or sha(raw) != self._expected_request_sha256
                or len(raw) != self._expected_request_bytes):
                raise ValueError("P1_PILOT_READ_EXACT_BODY_REQUIRED")
            result = {"schema": "P1-PILOT-BODY-PROJECTION-OFF-1.0",
                "state": "OFF_BODY_ONLY_NO_EFFECT", "operation": self._scope["operation"],
                "policy_sha256": self._scope["policy_sha256"],
                "parent_unknown_request_sha256": _PARENT,
                "preparation_ref": ref, "preparation_sha256": pin,
                "context_sha256": request["context_sha256"],
                "reference_set_sha256": self._scope["reference_set_sha256"],
                "runtime_sha256": self._scope["runtime_sha256"],
                "provider": "OPENAI", "model": wire.model,
                "endpoint": "https://api.openai.com/v1/responses",
                "request_sha256": sha(raw), "request_bytes": len(raw),
                "request_body_utf8": raw.decode("utf-8"),
                "historical_slots": 3, "historical_reserved_usd": "0.2544660",
                "historical_observation_status": "PRIOR_OWNER_METADATA_NOT_RECHECKED",
                "per_call_ceiling_usd": "0.1400000",
                "cumulative_ceiling_usd": "1.9600000",
                "new_cost_bound_usd": None,
                "cost_bound_status": "NOT_ESTABLISHED_FOR_NEW_WINDOW",
                "actual_billed_cost_status": "NOT_ESTABLISHED",
                "new_window_status": "NOT_GRANTED",
                "double_execution_cost_risk": "UNRESOLVED",
                "effect_permitted": False, "new_slots": 0, "provider_calls": 0}
            if self._historical_inspector is not None:
                observed = self._historical_inspector()
                if (observed.get("schema") != "P1-CAMPAIGN-UNKNOWN-OFF-METADATA-1.0"
                    or observed.get("state") != "OFF_RESERVATIONS_OBSERVED_NOT_EFFECT_AUTHORIZED"
                    or observed.get("slots_reserved") != 3
                    or observed.get("unknown_count") != 1
                    or observed.get("reserved_budget_usd") != "0.2544660"
                    or observed.get("effect_permitted") is not False
                    or observed.get("provider_calls") != 0
                    or observed.get("ledger_mutations") != 0):
                    raise ValueError("P1_PILOT_READ_OBSERVATION_REQUIRED")
                # Local conservative candidate: UTF-8 BPE text tokens cannot exceed
                # serialized request bytes; the existing P0 policy adds 10k tokens.
                upper = len(raw) + 10_000
                bound = (Decimal(upper) * Decimal("2.50")
                    + Decimal(4096) * Decimal("12.00")) / Decimal(1_000_000)
                total = Decimal(str(observed["reserved_budget_usd"])) + bound
                result.update(historical_observation_status="FRESH_APPLICATION_LOCKED",
                    historical_observed_at_utc=observed["timestamp_utc"],
                    historical_inspection_plan_sha256=observed["inspection_plan_sha256"],
                    read_scope_sha256=self._read_scope_sha256,
                    local_input_upper_tokens=upper, max_output_tokens=4096,
                    local_price_input_usd_per_million="2.50",
                    local_price_output_usd_per_million="12.00",
                    new_cost_bound_usd=str(bound),
                    combined_reserved_ceiling_usd=str(total),
                    cost_bound_status="LOCAL_CANDIDATE_NOT_ADMITTED_FOR_SEND")
            return result

        endpoint.pilot_preview_execute = preview

    def close(self) -> None:
        pass
