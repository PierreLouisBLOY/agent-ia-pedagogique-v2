"""Fail-closed pilot consent gate. A real broker/authority is injected explicitly.

This module never constructs a provider transport, credential, grant or receipt.
The historical OFF composition does not instantiate it.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, money, sha, utc
from backend.adapters.outbound.generation.openai.p0_product_policy import PREVIEW_FIELDS
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain


class PilotEffectBroker(Protocol):
    def preview(self, *, request: Mapping[str, object], preparation_ref: str,
                preparation_sha256: str, source_receipts: Sequence[Mapping[str, object]]) -> Mapping[str, object]: ...
    def accept(self, *, request: Mapping[str, object], consent: Mapping[str, object],
               source_receipts: Sequence[Mapping[str, object]]) -> None: ...
    def authorize(self, *, request: Mapping[str, object]) -> bool: ...
    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]: ...
    def confirmed_dispatches(self) -> tuple[Mapping[str, object], ...]: ...
    def recover_confirmed(self, *, request: Mapping[str, object]) -> Mapping[str, object]: ...
    def control_evidence(self, *, request: Mapping[str, object], bundle_sha256: str) -> Mapping[str, object]: ...


class P0PilotEffectGate:
    """Checks an exact adopted authority at each transition; owns no authority."""

    def __init__(self, *, broker: PilotEffectBroker, authority: Callable[[], Mapping[str, object]],
                 candidate_request_sha256: str, candidate_preparation_sha256: str,
                 parent_unknown_request_sha256: str,
                 approved_cost_bound_usd: str = "0.1237945",
                 expected_operation: str = "ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN",
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._broker, self._authority, self._clock = broker, authority, clock
        self._request_sha256 = candidate_request_sha256
        self._preparation_sha256 = candidate_preparation_sha256
        self._parent_sha256 = parent_unknown_request_sha256
        self._approved_cost_bound = money(approved_cost_bound_usd)
        if expected_operation not in {"ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN",
            "ONE_ADDITIONAL_MANUAL_CREATE_AFTER_406A", "ONE_ADDITIONAL_MANUAL_CREATE_AFTER_2F1E"}:
            raise ValueError("P1_PILOT_EFFECT_OPERATION_REQUIRED")
        self._expected_operation = expected_operation
        if self._approved_cost_bound <= 0 or self._approved_cost_bound > money("0.14"):
            raise ValueError("P1_PILOT_APPROVED_COST_BOUND_REQUIRED")
        self._mutex = threading.Lock()
        self._previews: dict[str, dict[str, object]] = {}
        self._preview_authorities: dict[str, str] = {}
        self._retired_preview_hashes: set[str] = set()
        self._pending: tuple[str, str, str] | None = None
        self._authorized = False
        self._dispatch_thread: int | None = None
        self._dispatch_command: str | None = None

    def dispatch(self, *, command_id: str, run: Callable[[], dict[str, object]]) -> dict[str, object]:
        """Only the accepted Application consent invocation may consume its slot."""
        with self._mutex:
            if (self._pending is None or self._pending[1] != command_id
                or self._dispatch_thread is not None):
                raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
            self._dispatch_thread = threading.get_ident()
            self._dispatch_command = command_id
        try:
            return run()
        finally:
            with self._mutex:
                self._dispatch_thread = None
                self._dispatch_command = None
                # A reserved slot is never made available by an Application error.
                self._pending = None
                self._authorized = False

    def _check(self, request: Mapping[str, object]) -> Mapping[str, object]:
        from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
        from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter

        raw = NormalP0GenerationAdapter.body(build_p0_content_request(request))
        if sha(raw) != self._request_sha256 or sha(canonical(as_plain(request))) != self._preparation_sha256:
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        authority = self._authority()
        now = self._clock()
        required = {"schema", "operation", "effect_authorized", "permission_sha256",
            "request_sha256", "preparation_sha256", "parent_unknown_request_sha256",
            "tariff_admitted", "tokenizer_verified", "historical_locked_verified",
            "issued_at_utc", "expires_at_utc", "max_calls", "retry", "fallback"}
        if (set(authority) != required or authority.get("schema") != "P1-PILOT-EFFECT-AUTHORITY-1.0"
            or authority.get("operation") != self._expected_operation
            or authority.get("effect_authorized") is not True
            or authority.get("request_sha256") != self._request_sha256
            or authority.get("preparation_sha256") != self._preparation_sha256
            or authority.get("parent_unknown_request_sha256") != self._parent_sha256
            or any(authority.get(k) is not True for k in (
                "tariff_admitted", "tokenizer_verified", "historical_locked_verified"))
            or type(authority.get("max_calls")) is not int or authority["max_calls"] != 1
            or type(authority.get("retry")) is not int or authority["retry"] != 0
            or authority.get("fallback") != "NONE"
            or not isinstance(authority.get("permission_sha256"), str)
            or len(cast(str, authority["permission_sha256"])) != 64
            or not isinstance(authority.get("issued_at_utc"), str)
            or not isinstance(authority.get("expires_at_utc"), str)
            or not utc(cast(str, authority["issued_at_utc"])) <= now < utc(cast(str, authority["expires_at_utc"]))
            or utc(cast(str, authority["expires_at_utc"])) - utc(cast(str, authority["issued_at_utc"])) > timedelta(minutes=60)):
            raise ValueError("P1_PILOT_EFFECT_AUTHORITY_REQUIRED")
        return authority

    def validate_current_authority(self, request: Mapping[str, object]) -> None:
        """Final check after credential resolution and immediately before ATTEMPTED."""
        self._check(request)

    def confirmed_dispatches(self) -> tuple[Mapping[str, object], ...]:
        return self._broker.confirmed_dispatches()

    def confirmed_dispatch(self) -> Mapping[str, object] | None:
        records = self.confirmed_dispatches()
        if len(records) > 1:
            raise ValueError("P1_PILOT_MULTIPLE_CHILDREN_STOP")
        return records[0] if records else None

    def recover_confirmed(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        return self._broker.recover_confirmed(request=request)

    def control_evidence(self, *, request: Mapping[str, object], bundle_sha256: str) -> Mapping[str, object]:
        return self._broker.control_evidence(request=request, bundle_sha256=bundle_sha256)

    def preview(self, *, request: Mapping[str, object], preparation_ref: str,
                preparation_sha256: str, source_receipts: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
        with self._mutex:
            authority = self._check(request)
            if preparation_sha256 != self._preparation_sha256 or self._pending is not None:
                raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
            # An unconsumed local preview is replaceable. Its former consent
            # digest is invalidated before another broker preflight is read.
            self._retired_preview_hashes.update(self._previews)
            self._previews.clear()
            self._preview_authorities.clear()
            from backend.adapters.outbound.generation.openai.p0_content import (
                build_p0_content_request,
            )
            from backend.adapters.outbound.generation.openai.p0_normal import (
                NormalP0GenerationAdapter,
            )

            raw = NormalP0GenerationAdapter.body(build_p0_content_request(request))
            try:
                result = dict(self._broker.preview(request=request, preparation_ref=preparation_ref,
                    preparation_sha256=preparation_sha256, source_receipts=source_receipts))
            except Exception:
                raise ValueError("P1_PILOT_OPERATION_STOP") from None
            preview = result.get("preview")
            if (not isinstance(preview, Mapping)
                or set(preview) != PREVIEW_FIELDS
                or result.get("state") != "LOCAL_OPERATOR_CONSENT_REQUIRED"
                or preview.get("request_sha256") != self._request_sha256
                or preview.get("request_bytes") != len(raw)
                or preview.get("request_body_utf8") != raw.decode("utf-8")
                or preview.get("preparation_sha256") != self._preparation_sha256
                or preview.get("preparation_ref") != preparation_ref
                or preview.get("context_sha256") != request.get("context_sha256")
                or preview.get("reference_set_sha256") != sha(canonical(as_plain(request.get("references"))))
                or canonical(preview.get("source_receipts")) != canonical(as_plain(source_receipts))
                or preview.get("permission_sha256") != authority["permission_sha256"]
                or result.get("provider_attempts") != 0
                or result.get("preview_sha256") != sha(canonical(preview))
                or result.get("preview_sha256") in self._retired_preview_hashes
                or not isinstance(preview.get("preflight"), Mapping)
                or preview.get("cost_bound_usd") != preview["preflight"].get("cost_bound_usd")
                or preview["preflight"].get("request_sha256") != self._request_sha256
                or not isinstance(preview.get("cost_bound_usd"), str)
                or money(preview["cost_bound_usd"]) > self._approved_cost_bound):
                raise ValueError("P1_PILOT_EFFECT_PREVIEW_BINDING")
            self._previews[str(result["preview_sha256"])] = result
            self._preview_authorities[str(result["preview_sha256"])] = sha(canonical(authority))
            return result

    def accept(self, *, request: Mapping[str, object], consent: Mapping[str, object],
               source_receipts: Sequence[Mapping[str, object]]) -> None:
        with self._mutex:
            authority = self._check(request)
            key = consent.get("preview_sha256")
            preview_result = self._previews.get(str(key))
            if (set(consent) != {"command_id", "preparation_ref", "preparation_sha256",
                    "preview_sha256", "transfer_accepted", "cost_bound_accepted",
                    "double_execution_cost_risk_accepted"}
                or preview_result is None or self._pending is not None
                or self._preview_authorities.get(str(key)) != sha(canonical(authority))
                or any(consent.get(k) is not True for k in (
                    "transfer_accepted", "cost_bound_accepted", "double_execution_cost_risk_accepted"))
                or consent.get("preparation_sha256") != self._preparation_sha256
                or consent.get("preparation_ref") != cast(Mapping[str, object], preview_result["preview"]).get("preparation_ref")
                or cast(Mapping[str, object], preview_result["preview"]).get("permission_sha256") != authority["permission_sha256"]):
                raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
            # The injected pilot broker must independently recheck the same
            # consent, original LOCK, frozen inventory, fresh proof and cumul.
            self._previews.pop(str(key))  # Consumed even if reservation fails or its outcome is uncertain.
            self._preview_authorities.pop(str(key), None)
            try:
                self._broker.accept(request=request, consent=consent, source_receipts=source_receipts)
            except Exception:
                raise ValueError("P1_PILOT_OPERATION_STOP") from None
            self._pending = (sha(canonical(as_plain(request))), str(consent["command_id"]),
                sha(canonical(authority)))
            self._authorized = False

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        with self._mutex:
            if (self._pending is None or self._pending[0] != sha(canonical(as_plain(request)))
                or self._dispatch_thread != threading.get_ident()
                or self._dispatch_command != self._pending[1]):
                return False
            try:
                authority = self._check(request)
                if sha(canonical(authority)) != self._pending[2]:
                    raise ValueError("P1_PILOT_EFFECT_AUTHORITY_CHANGED")
                allowed = self._broker.authorize(request=request)
                if allowed is not True:
                    self._pending = None
                    self._authorized = False
                    return False
                self._authorized = True
                return True
            except Exception:
                self._pending = None
                self._authorized = False
                raise ValueError("P1_PILOT_OPERATION_STOP") from None

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        with self._mutex:
            if (self._pending is None or not self._authorized
                or self._pending[0] != sha(canonical(as_plain(request)))
                or self._dispatch_thread != threading.get_ident()
                or self._dispatch_command != self._pending[1]):
                raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
            accepted_authority_sha256 = self._pending[2]
            self._pending = None  # Never replay after a transport or process error.
            self._authorized = False
            authority = self._check(request)
            if sha(canonical(authority)) != accepted_authority_sha256:
                raise ValueError("P1_PILOT_EFFECT_AUTHORITY_CHANGED")
            try:
                return self._broker.generate(request=request)
            except Exception:
                # A child is already reserved. The transport or local result
                # may have failed after an attempt, so never report refusal.
                raise ValueError("P0_OUTCOME_UNKNOWN") from None
