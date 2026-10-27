"""Finite consent/effect broker over the existing campaign ledger and LOCK."""

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import RLock, get_ident
from typing import cast

from backend.adapters.outbound.generation.openai.p0_finite_policy import (
    GRANT,
    ROLES,
    SLOT,
    financial_proof,
    validate_policy,
    validate_slot,
)
from backend.adapters.outbound.generation.openai.p0_finite_receipts import FiniteEffectReceipt
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    validate_events,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
)
from backend.agent_runtime.agents.review import ReviewOperation
from backend.infrastructure.filesystem import (
    capture_secure_path,
    hash_file_nofollow,
    read_file_nofollow,
)

CONSENT_FIELDS = {
    "command_id",
    "production_ref",
    "version_ref",
    "bundle_sha256",
    "direction",
    "objective",
    "evidence_query",
    "preview_sha256",
    "transfer_accepted",
    "cost_bound_accepted",
}


def request_identity(request: Mapping[str, object]) -> str:
    return sha(
        canonical(
            {
                key: value
                for key, value in request.items()
                if key not in {"command_id", "correction_parent_sha256", "correction_review_sha256"}
            }
        )
    )


class FiniteChainBroker:
    def __init__(
        self,
        *,
        ledger: P0ProductLedger,
        policy: Mapping[str, object],
        decision: Mapping[str, object],
        enabled: bool,
        revalidate: Callable[[], object],
        revalidate_authority: Callable[[], object] | None = None,
        source_reader: Callable[[Mapping[str, object]], list[dict[str, object]]],
        initial_wire: Callable[[Mapping[str, object]], OpenAIResponsesRequest],
        tokenizer: Callable[[bytes], Mapping[str, object]],
        tariff: Mapping[str, object],
        prepare_credential: Callable[[], object],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.ledger, self.policy, self.decision = ledger, dict(policy), dict(decision)
        self.enabled, self.revalidate = enabled, revalidate
        self.revalidate_authority = revalidate_authority
        self.sources, self.initial_wire, self.tokenizer, self.tariff = (
            source_reader,
            initial_wire,
            tokenizer,
            dict(tariff),
        )
        self.prepare_credential, self.clock = prepare_credential, clock
        self.policy_sha, self.decision_sha = sha(canonical(policy)), sha(canonical(decision))
        self.previews: dict[str, dict[str, object]] = {}
        self.observer = RLock()
        self.active: dict[str, object] | None = None
        self.pending_command: str | None = None
        self.current: FiniteEffectReceipt | None = None
        self.context: tuple[str, str] | None = None
        self.results: dict[str, dict[str, object]] = {}
        self.read_only_thread: int | None = None
        if ledger.finite_extension is not None:
            raise ValueError("P0_CHAIN_LEDGER_ALREADY_BOUND")
        ledger.finite_extension = self
        self.revalidate()
        validate_policy(
            self.policy,
            self.decision,
            self.ledger.permission,
            now=min(self.clock(), utc(self.policy["expires_at_utc"]) - timedelta(microseconds=1)),
            proposed=self.decision["status"] == "PROPOSED",
        )

    def _policy(self, *, full: bool = True) -> None:
        if full or self.revalidate_authority is None:
            self.revalidate()
        else:
            self.revalidate_authority()
        validate_policy(
            self.policy,
            self.decision,
            self.ledger.permission,
            now=self.clock(),
            proposed=self.decision["status"] == "PROPOSED",
        )
        if capture_secure_path(self._revocation_path(), allowed_root=self.ledger.root).exists:
            raise ValueError("P0_CHAIN_REVOKED")

    def _revocation_path(self) -> Path:
        return self.ledger.root / ("chain-revocation." + self.policy_sha + ".json")

    def _lock_identity(self) -> None:
        lock = self.ledger.root / (self.ledger.prefix + "LOCK")
        identity = capture_secure_path(lock, allowed_root=self.ledger.root)
        if not identity.exists:
            raise ValueError("P0_CHAIN_ORIGINAL_LOCK_REQUIRED")
        value = sha(canonical({"device": identity.device, "inode": identity.inode}))
        if value != self.policy["root_lock_identity_sha256"]:
            raise ValueError("P0_CHAIN_LOCK_IDENTITY_CHANGED")
        if (
            self.ledger._held_thread == get_ident()
            and self.ledger._held_lock_sha256 != self.policy["root_lock_sha256"]
        ):
            raise ValueError("P0_CHAIN_LOCK_BYTES_CHANGED")

    def _open_lock(self) -> None:
        self._lock_identity()
        raw = read_file_nofollow(
            self.ledger.root / (self.ledger.prefix + "LOCK"),
            allowed_root=self.ledger.root,
            maximum_bytes=1000,
        )
        if sha(raw) != self.policy["root_lock_sha256"]:
            raise ValueError("P0_CHAIN_LOCK_BYTES_CHANGED")

    def _proof(self, wire: OpenAIResponsesRequest) -> tuple[bytes, dict[str, object]]:
        raw = NormalP0GenerationAdapter.body(wire)
        return raw, financial_proof(
            raw, policy=self.policy, tariff=self.tariff, tokenizer=self.tokenizer(raw)
        )

    def _budget(
        self, slots: list[dict[str, object]], *, remaining: int, next_bound: Decimal
    ) -> None:
        total = sum((money(s["reserved_usd"]) for s in slots), Decimal(0))
        cap = money(self.policy["cumulative_ceiling_usd"])
        if (
            len(slots) + remaining > cast(int, self.policy["max_campaign_effects"])
            or total + next_bound > cap
        ):
            raise ValueError("P0_CHAIN_CUMULATIVE_BUDGET_STOP")

    def preview(self, request: Mapping[str, object]) -> Mapping[str, object]:
        self._policy()
        raw, proof = self._proof(self.initial_wire(request))
        # Disabled profiles do not manufacture source admission receipts.
        sources = self.sources(request) if self.enabled else []
        self._open_lock()
        with self.ledger.locked(create=False):
            self._lock_identity()
            slots = self.ledger.slots()
            if any(s.get("schema") == SLOT for s in slots):
                raise ValueError("P0_CHAIN_RIGHT_ALREADY_CONSUMED")
            per = money(self.policy["per_effect_ceiling_usd"])
            worst = money(proof["cost_bound_usd"]) + 3 * per
            self._budget(slots, remaining=4, next_bound=worst)
        now = self.clock()
        production = cast(Mapping[str, object], request["production"])
        result = {
            "schema": "P0-FINITE-CHAIN-PREVIEW-1.0",
            "state": "READY" if self.enabled else "DISARMED",
            "authority": "NONE",
            "provider_attempts": 0,
            "policy_sha256": self.policy_sha,
            "owner_decision_sha256": self.decision_sha,
            "request_identity_sha256": request_identity(request),
            "production_ref": production["production_ref"],
            "version_ref": production["version_ref"],
            "bundle_sha256": sha(canonical(production)),
            "context_sha256": production["context_sha256"],
            "references": production["references"],
            "source_receipts": sources,
            "source_admission": "OWNER_ADMITTED_EXACT"
            if self.enabled
            else "OWNER_DECISION_PENDING",
            "direction": request["direction"],
            "objective": request["objective"],
            "evidence_query": request["evidence_query"],
            "first_request_body_utf8": raw.decode(),
            "first_request_sha256": sha(raw),
            "first_request_bytes": len(raw),
            "first_preflight": proof,
            "roles": list(ROLES),
            "future_requests": "DERIVED_FROM_VALIDATED_PREVIOUS_OUTPUT_WITHIN_EXACT_POLICY",
            "model": "gpt-5.6-terra",
            "endpoint": "https://api.openai.com/v1/responses",
            "parameters": {
                "reasoning": "low",
                "service_tier": "default",
                "max_output_tokens": 4096,
                "retry": 0,
                "fallback": "NONE",
                "tools": [],
            },
            "maximum_effects": 4,
            "first_bound_usd": proof["cost_bound_usd"],
            "future_effect_ceiling_usd": str(per),
            "chain_bound_usd": str(worst),
            "reserved_budget_usd": str(sum((money(s["reserved_usd"]) for s in slots), Decimal(0))),
            "projected_cumulative_usd": str(
                sum((money(s["reserved_usd"]) for s in slots), Decimal(0)) + worst
            ),
            "snapshot_at_utc": now.isoformat(),
            "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
            "financial_evidence": {
                "tariff_sha256": self.policy["tariff_sha256"],
                "tokenizer_manifest_sha256": self.policy["tokenizer_manifest_sha256"],
                "price_evidence_sha256": self.policy["price_evidence_sha256"],
                "owner_admission": self.decision["financial_evidence_admitted"],
                "input_usd_per_million": self.tariff["input_usd_per_million"],
                "input_multiplier": self.tariff["input_multiplier"],
                "output_usd_per_million": self.tariff["output_usd_per_million"],
                "tariff_observed_at_utc": self.tariff["retrieved_at_utc"],
                "structural_reserve_tokens": 10000,
                "cache_discount_assumed": False,
                "billed_cost": "NOT_ESTABLISHED",
            },
            "historical_origins": [
                {
                    key: s[key]
                    for key in ("command_id", "namespace_sha256", "request_sha256", "reserved_usd")
                }
                for s in slots
            ],
            "historical_scope": "THIS_CAMPAIGN_ROOT_ONLY_OTHER_CAMPAIGNS_NOT_RECONCILED_OR_RELEASED",
            "issued_at_utc": now.isoformat(),
            "expires_at_utc": min(
                now + timedelta(minutes=15), utc(self.policy["expires_at_utc"])
            ).isoformat(),
        }
        key = sha(canonical(result))
        if len(self.previews) >= 64:
            raise ValueError("P0_CHAIN_PREVIEW_CAPACITY")
        self.previews[key] = result
        return {**result, "preview_sha256": key}

    def finalize(
        self,
        *,
        request: Mapping[str, object],
        consent: Mapping[str, object],
        run: Callable[[], Mapping[str, object]],
    ) -> Mapping[str, object]:
        closed(consent, CONSENT_FIELDS, "P0_CHAIN_CONSENT_FIELDS")
        command = str(consent["command_id"])
        with self.observer:
            if self.pending_command is not None:
                raise ValueError("P0_CHAIN_CONCURRENT_COMMAND")
            # Observation only: no authority, secret, LOCK or durable right here.
            self.pending_command = command
        try:
            return self._finalize(request=request, consent=consent, run=run)
        finally:
            with self.observer:
                self.pending_command = None

    def _finalize(
        self,
        *,
        request: Mapping[str, object],
        consent: Mapping[str, object],
        run: Callable[[], Mapping[str, object]],
    ) -> Mapping[str, object]:
        closed(consent, CONSENT_FIELDS, "P0_CHAIN_CONSENT_FIELDS")
        command = consent["command_id"]
        if (
            not isinstance(command, str)
            or len(command) != 32
            or any(c not in "0123456789abcdef" for c in command)
        ):
            raise ValueError("P0_CHAIN_COMMAND_IDENTITY")
        self._policy()
        if (
            not self.enabled
            or self.decision["status"] != "ADOPTED"
            or consent["transfer_accepted"] is not True
            or consent["cost_bound_accepted"] is not True
        ):
            raise ValueError("P0_CHAIN_EXACT_CONSENT_REQUIRED")
        key = str(consent["preview_sha256"])
        preview = self.previews.get(key)
        now = self.clock()
        if (
            preview is None
            or preview["request_identity_sha256"] != request_identity(request)
            or not utc(preview["issued_at_utc"]) <= now < utc(preview["expires_at_utc"])
        ):
            raise ValueError("P0_CHAIN_PREVIEW_CHANGED_OR_EXPIRED")
        if any(
            consent[k] != preview[k]
            for k in (
                "production_ref",
                "version_ref",
                "bundle_sha256",
                "direction",
                "objective",
                "evidence_query",
            )
        ):
            raise ValueError("P0_CHAIN_CONSENT_BINDING")
        sources = self.sources(request)
        if canonical(sources) != canonical(preview["source_receipts"]):
            raise ValueError("P0_CHAIN_SOURCE_CHANGED")
        # No secret resolution before all adoption/revocation/consent checks.
        self.prepare_credential()
        self._open_lock()
        with self.ledger.locked(create=False):
            self._policy()
            self._lock_identity()
            if canonical(self.sources(request)) != canonical(sources):
                raise ValueError("P0_CHAIN_SOURCE_CHANGED")
            slots = self.ledger.slots()
            if any(s.get("schema") == SLOT for s in slots):
                raise ValueError("P0_CHAIN_RIGHT_ALREADY_CONSUMED")
            raw, fresh = self._proof(self.initial_wire(request))
            if sha(raw) != preview["first_request_sha256"] or canonical(fresh) != canonical(
                preview["first_preflight"]
            ):
                raise ValueError("P0_CHAIN_PREFLIGHT_CHANGED")
            self._budget(slots, remaining=4, next_bound=money(preview["chain_bound_usd"]))
            t0 = self.clock()
            if not utc(preview["issued_at_utc"]) <= t0 < utc(preview["expires_at_utc"]):
                raise ValueError("P0_CHAIN_PREVIEW_CHANGED_OR_EXPIRED")
            with self.observer:
                if self.active is not None:
                    raise ValueError("P0_CHAIN_CONCURRENT_COMMAND")
                self.active = {
                    "thread": get_ident(),
                    "command_id": consent["command_id"],
                    "request_sha256": request_identity(request),
                    "preview_sha256": key,
                    "consent_sha256": sha(canonical(consent)),
                    "plan_sha256": sha(canonical({"policy": self.policy_sha, "preview": key})),
                    "parent_sha256": preview["bundle_sha256"],
                    "issued_at_utc": t0.isoformat(),
                    "expires_at_utc": min(
                        t0 + timedelta(minutes=60), utc(self.policy["expires_at_utc"])
                    ).isoformat(),
                    "slots": [],
                    "staged_slot": None,
                    "phase": "PREFLIGHT_CHECKED",
                    "can_correct": False,
                    "first_request_sha256": sha(raw),
                    "preview": preview,
                    "consent": dict(consent),
                }
            self.previews.pop(key)
            try:
                result = dict(run())
                result["financial"] = self._summary()
                with self.observer:
                    self.results[str(consent["command_id"])] = result
                return result
            finally:
                with self.observer:
                    self.active = None
                    self.context = None
                    self.current = None

    def authorize_chain(self, request: Mapping[str, object]) -> bool:
        self._live()
        assert self.active is not None
        return self.active["command_id"] == request["command_id"] and self.active[
            "request_sha256"
        ] == request_identity(request)

    def _live(self) -> None:
        self._policy(full=False)
        if (
            not self.enabled
            or self.decision["status"] != "ADOPTED"
            or self.active is None
            or self.active["thread"] != get_ident()
            or self.ledger._held_thread != get_ident()
            or not self.clock() < utc(self.active["expires_at_utc"])
        ):
            raise ValueError("P0_CHAIN_LIVING_AUTHORITY_REQUIRED")

    def enter_port(self, *, role: str, step_id: str) -> None:
        self._live()
        # The next adapter must never annotate the previous effect's receipt.
        self.current = None
        assert self.active is not None
        own = cast(list[dict[str, object]], self.active["slots"])
        if (
            len(own) >= 4
            or role != ROLES[len(own)]
            or (role == "CORRECT" and self.active["can_correct"] is not True)
        ):
            raise ValueError("P0_CHAIN_ROLE_ORDER")
        self.context = (role, step_id)

    def dispatch(
        self, wire: OpenAIResponsesRequest, call: Callable[[], OpenAIResponsesResponse]
    ) -> OpenAIResponsesResponse:
        self._live()
        assert self.active is not None
        if self.context is None:
            raise ValueError("P0_CHAIN_EFFECT_CONTEXT_REQUIRED")
        role, step_id = self.context
        expected_schema = (
            "technical_pedagogical_review"
            if role in {"REVIEW_INITIAL", "REVIEW_CORRECTED"}
            else "p0_codesign_content"
        )
        expected_operation = (
            ReviewOperation.SEMANTIC_REVIEW.value
            if role in {"REVIEW_INITIAL", "REVIEW_CORRECTED"}
            else "CORRECT"
            if role == "CORRECT"
            else "TRANSFORM"
            if cast(Mapping[str, object], self.active["preview"])["direction"] == "V2_TO_AI"
            else "GENERATE"
        )
        payload = json.loads(wire.input_json)
        if (
            wire.schema_name != expected_schema
            or not isinstance(payload, dict)
            or payload.get("operation") != expected_operation
        ):
            raise ValueError("P0_CHAIN_ROLE_WIRE_BINDING")
        own = cast(list[dict[str, object]], self.active["slots"])
        ordinal = len(own)
        shown = cast(Mapping[str, object], self.active["preview"])
        if ordinal == 0 and not self.clock() < utc(shown["expires_at_utc"]):
            raise ValueError("P0_CHAIN_PREVIEW_CHANGED_OR_EXPIRED")
        raw, proof = self._proof(wire)
        # Full package/SDK/source validation after counting, before reservation.
        self._policy()
        if ordinal == 0 and sha(raw) != self.active["first_request_sha256"]:
            raise ValueError("P0_CHAIN_FIRST_BODY_CHANGED")
        slots = self.ledger.slots()
        future = 3 - ordinal
        self._budget(
            slots,
            remaining=1 + future,
            next_bound=money(proof["cost_bound_usd"])
            + Decimal(future) * money(self.policy["per_effect_ceiling_usd"]),
        )
        command = str(self.active["command_id"])
        key = sha(canonical({"chain": command, "ordinal": ordinal, "policy": self.policy_sha}))
        effect_id = sha(
            canonical(
                {
                    "consent": self.active["consent_sha256"],
                    "ordinal": ordinal,
                    "policy": self.policy_sha,
                }
            )
        )[:32]
        grant = {
            "schema": GRANT,
            "policy_sha256": self.policy_sha,
            "owner_decision_sha256": self.decision_sha,
            "normal_permission_sha256": self.ledger.permission_sha256,
            "campaign_namespace_sha256": self.policy["campaign_namespace_sha256"],
            "namespace_sha256": sha(canonical({"policy": self.policy_sha, "effect": effect_id})),
            "chain_command_id": command,
            "effect_id": effect_id,
            "ordinal": ordinal,
            "role": role,
            **{
                k: self.active[k]
                for k in ("preview_sha256", "consent_sha256", "plan_sha256", "parent_sha256")
            },
            "request_sha256": sha(raw),
            "request_bytes": len(raw),
            "preflight_sha256": sha(canonical(proof)),
            "issued_at_utc": self.clock().isoformat(),
            "authority_issued_at_utc": self.active["issued_at_utc"],
            "expires_at_utc": self.active["expires_at_utc"],
            "ceiling_usd": self.policy["per_effect_ceiling_usd"],
            "step_id": step_id,
        }
        slot = {
            "schema": SLOT,
            "permission_sha256": self.ledger.permission_sha256,
            "preview_sha256": key,
            "command_id": effect_id,
            "grant": grant,
            "grant_sha256": sha(canonical(grant)),
            "namespace_sha256": grant["namespace_sha256"],
            "request_sha256": sha(raw),
            "preflight_sha256": grant["preflight_sha256"],
            "reserved_usd": proof["cost_bound_usd"],
        }
        # Recheck at the durable point, after fresh tokenizer/budget work.
        self._live()
        if ordinal == 0 and not self.clock() < utc(shown["expires_at_utc"]):
            raise ValueError("P0_CHAIN_PREVIEW_CHANGED_OR_EXPIRED")
        self.active["staged_slot"] = slot  # Internal capability, not a durable reservation claim.
        self.ledger.reserve_finite(slot)
        with self.observer:
            own.append(slot)
            self.active["staged_slot"] = None
        receipt = FiniteEffectReceipt(
            P0NormalReceipt(self.ledger.root, str(slot["namespace_sha256"])), slot
        )
        self.current = receipt
        receipt.event("RESERVED", self.clock())
        receipt.receipt.publish(
            "DISPATCH",
            {
                "schema": "P0-FINITE-EFFECT-DISPATCH-1.0",
                "grant": grant,
                "preflight": proof,
                "request_body_utf8": raw.decode(),
                "chain_preview": shown,
                "chain_consent": self.active["consent"],
            },
        )
        self._live()
        receipt.event("PROVIDER_ATTEMPTED", self.clock())
        with self.observer:
            self.active["phase"] = role + "_TRANSPORT_ENTERED"
        try:
            response = call()
        except Exception:
            receipt.event("UNKNOWN", self.clock())
            raise ValueError("P0_CHAIN_TRANSPORT_OUTCOME_UNKNOWN") from None
        receipt.capture(response, self.clock())
        if (
            response.status is not OpenAIResponseStatus.COMPLETED
            or response.service_tier not in {None, "default"}
            or not self.clock() < utc(self.active["expires_at_utc"])
        ):
            receipt.event("PARSING_REJECTED", self.clock(), status="INCOMPLETE_OR_LATE")
            raise ValueError("P0_CHAIN_RESPONSE_INCOMPLETE_OR_LATE")
        return response

    def mapped(self, *, successful: bool, can_correct: bool = False) -> Mapping[str, object]:
        if self.current is None or self.active is None:
            raise ValueError("P0_CHAIN_RECEIPT_NOT_CAPTURED")
        receipt = self.current
        if not successful:
            if not receipt.receipt.exists("PARSING_REJECTED"):
                receipt.event("PARSING_REJECTED", self.clock(), status="MAPPING_REJECTED")
            raise ValueError("P0_CHAIN_MAPPING_REJECTED")
        self._live()
        receipt.event("PARSED", self.clock(), status="TECHNICAL_MAPPING_ONLY")
        marker = receipt.event(
            "CONSUMED", self.clock(), status="ONE_ATTEMPT_CONSUMED_NOT_PEDAGOGICAL_VALIDATION"
        )
        self.active["can_correct"] = can_correct
        result = {
            "finite_effect_receipt_sha256": marker,
            "finite_chain_command_id": self.active["command_id"],
            "request_sha256": receipt.slot["request_sha256"],
            "reserved_usd": receipt.slot["reserved_usd"],
            "billed_cost": "NOT_ESTABLISHED",
        }
        self.current = None
        self.context = None
        return result

    def validate(self, record: Mapping[str, object], *, file_name: str) -> None:
        validate_slot(
            record,
            policy=self.policy,
            decision_sha256=self.decision_sha,
            permission_sha256=self.ledger.permission_sha256,
            prefix=self.ledger.prefix,
            file_name=file_name,
        )
        grant = cast(Mapping[str, object], record["grant"])
        receipt = FiniteEffectReceipt(
            P0NormalReceipt(self.ledger.root, str(record["namespace_sha256"])), record
        )
        states = receipt.states()
        own = (
            self.active is not None
            and self.active["thread"] == get_ident()
            and (
                self.active.get("staged_slot") == record
                or any(
                    s["grant_sha256"] == record["grant_sha256"]
                    for s in cast(list[dict[str, object]], self.active["slots"])
                )
            )
        )
        if (
            not own
            and self.read_only_thread != get_ident()
            and (
                "CONSUMED" not in states
                or any(s in states for s in ("UNKNOWN", "PARSING_REJECTED"))
            )
        ):
            raise ValueError("P0_CHAIN_RETAINED_UNCERTAINTY_STOP")
        if (
            grant["effect_id"]
            != sha(
                canonical(
                    {
                        "consent": grant["consent_sha256"],
                        "ordinal": grant["ordinal"],
                        "policy": self.policy_sha,
                    }
                )
            )[:32]
        ):
            raise ValueError("P0_CHAIN_EFFECT_IDENTITY")

    def validate_group(self, records: list[dict[str, object]]) -> None:
        self._budget(records, remaining=0, next_bound=Decimal(0))
        legacy = [s for s in records if s.get("schema") != SLOT]
        witnesses = cast(list[Mapping[str, object]], self.policy["retained_origins"])
        if len({w.get("slot_sha256") for w in witnesses}) != len(witnesses) or any(
            w.get("slot_sha256") not in {sha(canonical(s)) for s in legacy} for w in witnesses
        ):
            raise ValueError("P0_CHAIN_RETAINED_ORIGIN_NOT_FOUND")
        for record in legacy:
            if any(w.get("slot_sha256") == sha(canonical(record)) for w in witnesses):
                self.validate_retained_origin(record)
            receipt = P0NormalReceipt(self.ledger.root, str(record["namespace_sha256"]))
            try:
                if receipt.confirmed(cast(Mapping[str, object], record["grant"])) is None:
                    raise ValueError("P0_CHAIN_HISTORICAL_CYCLE_NOT_COMPLETE")
                validate_events(
                    record,
                    {
                        name: receipt.read(name)
                        for name in (
                            "RESERVED",
                            "PROVIDER_ATTEMPTED",
                            "RESPONSE_CAPTURED",
                            "PARSED",
                            "CONSUMED",
                        )
                    },
                )
            except (ValueError, FileNotFoundError):
                self.validate_retained_origin(record)
        import re

        namespaces = {s["namespace_sha256"] for s in records}
        for path in self.ledger.root.glob("*.json"):
            match = re.fullmatch(r"([0-9a-f]{64})\.([A-Z_]+)\.json", path.name)
            if match and (match[1] not in namespaces or match[2] not in self._marker_names()):
                raise ValueError("P0_CHAIN_ORPHAN_RECEIPT_NAMESPACE")
        selected = [s for s in records if s.get("schema") == SLOT]
        commands = {cast(Mapping[str, object], s["grant"])["chain_command_id"] for s in selected}
        if len(commands) > 1:
            raise ValueError("P0_CHAIN_RIGHT_OVERUSED")
        if selected:
            grants = sorted(
                [cast(Mapping[str, object], s["grant"]) for s in selected],
                key=lambda g: cast(int, g["ordinal"]),
            )
            if [g["ordinal"] for g in grants] != list(range(len(grants))):
                raise ValueError("P0_CHAIN_ROLE_COLLISION")
            for field in (
                "consent_sha256",
                "preview_sha256",
                "plan_sha256",
                "parent_sha256",
                "authority_issued_at_utc",
                "expires_at_utc",
            ):
                if len({g[field] for g in grants}) != 1:
                    raise ValueError("P0_CHAIN_GROUP_BINDING")

    @staticmethod
    def _marker_names() -> tuple[str, ...]:
        return (
            "RESERVED",
            "PROVIDER_ATTEMPTED",
            "RESPONSE_CAPTURED",
            "PARSED",
            "CONSUMED",
            "UNKNOWN",
            "PARSING_REJECTED",
            "DISPATCH",
            "RESULT",
        )

    def retained_origin_snapshot(self, record: Mapping[str, object]) -> Mapping[str, object]:
        receipt = P0NormalReceipt(self.ledger.root, str(record["namespace_sha256"]))
        return {
            "schema": "P0-FINITE-RETAINED-ORIGIN-1.0",
            "disposition": "RETAIN_UNCERTAINTY_NO_REPLAY",
            "slot_sha256": sha(canonical(record)),
            **{
                key: record[key]
                for key in (
                    "permission_sha256",
                    "namespace_sha256",
                    "grant_sha256",
                    "request_sha256",
                    "reserved_usd",
                )
            },
            "markers_sha256": {
                name: hash_file_nofollow(receipt._path(name), allowed_root=self.ledger.root)
                if receipt.exists(name)
                else None
                for name in self._marker_names()
            },
        }

    def validate_retained_origin(self, record: Mapping[str, object]) -> None:
        actual = self.retained_origin_snapshot(record)
        selected = [
            row
            for row in cast(list[object], self.policy["retained_origins"])
            if isinstance(row, Mapping) and row.get("slot_sha256") == actual["slot_sha256"]
        ]
        if len(selected) != 1 or canonical(selected[0]) != canonical(actual):
            raise ValueError("P0_CHAIN_EXACT_HISTORICAL_DISPOSITION_REQUIRED")

    def revoke(self, preview_sha256: str) -> Mapping[str, object]:
        if not digest(preview_sha256) or (
            preview_sha256 not in self.previews
            and (self.active is None or self.active["preview_sha256"] != preview_sha256)
        ):
            raise ValueError("P0_CHAIN_REVOCATION_SCOPE")
        path = self._revocation_path()
        proof = {
            "schema": "P0-FINITE-CHAIN-REVOCATION-1.0",
            "policy_sha256": self.policy_sha,
            "preview_sha256": preview_sha256,
            "timestamp_utc": self.clock().isoformat(),
        }
        self.ledger.pin._publish_document(path, proof)
        return {"state": "REVOKED", "policy_sha256": self.policy_sha, "reservation_release": "NONE"}

    def _summary(self) -> dict[str, object]:
        assert self.active is not None
        own = cast(list[dict[str, object]], self.active["slots"])
        return {
            "policy_sha256": self.policy_sha,
            "command_id": self.active["command_id"],
            "issued_at_utc": self.active["issued_at_utc"],
            "expires_at_utc": self.active["expires_at_utc"],
            "effects_reserved": len(own),
            "reserved_usd": str(sum((money(s["reserved_usd"]) for s in own), Decimal(0))),
            "billing": "NOT_ESTABLISHED",
            "retry": 0,
        }

    def observe(self, command_id: str) -> Mapping[str, object] | None:
        with self.observer:
            if self.active is not None and self.active["command_id"] == command_id:
                return {
                    "command_id": command_id,
                    "state": "LOCAL_COMMAND_RUNNING",
                    "phase": self.active["phase"],
                    "financial": self._summary(),
                    "retry": 0,
                }
            if (
                command_id in self.results
                and self.results[command_id].get("state") == "CODESIGN_CANDIDATE"
            ):
                return {
                    "command_id": command_id,
                    "state": "LOCAL_COMMAND_COMPLETED",
                    "result": self.results[command_id],
                    "retry": 0,
                }
            if self.pending_command == command_id:
                return {
                    "command_id": command_id,
                    "state": "LOCAL_COMMAND_RUNNING",
                    "phase": "PREFLIGHT_RUNNING",
                    "retry": 0,
                }
        if len(command_id) != 32 or any(c not in "0123456789abcdef" for c in command_id):
            raise ValueError("P0_CHAIN_COMMAND_IDENTITY")
        # Passive recovery: validate and expose retained evidence, never resume.
        self._open_lock()
        with self.ledger.locked(create=False):
            self._lock_identity()
            self.read_only_thread = get_ident()
            try:
                slots = self.ledger.slots()
            finally:
                self.read_only_thread = None
        selected = [
            s
            for s in slots
            if s.get("schema") == SLOT
            and cast(Mapping[str, object], s["grant"])["chain_command_id"] == command_id
        ]
        if not selected:
            if command_id in self.results:
                return {
                    "state": "LOCAL_COMMAND_STOPPED",
                    "command_id": command_id,
                    "result": self.results[command_id],
                    "authority_restored": False,
                    "retry": 0,
                }
            return None
        return {
            "state": "LOCAL_COMMAND_RETAINED_UNCERTAIN",
            "command_id": command_id,
            "phase": "RETAINED_EVIDENCE_NO_AUTOMATIC_RECOVERY",
            "retry": 0,
            "effects": [
                {
                    "role": cast(Mapping[str, object], s["grant"])["role"],
                    "request_sha256": s["request_sha256"],
                    "reserved_usd": s["reserved_usd"],
                    "states": list(
                        FiniteEffectReceipt(
                            P0NormalReceipt(self.ledger.root, str(s["namespace_sha256"])), s
                        ).states()
                    ),
                }
                for s in selected
            ],
            "billing": "NOT_ESTABLISHED",
            "authority_restored": False,
            "local_result_state": self.results.get(command_id, {}).get(
                "state", "NOT_ESTABLISHED_AFTER_RESTART"
            ),
        }
