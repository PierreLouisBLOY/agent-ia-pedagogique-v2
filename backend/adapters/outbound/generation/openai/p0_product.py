"""Explicit P1 broker; local exact consent derives G1, never accepts an HTTP grant."""
from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from secrets import token_hex
from typing import cast

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import (
    IdentitySource,
    NormalP0GenerationAdapter,
    TokenizerSource,
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
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    P1_HASHES,
    derive_grant,
    validate_permission,
    validate_source_receipts,
)
from backend.adapters.outbound.openai.contracts import OpenAIResponsesTransportFactory
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretResolver,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain


class P0ProductGenerationAdapter:
    def __init__(self, *, permission: Mapping[str, object], permission_identities: Callable[[], Mapping[str, object]],
                 identity_source: IdentitySource, tariff: Mapping[str, object], tokenizer: TokenizerSource,
                 receipt_root: Path, resolver: ProviderSecretResolver, credential_ref: ProviderCredentialRef,
                 transport: OpenAIResponsesTransportFactory, clock: Callable[[], datetime] = lambda: datetime.now(UTC),
                 local_context_adoption: Mapping[str, object] | None = None) -> None:
        self.permission = cast(dict[str, object], as_plain(permission))
        self.permission_identities, self.identity_source = permission_identities, identity_source
        self.tariff, self.tokenizer = cast(dict[str, object], as_plain(tariff)), tokenizer
        self.local_context_adoption = None if local_context_adoption is None else cast(dict[str, object], as_plain(local_context_adoption))
        self.root, self.resolver, self.credential_ref, self.transport, self.clock = receipt_root, resolver, credential_ref, transport, clock
        self.ledger = P0ProductLedger(root=receipt_root, permission=self.permission)
        self.previews: dict[str, dict[str, object]] = {}
        self.pending: dict[str, NormalP0GenerationAdapter] = {}
        self.adapters: dict[str, NormalP0GenerationAdapter] = {}
        self.confirmed_results: dict[tuple[str, str], set[str]] = {}
        self.lock = threading.Lock()

    def _adapter(self, grant: Mapping[str, object]) -> NormalP0GenerationAdapter:
        # The broker owns the fresh namespace; the factory supplies all other IDs.
        def identities(request: Mapping[str, object], body: bytes) -> Mapping[str, object]:
            return {**self.identity_source(request, body), "namespace_sha256": grant["namespace_sha256"]}
        return NormalP0GenerationAdapter(grant=grant, identity_source=identities, tariff=self.tariff,
            tokenizer=self.tokenizer, receipt_root=self.root, resolver=self.resolver,
            credential_ref=self.credential_ref, transport=self.transport, clock=self.clock)

    @staticmethod
    def _family(request: Mapping[str, object]) -> tuple[str, str]:
        context = cast(Mapping[str, object], request["context"])
        family = context["resource_type"]
        if family == "QUESTION_SET":
            family = context["question_mode"]
        return str(family), str(context["level"])

    def _snapshot(self, request: Mapping[str, object], receipts: Sequence[Mapping[str, object]]) -> tuple[bytes, dict[str, object], dict[str, object]]:
        family, level = self._family(request)
        now = self.clock()
        validate_permission(self.permission, identities=self.permission_identities(), now=now, family=family, level=level)
        if utc(self.tariff["retrieved_at_utc"]) > utc(self.permission["issued_at_utc"]):
            raise ValueError("P0_PRODUCT_TARIFF_PERIOD")
        validate_source_receipts(self.permission, receipts, local_context_adoption=self.local_context_adoption)
        wire = build_p0_content_request(request)
        raw = NormalP0GenerationAdapter.body(wire)
        identities = dict(self.identity_source(request, raw))
        if set(identities) != HASH_FIELDS | {"baseline_commit", "request_bytes"}:
            raise ValueError("P0_PRODUCT_FACTORY_IDENTITIES")
        intrinsic = {"context_sha256": request["context_sha256"], "preparation_sha256": sha(canonical(as_plain(request))),
            "reference_set_sha256": sha(canonical(as_plain(request["references"]))), "request_sha256": sha(raw),
            "request_bytes": len(raw), "output_schema_sha256": sha(canonical(wire.output_schema)),
            "receipt_root_sha256": self.ledger.pin.root_sha256, "tariff_sha256": sha(canonical(self.tariff))}
        if any(identities.get(k) != v for k, v in intrinsic.items()):
            raise ValueError("P0_PRODUCT_INTRINSIC_BINDING")
        if sha(canonical([as_plain(receipt["reference"]) for receipt in receipts])) != identities["reference_set_sha256"]:
            raise ValueError("P0_PRODUCT_SOURCE_REFERENCE_SET_BINDING")
        if any(identities[k] != self.permission[k] for k in (P1_HASHES & HASH_FIELDS) | {"baseline_commit"}):
            raise ValueError("P0_PRODUCT_FACTORY_PERMISSION_BINDING")
        grant = {**identities, "schema": "P0-NORMAL-CREATE-GRANT-1.0", "operation": "CREATE", "provider": "OPENAI",
            "model": self.permission["model"], "endpoint": self.permission["endpoint"], "reasoning": "low", "tier": "default",
            "max_output_tokens": 4096, "max_calls": 1, "count_calls": 0, "review_calls": 0, "modify_calls": 0,
            "retry": 0, "fallback": "NONE", "parallelism": 1, "ceiling_usd": self.permission["per_call_ceiling_usd"],
            "issued_at_utc": now.isoformat(), "expires_at_utc": min(now + timedelta(minutes=120), utc(self.permission["expires_at_utc"])).isoformat(),
            "live_authorized": True, "transfer_authorized": True}
        proof = preflight(raw, grant, self.tariff, self.tokenizer(raw), now=now)
        agent_preparation(request, now)
        return raw, identities, proof

    def preview(self, *, request: Mapping[str, object], preparation_ref: str, preparation_sha256: str,
                source_receipts: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
        with self.lock:
            raw, identities, proof = self._snapshot(request, source_receipts)
            if identities["preparation_sha256"] != preparation_sha256:
                raise ValueError("P0_PREPARATION_CHANGED")
            now = self.clock()
            self.previews = {k: v for k, v in self.previews.items() if now < utc(v["expires_at_utc"])}
            if len(self.previews) >= 128:
                raise ValueError("P0_PRODUCT_PREVIEW_LIMIT")
            preview = {"schema": "P0-PRODUCT-CONSENT-PREVIEW-1.0", "permission_sha256": sha(canonical(self.permission)),
                "preparation_ref": preparation_ref, "preparation_sha256": preparation_sha256,
                "context_sha256": request["context_sha256"], "reference_set_sha256": identities["reference_set_sha256"],
                "request_sha256": sha(raw), "request_bytes": len(raw), "request_body_utf8": raw.decode(),
                "cost_bound_usd": proof["cost_bound_usd"], "preflight": proof, "source_receipts": as_plain(source_receipts),
                "issued_at_utc": now.isoformat(), "expires_at_utc": min(now + timedelta(minutes=15), utc(self.permission["expires_at_utc"])).isoformat()}
            key = sha(canonical(preview))
            self.previews[key] = preview
            slots = self.ledger.slots()
            return {"state": "LOCAL_OPERATOR_CONSENT_REQUIRED", "preview": as_plain(preview), "preview_sha256": key,
                "transfer_destination": {"provider": self.permission["provider"], "model": self.permission["model"],
                    "endpoint": self.permission["endpoint"], "permission_sha256": preview["permission_sha256"]},
                "remaining_calls": cast(int, self.permission["max_calls"]) - len(slots), "provider_attempts": 0,
                "remaining_budget_usd": str(money(self.permission["cumulative_ceiling_usd"]) - sum((money(s["reserved_usd"]) for s in slots), Decimal(0))),
                "review_state": "NOT_RUN", "source_status": "RESERVE", "consent_actor": "LOCAL_OPERATOR_DELEGATED"}

    def accept(self, *, request: Mapping[str, object], consent: Mapping[str, object],
               source_receipts: Sequence[Mapping[str, object]]) -> None:
        if not self.lock.acquire(blocking=False):
            raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
        try:
            key = str(consent.get("preview_sha256"))
            preview = self.previews.get(key)
            if preview is None:
                raise ValueError("P0_PRODUCT_PREVIEW_UNKNOWN_OR_CONSUMED")
            with self.ledger.locked():
                slots = self.ledger.slots()
                if any(slot["preview_sha256"] == key for slot in slots):
                    raise ValueError("P0_PRODUCT_PREVIEW_CONSUMED")
                _, identities, fresh = self._snapshot(request, source_receipts)
                nonce = token_hex(32)
                identities["namespace_sha256"] = sha(canonical({"permission_sha256": sha(canonical(self.permission)),
                    "preview_sha256": key, "command_id": consent["command_id"], "nonce_sha256": nonce}))
                family, level = self._family(request)
                grant = derive_grant(permission=self.permission, permission_identities=self.permission_identities(),
                    grant_identities=identities, preview=preview, consent=consent, nonce_sha256=nonce, family=family, level=level,
                    reserved=[money(slot["reserved_usd"]) for slot in slots], now=self.clock(), fresh_preflight=fresh,
                    application_source_receipts=source_receipts, local_context_adoption=self.local_context_adoption)
                # The precise pessimistic costs are read under the same lock.
                from backend.adapters.outbound.generation.openai.p0_product_policy import (
                    check_budget,
                )
                check_budget(self.permission, [money(slot["reserved_usd"]) for slot in slots], money(fresh["cost_bound_usd"]))
                self.ledger.reserve(grant=grant, preview_sha256=key, command_id=str(consent["command_id"]), preflight=fresh)
                self.previews.pop(key)
                adapter = self._adapter(grant)
                dispatch_key = sha(canonical(as_plain(request)))
                self.pending[dispatch_key] = adapter
                self.adapters[str(grant["namespace_sha256"])] = adapter
        finally:
            self.lock.release()

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        adapter = self.pending.get(sha(canonical(as_plain(request))))
        return False if adapter is None else adapter.authorize(request=request)

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        key = sha(canonical(as_plain(request)))
        adapter = self.pending.pop(key, None)
        if adapter is None:
            raise ValueError("P0_PRODUCT_CONSENT_REQUIRED")
        # The permission's retained Windows lock covers the actual effect, too.
        # Independent preparations/processes cannot run overlapping requests.
        # A competing call refuses; its already reserved cost is never refunded.
        with self.ledger.locked():
            result = adapter.generate(request=request)
            self._record_confirmation(request, result, adapter)
            return result

    def _record_confirmation(self, request: Mapping[str, object], result: Mapping[str, object],
                             adapter: NormalP0GenerationAdapter) -> None:
        dispatch = adapter.confirmed_dispatch()
        if dispatch is None or canonical(dispatch) != canonical(request):
            raise ValueError("P0_PRODUCT_RESULT_CONFIRMATION_BINDING")
        result_sha = sha(canonical(result))
        adapter.control_evidence(request=request, bundle_sha256=result_sha)
        key = (sha(canonical(request)), result_sha)
        with self.lock:
            self.confirmed_results.setdefault(key, set()).add(str(adapter.grant["namespace_sha256"]))

    def _historical_adapters(self) -> list[NormalP0GenerationAdapter]:
        result = []
        for slot in self.ledger.slots():
            adapter = self._adapter(cast(Mapping[str, object], slot["grant"]))
            if adapter.receipt.exists("RESERVED"):
                capture = adapter.receipt.read("DISPATCH")
                if capture["preflight_sha256"] != slot["preflight_sha256"]:
                    raise ValueError("P0_PRODUCT_RECOVERY_SLOT_BINDING")
            result.append(adapter)
        return result

    def confirmed_dispatches(self) -> tuple[Mapping[str, object], ...]:
        records = tuple(dispatch for adapter in self._historical_adapters() if (dispatch := adapter.confirmed_dispatch()) is not None)
        identities = [(str(r["production_ref"]), str(r["version_ref"])) for r in records]
        if len(identities) != len(set(identities)):
            raise ValueError("P0_PRODUCT_CONFIRMATION_AMBIGUOUS")
        return records

    def confirmed_dispatch(self) -> Mapping[str, object] | None:
        records = self.confirmed_dispatches()
        if len(records) > 1:
            raise ValueError("P0_PRODUCT_MULTIPLE_CONFIRMATIONS")
        return records[0] if records else None

    def recover_confirmed(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        identity = sha(canonical(as_plain(request)))
        matches = []
        for adapter in self._historical_adapters():
            dispatch = adapter.confirmed_dispatch()
            if dispatch is not None and sha(canonical(as_plain(dispatch))) == identity:
                matches.append(adapter)
        if len(matches) != 1:
            raise ValueError("P0_PRODUCT_RECOVERY_NOT_FOUND" if not matches else "P0_PRODUCT_CONFIRMATION_AMBIGUOUS")
        adapter = matches[0]
        result = adapter.recover_confirmed(request=request)
        self.adapters[str(adapter.grant["namespace_sha256"])] = adapter
        self._record_confirmation(request, result, adapter)
        return result

    def control_evidence(self, *, request: Mapping[str, object], bundle_sha256: str) -> Mapping[str, object]:
        with self.lock:
            namespaces = self.confirmed_results.get((sha(canonical(request)), bundle_sha256), set())
            if len(namespaces) != 1:
                raise ValueError("P0_PRODUCT_CONTROLS_NOT_FOUND" if not namespaces else "P0_PRODUCT_CONFIRMATION_AMBIGUOUS")
            adapter = self.adapters[next(iter(namespaces))]
        return adapter.control_evidence(request=request, bundle_sha256=bundle_sha256)
