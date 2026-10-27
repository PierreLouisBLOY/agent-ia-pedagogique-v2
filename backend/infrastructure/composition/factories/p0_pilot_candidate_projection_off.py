"""One selected, recoverable pilot preview; no generation or P1 effect authority."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import cast

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.persistence.p0_pilot_candidate_off import P0PilotCandidateOffStore
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService

_PARENT = "176b136b4f80b11009d93713fa85e7805c851ad3c466b609a43e45c7fa84cf2b"
_POLICY = "d1ac715fa05ae5acc96d987178737f4a7694063048e68060124ef065ae938a72"
_FIELDS = {"schema", "operation", "policy_sha256", "parent_unknown_request_sha256",
    "previous_body_scope_sha256", "read_scope_sha256", "runtime_sha256",
    "context_sha256", "reference_set_sha256", "question_ref", "effect_authorized",
    "provider_calls_allowed", "max_candidate_bytes"}


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


class P0PilotCandidateProjectionOffComposition:
    generation = None

    def __init__(self, *, scope: Mapping[str, object], runtime_sha256: str,
        read_scope_sha256: str, historical_inspector: Callable[[], dict[str, object]],
        store: P0PilotCandidateOffStore) -> None:
        data = object_data(scope, _FIELDS)
        if (data["schema"] != "P1-PILOT-CANDIDATE-SCOPE-OFF-1.0"
            or data["operation"] != "ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN"
            or data["policy_sha256"] != _POLICY
            or data["parent_unknown_request_sha256"] != _PARENT
            or data["runtime_sha256"] != runtime_sha256
            or data["read_scope_sha256"] != read_scope_sha256
            or data["effect_authorized"] is not False
            or type(data["provider_calls_allowed"]) is not int
            or data["provider_calls_allowed"] != 0
            or type(data["max_candidate_bytes"]) is not int
            or not 0 < data["max_candidate_bytes"] <= 512_000
            or any(not _digest(data[key]) for key in (
                "previous_body_scope_sha256", "context_sha256", "reference_set_sha256"))
            or type(data["question_ref"]) is not str
            or not 1 <= len(data["question_ref"]) <= 256):
            raise ValueError("P0_PILOT_CANDIDATE_SCOPE_REJECTED")
        self._scope = data
        self._inspect = historical_inspector
        self._store = store

    def _request(self, record: Mapping[str, object]) -> tuple[dict[str, object], bytes]:
        request = object_data(record)
        if (request.get("context_sha256") != self._scope["context_sha256"]
            or sha(canonical(request.get("references"))) != self._scope["reference_set_sha256"]):
            raise ValueError("P0_PILOT_CANDIDATE_CONTEXT_CHANGED")
        context = object_data(request["context"])
        institutional = object_data(context["institutional"])
        if (context.get("resource_type") != "COURSE"
            or context.get("course_format") != "CHAPTER"
            or context.get("level") != "FIRST_STMG"
            or institutional.get("frame") != "SGN_PREMIERE"
            or institutional.get("question_ref") != self._scope["question_ref"]):
            raise ValueError("P0_PILOT_CANDIDATE_NEED_CHANGED")
        wire = build_p0_content_request(request)
        if wire.model != "gpt-5.6-terra" or wire.max_output_tokens != 4096:
            raise ValueError("P0_PILOT_CANDIDATE_PROFILE_CHANGED")
        raw = NormalP0GenerationAdapter.body(wire)
        if not 0 < len(raw) <= cast(int, self._scope["max_candidate_bytes"]):
            raise ValueError("P0_PILOT_CANDIDATE_BODY_SIZE")
        return request, raw

    def _preview(self, request: Mapping[str, object], ref: str, pin: str,
        raw: bytes, observed: Mapping[str, object]) -> dict[str, object]:
        if (observed.get("schema") != "P1-CAMPAIGN-UNKNOWN-OFF-METADATA-1.0"
            or observed.get("state") != "OFF_RESERVATIONS_OBSERVED_NOT_EFFECT_AUTHORIZED"
            or observed.get("slots_reserved") != 3
            or observed.get("unknown_count") != 1
            or observed.get("reserved_budget_usd") != "0.2544660"
            or observed.get("effect_permitted") is not False
            or observed.get("provider_calls") != 0
            or observed.get("ledger_mutations") != 0):
            raise ValueError("P0_PILOT_CANDIDATE_OBSERVATION_REJECTED")
        upper = len(raw) + 10_000
        bound = (Decimal(upper) * Decimal("2.50")
            + Decimal(4096) * Decimal("12.00")) / Decimal(1_000_000)
        combined = Decimal(str(observed["reserved_budget_usd"])) + bound
        return {"schema": "P1-PILOT-CANDIDATE-PREVIEW-OFF-1.0",
            "state": "OFF_CANDIDATE_NO_EFFECT",
            "operation": self._scope["operation"], "policy_sha256": _POLICY,
            "parent_unknown_request_sha256": _PARENT,
            "preparation_ref": ref, "preparation_sha256": pin,
            "context_sha256": request["context_sha256"],
            "reference_set_sha256": self._scope["reference_set_sha256"],
            "runtime_sha256": self._scope["runtime_sha256"],
            "provider": "OPENAI", "model": "gpt-5.6-terra",
            "endpoint": "https://api.openai.com/v1/responses",
            "request_sha256": sha(raw), "request_bytes": len(raw),
            "request_body_utf8": raw.decode("utf-8"),
            "historical_slots": 3,
            "historical_reserved_usd": observed["reserved_budget_usd"],
            "historical_observation_status": "FRESH_APPLICATION_LOCKED",
            "historical_observed_at_utc": observed["timestamp_utc"],
            "historical_inspection_plan_sha256": observed["inspection_plan_sha256"],
            "read_scope_sha256": self._scope["read_scope_sha256"],
            "local_input_upper_tokens": upper, "max_output_tokens": 4096,
            "local_price_input_usd_per_million": "2.50",
            "local_price_output_usd_per_million": "12.00",
            "new_cost_bound_usd": str(bound),
            "combined_reserved_ceiling_usd": str(combined),
            "per_call_ceiling_usd": "0.1400000",
            "cumulative_ceiling_usd": "1.9600000",
            "cost_bound_status": "LOCAL_CANDIDATE_NOT_ADMITTED_FOR_SEND",
            "actual_billed_cost_status": "NOT_ESTABLISHED",
            "new_window_status": "NOT_GRANTED",
            "double_execution_cost_risk": "UNRESOLVED",
            "effect_permitted": False, "new_slots": 0, "provider_calls": 0}

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        if service.generation is not None or endpoint.consent_execute is not None:
            raise ValueError("P0_PILOT_CANDIDATE_EFFECT_FORBIDDEN")
        endpoint.generation_bound = False
        endpoint.consent_execute = None
        endpoint.campaign_snapshot = None

        def select(payload: Mapping[str, object]) -> dict[str, object]:
            data = object_data(payload, {"command_id", "preparation_ref",
                "preparation_sha256", "demand"})
            command, ref, pin, demand = (data[key] for key in (
                "command_id", "preparation_ref", "preparation_sha256", "demand"))
            if (type(command) is not str or len(command) != 32
                or any(char not in "0123456789abcdef" for char in command)
                or type(ref) is not str or not ref.startswith("prep:")
                or not _digest(pin) or type(demand) is not str
                or not 1 <= len(demand) <= 2048):
                raise ValueError("P0_PILOT_CANDIDATE_IDENTITY")
            existing = self._store.read()
            if existing is not None:
                if existing["preparation_ref"] != ref or existing["preparation_sha256"] != pin:
                    raise ValueError("P0_PILOT_CANDIDATE_CONFLICT")
                return cast(dict[str, object], self._restore(existing)["preview"])
            request = service.prepared.get(ref)
            if request is None or fingerprint(request) != pin:
                raise ValueError("P0_PREPARATION_CHANGED")
            checked, raw = self._request(request)
            observed = self._inspect()
            preview = self._preview(checked, ref, pin, raw, observed)
            record = {"schema": "P1-PILOT-CANDIDATE-OFF-1.0", "demand": demand,
                "request": as_plain(checked), "preparation_ref": ref,
                "preparation_sha256": pin, "preview": preview}
            self._store.publish(record)
            return preview

        endpoint.pilot_preview_execute = select
        endpoint.pilot_candidate_read = lambda: self._restore(self._store.read())

    def _restore(self, record: dict[str, object] | None) -> dict[str, object]:
        if record is None:
            return {"state": "NO_CANDIDATE"}
        request, raw = self._request(object_data(record["request"]))
        saved = object_data(record["preview"])
        if (fingerprint(request) != record["preparation_sha256"]
            or saved.get("request_sha256") != sha(raw)
            or saved.get("request_bytes") != len(raw)
            or saved.get("request_body_utf8") != raw.decode("utf-8")
            or saved.get("parent_unknown_request_sha256") != _PARENT
            or saved.get("read_scope_sha256") != self._scope["read_scope_sha256"]):
            raise ValueError("P0_PILOT_CANDIDATE_INTEGRITY")
        preview = dict(saved)
        preview["historical_observation_status"] = "PRIOR_APPLICATION_OBSERVATION"
        return {"state": "OFF_CANDIDATE_RESTORED", "demand": record["demand"],
            "prepared": {"state": "PREPARATION_READY", "authorization": "REQUIRED",
                "preparation_ref": record["preparation_ref"],
                "preparation_sha256": record["preparation_sha256"],
                "context": as_plain(request["context"]),
                "references": as_plain(request["references"]), "provider_attempts": 0},
            "preview": preview}

    def close(self) -> None:
        pass
