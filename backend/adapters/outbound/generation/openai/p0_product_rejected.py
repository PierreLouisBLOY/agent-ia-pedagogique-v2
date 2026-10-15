"""V2 opt-in broker; no transfer or repair of the known rejected grant."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from secrets import token_hex
from typing import cast

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import (
    NormalP0GenerationAdapter,
)
from backend.adapters.outbound.generation.openai.p0_normal_agents import agent_preparation
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    HASH_FIELDS,
    canonical,
    money,
    preflight,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    OwnPending,
    require_effect_enabled,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
    P0ContinuityProductLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    P1_HASHES,
    validate_permission,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
    P0RejectedReadPhasePort,
    target,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_ledger import (
    P0RejectedContinuityLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_policy import (
    derive_grant4,
    validate_source_receipts4,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain


class P0RejectedProductGenerationAdapter(P0ProductGenerationAdapter):
    """Only the profile4 factory can construct this opt-in composition."""

    def __init__(
        self,
        *,
        rejected_chain: Callable[[], BoundChainV2],
        read_phase: P0RejectedReadPhasePort,
        **kwargs: object,
    ) -> None:
        # All inherited financial and consent predicates keep their originals.
        super().__init__(continuity_chain=rejected_chain, **kwargs)  # type: ignore[arg-type]
        self.read_phase = read_phase
        chain = rejected_chain()
        self.ledger = P0RejectedContinuityLedger(
            root=self.root,
            permission=self.permission,
            chain_loader=rejected_chain,
            broker_identity=self,
            clock=self.clock,
            selected=target(chain.disposition["target_attempt"]),
            tariff=self.tariff,
            orientation=cast(Mapping[str, object], chain.evidence["owner_orientation_adoption"]),
            diagnostic=cast(Mapping[str, object], chain.evidence["owner_diagnostic"]),
            plan_sha256=str(chain.evidence["inspection_plan_sha256"]),
        )

    def _snapshot(
        self, request: Mapping[str, object], receipts: Sequence[Mapping[str, object]]
    ) -> tuple[bytes, dict[str, object], dict[str, object]]:
        context = cast(Mapping[str, object], request["context"])
        if (
            context.get("contract_id") != "P0-CONTEXT-COURSE-4.0"
            or context.get("course_format") != "CHAPTER"
        ):
            raise ValueError("P0_REJECTED_NEW_NOTION_COURSE_REQUIRED")
        family, level = self._family(request)
        now = self.clock()
        if self.continuity_chain is not None:
            require_effect_enabled(self.continuity_chain(), now=now, family=family, level=level)
        validate_permission(
            self.permission,
            identities=self.permission_identities(),
            now=now,
            family=family,
            level=level,
        )
        if utc(self.tariff["retrieved_at_utc"]) > utc(self.permission["issued_at_utc"]):
            raise ValueError("P0_PRODUCT_TARIFF_PERIOD")
        validate_source_receipts4(
            self.permission, receipts, local_context_adoption=self.local_context_adoption
        )
        wire = build_p0_content_request(request)
        raw = NormalP0GenerationAdapter.body(wire)
        identities = dict(self.identity_source(request, raw))
        if set(identities) != HASH_FIELDS | {"baseline_commit", "request_bytes"}:
            raise ValueError("P0_PRODUCT_FACTORY_IDENTITIES")
        intrinsic = {
            "context_sha256": request["context_sha256"],
            "preparation_sha256": sha(canonical(as_plain(request))),
            "reference_set_sha256": sha(canonical(as_plain(request["references"]))),
            "request_sha256": sha(raw),
            "request_bytes": len(raw),
            "output_schema_sha256": sha(canonical(wire.output_schema)),
            "receipt_root_sha256": self.ledger.pin.root_sha256,
            "tariff_sha256": sha(canonical(self.tariff)),
        }
        if any(identities.get(k) != v for k, v in intrinsic.items()):
            raise ValueError("P0_PRODUCT_INTRINSIC_BINDING")
        if (
            sha(canonical([as_plain(receipt["reference"]) for receipt in receipts]))
            != identities["reference_set_sha256"]
        ):
            raise ValueError("P0_PRODUCT_SOURCE_REFERENCE_SET_BINDING")
        if any(
            identities[k] != self.permission[k]
            for k in (P1_HASHES & HASH_FIELDS) | {"baseline_commit"}
        ):
            raise ValueError("P0_PRODUCT_FACTORY_PERMISSION_BINDING")
        grant = {
            **identities,
            "schema": "P0-NORMAL-CREATE-GRANT-1.0",
            "operation": "CREATE",
            "provider": "OPENAI",
            "model": self.permission["model"],
            "endpoint": self.permission["endpoint"],
            "reasoning": "low",
            "tier": "default",
            "max_output_tokens": 4096,
            "max_calls": 1,
            "count_calls": 0,
            "review_calls": 0,
            "modify_calls": 0,
            "retry": 0,
            "fallback": "NONE",
            "parallelism": 1,
            "ceiling_usd": self.permission["per_call_ceiling_usd"],
            "issued_at_utc": now.isoformat(),
            "expires_at_utc": min(
                now + timedelta(minutes=120), utc(self.permission["expires_at_utc"])
            ).isoformat(),
            "live_authorized": True,
            "transfer_authorized": True,
        }
        proof = preflight(raw, grant, self.tariff, self.tokenizer(raw), now=now)
        agent_preparation(request, now)
        return raw, identities, proof

    def accept(
        self,
        *,
        request: Mapping[str, object],
        consent: Mapping[str, object],
        source_receipts: Sequence[Mapping[str, object]],
    ) -> None:
        if not self.lock.acquire(blocking=False):
            raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
        try:
            key = str(consent.get("preview_sha256"))
            preview = self.previews.get(key)
            if preview is None:
                raise ValueError("P0_PRODUCT_PREVIEW_UNKNOWN_OR_CONSUMED")
            with self.ledger.locked(), self.read_phase.phase("ACCEPT"):
                slots = self.ledger.slots()
                if any(slot["preview_sha256"] == key for slot in slots):
                    raise ValueError("P0_PRODUCT_PREVIEW_CONSUMED")
                _, identities, fresh = self._snapshot(request, source_receipts)
                nonce = token_hex(32)
                identities["namespace_sha256"] = sha(
                    canonical(
                        {
                            "permission_sha256": sha(canonical(self.permission)),
                            "preview_sha256": key,
                            "command_id": consent["command_id"],
                            "nonce_sha256": nonce,
                        }
                    )
                )
                family, level = self._family(request)
                grant = derive_grant4(
                    permission=self.permission,
                    permission_identities=self.permission_identities(),
                    grant_identities=identities,
                    preview=preview,
                    consent=consent,
                    nonce_sha256=nonce,
                    family=family,
                    level=level,
                    reserved=[money(slot["reserved_usd"]) for slot in slots],
                    now=self.clock(),
                    fresh_preflight=fresh,
                    application_source_receipts=source_receipts,
                    local_context_adoption=self.local_context_adoption,
                )
                # The precise pessimistic costs are read under the same lock.
                from backend.adapters.outbound.generation.openai.p0_product_policy import (
                    check_budget,
                )

                check_budget(
                    self.permission,
                    [money(slot["reserved_usd"]) for slot in slots],
                    money(fresh["cost_bound_usd"]),
                )
                self.ledger.reserve(
                    grant=grant,
                    preview_sha256=key,
                    command_id=str(consent["command_id"]),
                    preflight=fresh,
                )
                self.previews.pop(key)
                adapter = self._adapter(grant)
                dispatch_key = sha(canonical(as_plain(request)))
                self.pending[dispatch_key] = adapter
                if isinstance(self.ledger, P0ContinuityProductLedger):
                    self.pending_capabilities[dispatch_key] = OwnPending(
                        self,
                        sha(canonical(self.permission)),
                        str(consent["command_id"]),
                        sha(canonical(grant)),
                        str(grant["namespace_sha256"]),
                        str(grant["request_sha256"]),
                        sha(canonical(fresh)),
                        dispatch_key,
                        str(preview["expires_at_utc"]),
                    )
                self.adapters[str(grant["namespace_sha256"])] = adapter
        finally:
            self.lock.release()

    def preview(
        self,
        *,
        request: Mapping[str, object],
        preparation_ref: str,
        preparation_sha256: str,
        source_receipts: Sequence[Mapping[str, object]],
    ) -> Mapping[str, object]:
        with self.ledger.locked(), self.read_phase.phase("PREVIEW"):
            self.ledger.slots()
            return self._preview(
                request=request,
                preparation_ref=preparation_ref,
                preparation_sha256=preparation_sha256,
                source_receipts=source_receipts,
            )

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        key = sha(canonical(as_plain(request)))
        adapter = self.pending.pop(key, None)
        if adapter is None:
            raise ValueError("P0_PRODUCT_CONSENT_REQUIRED")
        ledger = cast(P0RejectedContinuityLedger, self.ledger)
        with ledger.locked():
            capability = self.pending_capabilities.pop(key, None)
            if capability is None:
                raise ValueError("P0_CONTINUITY_OWN_PENDING_REQUIRED")
            family, level = self._family(request)
            require_effect_enabled(ledger.chain(), now=self.clock(), family=family, level=level)
            with (
                ledger.own_transition(capability, dispatch_sha256=key),
                self.read_phase.phase("GENERATE"),
            ):
                self.ledger.slots()
                result = adapter.generate(request=request)
                # Only the actual Normal return can reach this terminal check.
                # confirmed()/event validation retain the complete real lifecycle.
                self.ledger.slots()
                self._record_confirmation(request, result, adapter)
                return result
