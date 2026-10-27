"""OFF-only P0 generation guard for a manual same-need pilot after UNKNOWN.

The injected observation port owns the original LOCK and historical reads.
This adapter has no transport, credential, reserve, or ON transition.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol, cast

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_pilot_same_need_contract import (
    assess_off,
    validate_off_plan,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_continuation_contract import (
    UnknownContinuation,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    P0UnknownOffReader,
)


class PilotHistoricalObservationPort(Protocol):
    def locked(self) -> AbstractContextManager[None]: ...

    def pilot_snapshot(self) -> Mapping[str, object]: ...


class PilotHistoricalLedgerPort(Protocol):
    root: Path

    def locked(self) -> AbstractContextManager[None]: ...

    def chain(self) -> BoundChainV2: ...

    def operation_context(self) -> UnknownContinuation: ...

    def slots(self) -> list[dict[str, object]]: ...


class P0PilotUnknownHistoryObservation:
    """Translate the existing locked UNKNOWN ledger into bounded OFF metadata."""

    def __init__(self, ledger: PilotHistoricalLedgerPort) -> None:
        self._ledger = ledger

    def locked(self) -> AbstractContextManager[None]:
        return self._ledger.locked()

    def pilot_snapshot(self) -> Mapping[str, object]:
        chain = self._ledger.chain()  # Enforces the retained original LOCK.
        context = self._ledger.operation_context()
        records = self._ledger.slots()  # Revalidates all historical bytes and identities.
        classes = {str(row["namespace_sha256"]): str(row["classification"]) for row in
            cast(list[Mapping[str, object]], context.historical_manifest["expected_slots"])}
        terminal = {"UNKNOWN": "UNKNOWN", "KNOWN_REJECTED": "PARSING_REJECTED", "CONSUMED": "CONSUMED"}
        slots: list[dict[str, object]] = []
        for record in records:
            namespace = str(record["namespace_sha256"])
            classification = classes.get(namespace)
            if classification not in terminal:
                raise ValueError("P1_PILOT_SLOT_CLASSIFICATION_REQUIRED")
            _, hashes = P0UnknownOffReader._files(self._ledger.root, namespace, {terminal[classification]})
            slots.append({"namespace_sha256": namespace, "slot_sha256": sha(canonical(record)),
                "request_sha256": record["request_sha256"], "classification": classification,
                "reserved_usd": record["reserved_usd"], "terminal_receipt_sha256": hashes[terminal[classification]]})
        return {"schema": "P1-PILOT-HISTORICAL-OBSERVATION-1.0",
            "campaign_namespace_sha256": chain.manifest["campaign_namespace_sha256"],
            "original_lock_sha256": chain.manifest["root_lock_sha256"],
            "frozen_inventory": context.history["frozen_inventory"], "slots": slots,
            "actual_billed_cost_status": "NOT_ESTABLISHED"}


class P0PilotSameNeedOffGeneration:
    def __init__(self, *, plan: Mapping[str, object], historical: PilotHistoricalObservationPort) -> None:
        validate_off_plan(plan)
        self._plan = dict(plan)
        self._plan_sha256 = sha(canonical(plan))
        self._historical = historical

    def inspect(self) -> dict[str, object]:
        if sha(canonical(self._plan)) != self._plan_sha256:
            raise ValueError("P1_PILOT_OFF_PLAN_CHANGED")
        with self._historical.locked():
            observation = self._historical.pilot_snapshot()
            result = assess_off(self._plan, observation)
            # Re-read before releasing the retained LOCK; an observer may not
            # manufacture availability from a moving inventory.
            if canonical(observation) != canonical(self._historical.pilot_snapshot()):
                raise ValueError("P1_PILOT_OFF_OBSERVATION_CHANGED")
            return result

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        if (request.get("context_sha256") != self._plan["context_sha256"]
            or sha(canonical(request.get("references"))) != self._plan["reference_set_sha256"]
            or sha(canonical(request)) != self._plan["new_preparation_sha256"]):
            raise ValueError("P1_PILOT_OFF_PREPARATION_CHANGED")
        self.inspect()
        return False

    def preview(self, *, request: Mapping[str, object], preparation_ref: str,
                preparation_sha256: str) -> dict[str, object]:
        """Project exact provider bytes after the historical OFF guard, without a grant."""
        if (type(preparation_ref) is not str or not preparation_ref.startswith("prep:")
            or preparation_sha256 != sha(canonical(request))):
            raise ValueError("P1_PILOT_OFF_PREPARATION_CHANGED")
        if self.authorize(request=request):
            raise ValueError("P1_PILOT_OFF_EFFECT_FORBIDDEN")
        wire = build_p0_content_request(request)
        raw = NormalP0GenerationAdapter.body(wire)
        parent = self._plan["parent_unknown"]
        assert isinstance(parent, Mapping)
        return {"schema": "P1-PILOT-SAME-NEED-PREVIEW-OFF-1.0",
            "state": "OFF_PREVIEW_NO_EFFECT", "operation": self._plan["operation"],
            "policy_sha256": self._plan["policy_sha256"],
            "parent_unknown_request_sha256": parent["request_sha256"],
            "preparation_ref": preparation_ref, "preparation_sha256": preparation_sha256,
            "context_sha256": request["context_sha256"],
            "reference_set_sha256": sha(canonical(request["references"])),
            "provider": "OPENAI", "model": wire.model,
            "endpoint": "https://api.openai.com/v1/responses",
            "request_sha256": sha(raw), "request_bytes": len(raw),
            "request_body_utf8": raw.decode("utf-8"),
            "historical_slots": 3, "historical_reserved_usd": self._plan["historical_reserved_usd"],
            "per_call_ceiling_usd": self._plan["per_call_ceiling_usd"],
            "cumulative_ceiling_usd": self._plan["cumulative_ceiling_usd"],
            "cost_bound_status": "NOT_ESTABLISHED_FOR_NEW_WINDOW",
            "actual_billed_cost_status": "NOT_ESTABLISHED",
            "new_window_status": "NOT_GRANTED", "double_execution_cost_risk": "UNRESOLVED",
            "effect_permitted": False, "new_slots": 0, "provider_calls": 0}

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        raise ValueError("P1_PILOT_OFF_NO_EFFECT")
