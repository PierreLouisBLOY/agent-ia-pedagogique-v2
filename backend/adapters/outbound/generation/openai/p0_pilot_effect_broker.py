"""One pilot CREATE on the normal transport with a separate same-need ledger.

The trusted composition supplies an adopted successor permission, fresh
Application receipts and exact historical anchors.  No instance is created by
the OFF browser composition, and construction never resolves a credential.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from secrets import token_hex
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal import (
    IdentitySource,
    NormalP0GenerationAdapter,
    TokenizerSource,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, money, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import decode
from backend.adapters.outbound.generation.openai.p0_pilot_mixed_ledger import P0PilotMixedLedger
from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    CONSENT_FIELDS,
    check_budget,
    derive_grant,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    ValidatedUnknownOff,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesTransportFactory,
)
from backend.adapters.outbound.persistence.p0_pilot_incident import P0PilotIncidentDisposition
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretResolver,
)
from backend.infrastructure.filesystem import read_file_nofollow
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain


def conservative_pilot_preflight(proof: Mapping[str, object], *,
                                 request_sha256: str, request_bytes: int,
                                 local_text_tokens: int, tariff: Mapping[str, object],
                                 approved_cost_bound: Decimal) -> dict[str, object]:
    """Reserve the admitted byte bound without changing the observed token count."""
    if (proof.get("request_sha256") != request_sha256
        or proof.get("request_bytes") != request_bytes
        or type(proof.get("local_text_tokens")) is not int
        or proof["local_text_tokens"] != local_text_tokens
        or proof.get("structural_reserve_tokens") != 10000
        or proof.get("input_upper_tokens") != local_text_tokens + 10000
        or proof.get("tariff_sha256") != sha(canonical(tariff))
        or proof.get("max_output_tokens") != 4096):
        raise ValueError("P1_PILOT_CONSERVATIVE_PREFLIGHT_CHANGED")
    upper = max(request_bytes, local_text_tokens) + 10000
    if upper > 40000:
        raise ValueError("P1_PILOT_CONSERVATIVE_INPUT_BOUND")
    cost = (Decimal(upper) * money(tariff["input_usd_per_million"])
        * money(tariff["input_multiplier"])
        + Decimal(4096) * money(tariff["output_usd_per_million"])) / Decimal(1000000)
    if cost != approved_cost_bound or cost > money(proof["ceiling_usd"]):
        raise ValueError("P1_PILOT_CONSERVATIVE_COST_CHANGED")
    return {**proof, "structural_reserve_tokens": upper - local_text_tokens,
        "input_upper_tokens": upper, "cost_bound_usd": str(cost)}


class _PilotConservativeAdapter(NormalP0GenerationAdapter):
    def __init__(self, *, grant: Mapping[str, object], identity_source: IdentitySource,
                 tariff: Mapping[str, object], tokenizer: TokenizerSource,
                 receipt_root: Path, resolver: ProviderSecretResolver,
                 credential_ref: ProviderCredentialRef,
                 transport: OpenAIResponsesTransportFactory,
                 clock: Callable[[], datetime],
                 before_attempt: Callable[[Mapping[str, object]], None] | None,
                 request_sha256: str, request_bytes: int,
                 local_text_tokens: int, approved_cost_bound: Decimal) -> None:
        super().__init__(grant=grant, identity_source=identity_source,
            tariff=tariff, tokenizer=tokenizer, receipt_root=receipt_root,
            resolver=resolver, credential_ref=credential_ref,
            transport=transport, clock=clock, before_attempt=before_attempt)
        self._pilot_request_sha256 = request_sha256
        self._pilot_request_bytes = request_bytes
        self._pilot_local_text_tokens = local_text_tokens
        self._pilot_cost_bound = approved_cost_bound

    def _check(self, request: Mapping[str, object], *, require_unused: bool = True
               ) -> tuple[OpenAIResponsesRequest, dict[str, object], datetime]:
        wire, proof, now = super()._check(request, require_unused=require_unused)
        return wire, conservative_pilot_preflight(proof,
            request_sha256=self._pilot_request_sha256,
            request_bytes=self._pilot_request_bytes,
            local_text_tokens=self._pilot_local_text_tokens,
            tariff=self.tariff, approved_cost_bound=self._pilot_cost_bound), now


class P0PilotEffectBroker(P0ProductGenerationAdapter):
    """Three-consent pilot wrapper; no retry and no reuse of an old grant."""

    def __init__(self, *, permission: Mapping[str, object],
                 permission_identities: Callable[[], Mapping[str, object]],
                 identity_source: IdentitySource, tariff: Mapping[str, object],
                 tokenizer: TokenizerSource, receipt_root: Path,
                 resolver: ProviderSecretResolver, credential_ref: ProviderCredentialRef,
                 transport: OpenAIResponsesTransportFactory,
                 historical: Callable[[], ValidatedUnknownOff],
                 frozen_inventory: Sequence[Mapping[str, object]],
                 frozen_inventory_sha256: str,
                 parent_unknown_request_sha256: str,
                 candidate_request_sha256: str,
                 candidate_preparation_sha256: str,
                 candidate_context_sha256: str,
                 candidate_reference_set_sha256: str,
                 source_reader: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]],
                 before_provider_attempt: Callable[[Mapping[str, object]], None] | None = None,
                 before_reservation: Callable[[Mapping[str, object]], None] | None = None,
                 approved_cost_bound_usd: str = "0.1237945",
                 approved_request_bytes: int = 19857,
                 approved_local_text_tokens: int = 5296,
                 local_context_adoption: Mapping[str, object] | None = None,
                 historical_extras: Sequence[Mapping[str, object]] = (),
                 incident: P0PilotIncidentDisposition | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        disposition = cast(Mapping[str, object], historical().disposition["target_attempt"])
        if disposition["request_sha256"] != parent_unknown_request_sha256:
            raise ValueError("P1_PILOT_PARENT_UNKNOWN_CHANGED")
        self._approved_cost_bound = money(approved_cost_bound_usd)
        self._approved_request_sha256 = candidate_request_sha256
        self._approved_request_bytes = approved_request_bytes
        self._approved_local_text_tokens = approved_local_text_tokens
        if self._approved_cost_bound <= 0 or self._approved_cost_bound > money("0.14"):
            raise ValueError("P1_PILOT_APPROVED_COST_BOUND_REQUIRED")
        super().__init__(permission=permission, permission_identities=permission_identities,
            identity_source=identity_source, tariff=tariff, tokenizer=tokenizer,
            receipt_root=receipt_root, resolver=resolver, credential_ref=credential_ref,
            transport=transport, clock=clock, local_context_adoption=local_context_adoption)
        self.base_slots_count = incident.base_slots_count if incident is not None else 3
        self.ledger = P0PilotMixedLedger(root=receipt_root, permission=permission,
            historical=historical, frozen_inventory=frozen_inventory,
            frozen_inventory_sha256=frozen_inventory_sha256,
            candidate_request_sha256=candidate_request_sha256,
            candidate_preparation_sha256=candidate_preparation_sha256,
            candidate_context_sha256=candidate_context_sha256,
            candidate_reference_set_sha256=candidate_reference_set_sha256,
            clock=clock, broker_identity=self, historical_extras=historical_extras,
            incident=incident)
        self._source_reader = source_reader
        self._before_provider_attempt = before_provider_attempt
        self._before_reservation = before_reservation
        self._accepted_source_hash: dict[str, str] = {}

    def _adapter(self, grant: Mapping[str, object]) -> NormalP0GenerationAdapter:
        def identities(request: Mapping[str, object], body: bytes) -> Mapping[str, object]:
            return {**self.identity_source(request, body),
                "namespace_sha256": grant["namespace_sha256"]}
        return _PilotConservativeAdapter(grant=grant, identity_source=identities,
            tariff=self.tariff, tokenizer=self.tokenizer, receipt_root=self.root,
            resolver=self.resolver, credential_ref=self.credential_ref,
            transport=self.transport, clock=self.clock,
            before_attempt=self._before_provider_attempt,
            request_sha256=self._approved_request_sha256,
            request_bytes=self._approved_request_bytes,
            local_text_tokens=self._approved_local_text_tokens,
            approved_cost_bound=self._approved_cost_bound)

    def _snapshot(self, request: Mapping[str, object], receipts: Sequence[Mapping[str, object]]
                  ) -> tuple[bytes, dict[str, object], dict[str, object]]:
        raw, identities, proof = super()._snapshot(request, receipts)
        return raw, identities, conservative_pilot_preflight(proof,
            request_sha256=self._approved_request_sha256,
            request_bytes=self._approved_request_bytes,
            local_text_tokens=self._approved_local_text_tokens,
            tariff=self.tariff, approved_cost_bound=self._approved_cost_bound)

    def revalidate_before_attempt(self, request: Mapping[str, object]) -> None:
        """Recheck the retained history and exact child under the held original LOCK."""
        slots = self.ledger.slots()
        if len(slots) != self.base_slots_count + 1:
            raise ValueError("P1_PILOT_RESERVED_CHILD_REQUIRED")
        fresh = self._source_reader(request)
        _, identities, proof = self._snapshot(request, fresh)
        child = slots[-1]
        if (identities["request_sha256"] != child["request_sha256"]
            or money(proof["cost_bound_usd"]) > self._approved_cost_bound
            or proof["cost_bound_usd"] != child["reserved_usd"]
            or sha(canonical(proof)) != child["preflight_sha256"]):
            raise ValueError("P1_PILOT_FRESH_PREFLIGHT_CHANGED")

    def _confirmed_child_adapters(self) -> list[NormalP0GenerationAdapter]:
        with self.ledger.locked():
            slots = self.ledger.slots()
            children = [slot for slot in slots if slot.get("permission_sha256") ==
                sha(canonical(self.permission))]
            if len(children) > 1:
                raise ValueError("P1_PILOT_MULTIPLE_CHILDREN_STOP")
            return self._historical_adapters_from(children)

    def confirmed_dispatches(self) -> tuple[Mapping[str, object], ...]:
        adapters = self._confirmed_child_adapters()
        return tuple(dispatch for adapter in adapters
            if (dispatch := adapter.confirmed_dispatch()) is not None)

    def recover_confirmed(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        identity = sha(canonical(as_plain(request)))
        matches = [adapter for adapter in self._confirmed_child_adapters()
            if (dispatch := adapter.confirmed_dispatch()) is not None
            and sha(canonical(dispatch)) == identity]
        if len(matches) != 1:
            raise ValueError("P1_PILOT_CONFIRMED_CHILD_NOT_FOUND")
        adapter = matches[0]
        result = adapter.recover_confirmed(request=request)
        self.adapters[str(adapter.grant["namespace_sha256"])] = adapter
        self._record_confirmation(request, result, adapter)
        return result

    def preview(self, *, request: Mapping[str, object], preparation_ref: str,
                preparation_sha256: str,
                source_receipts: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
        # Unlike the normal broker, historical mixed slots cannot be read
        # outside the original retained LOCK.
        with self.ledger.locked():
            slots = self.ledger.slots()
            if len(slots) != self.base_slots_count:
                raise ValueError("P1_PILOT_OPERATION_ALREADY_RESERVED")
            fresh = self._source_reader(request)
            if canonical(as_plain(fresh)) != canonical(as_plain(source_receipts)):
                raise ValueError("P1_PILOT_SOURCE_CHANGED")
            result = dict(self._preview(request=request, preparation_ref=preparation_ref,
                preparation_sha256=preparation_sha256, source_receipts=fresh))
            shown = cast(Mapping[str, object], result["preview"])
            if money(shown["cost_bound_usd"]) > self._approved_cost_bound:
                raise ValueError("P1_PILOT_APPROVED_COST_BOUND_EXCEEDED")
            result["remaining_calls"] = 1
            return result

    def accept(self, *, request: Mapping[str, object], consent: Mapping[str, object],
               source_receipts: Sequence[Mapping[str, object]]) -> None:
        if (set(consent) != CONSENT_FIELDS | {"double_execution_cost_risk_accepted"}
            or consent.get("double_execution_cost_risk_accepted") is not True
            or consent.get("transfer_accepted") is not True
            or consent.get("cost_bound_accepted") is not True):
            raise ValueError("P1_PILOT_THREE_CONSENTS_REQUIRED")
        if not self.lock.acquire(blocking=False):
            raise ValueError("P0_PRODUCT_CONCURRENT_DISPATCH")
        try:
            with self.ledger.locked():
                key = str(consent["preview_sha256"])
                preview = self.previews.get(key)
                slots = self.ledger.slots()
                if preview is None or len(slots) != self.base_slots_count:
                    raise ValueError("P1_PILOT_PREVIEW_OR_CAPACITY_CHANGED")
                fresh = self._source_reader(request)
                if canonical(as_plain(fresh)) != canonical(as_plain(source_receipts)):
                    raise ValueError("P1_PILOT_SOURCE_CHANGED")
                _, identities, proof = self._snapshot(request, fresh)
                if money(proof["cost_bound_usd"]) > self._approved_cost_bound:
                    raise ValueError("P1_PILOT_APPROVED_COST_BOUND_EXCEEDED")
                nonce = token_hex(32)
                identities["namespace_sha256"] = sha(canonical({
                    "permission_sha256": sha(canonical(self.permission)),
                    "preview_sha256": key, "command_id": consent["command_id"],
                    "nonce_sha256": nonce}))
                family, level = self._family(request)
                # The pilot has already checked the third consent. Normal
                # derive_grant supplies the compatible G1 only after the
                # fresh three-slot read and source proof under this LOCK.
                normal_consent = {field: consent[field] for field in CONSENT_FIELDS}
                grant = derive_grant(permission=self.permission,
                    permission_identities=self.permission_identities(),
                    grant_identities=identities, preview=preview, consent=normal_consent,
                    nonce_sha256=nonce, family=family, level=level,
                    reserved=[money(slot["reserved_usd"]) for slot in slots], now=self.clock(),
                    fresh_preflight=proof, application_source_receipts=fresh,
                    local_context_adoption=self.local_context_adoption)
                check_budget(self.permission, [money(slot["reserved_usd"]) for slot in slots],
                    money(proof["cost_bound_usd"]))
                if self._before_reservation is not None:
                    self._before_reservation(request)
                self.ledger.reserve(grant=grant, preview_sha256=key,
                    command_id=str(consent["command_id"]), preflight=proof)
                self.previews.pop(key)
                path = self.ledger.root / (self.ledger.prefix + key + ".json")
                record = decode(read_file_nofollow(path, allowed_root=self.ledger.root,
                    maximum_bytes=32_000))
                if (record["command_id"] != consent["command_id"]
                    or record["grant_sha256"] != sha(canonical(grant))
                    or record["request_sha256"] != grant["request_sha256"]):
                    raise ValueError("P1_PILOT_RESERVED_CHILD_CHANGED")
                cast(P0PilotMixedLedger, self.ledger).arm(record=record)
                self.ledger.slots()
                adapter = self._adapter(grant)
                dispatch_key = sha(canonical(as_plain(request)))
                self.pending[dispatch_key] = adapter
                self.adapters[str(grant["namespace_sha256"])] = adapter
                self._accepted_source_hash[dispatch_key] = sha(canonical(as_plain(fresh)))
        except Exception:
            cast(P0PilotMixedLedger, self.ledger).disarm()
            raise ValueError("P1_PILOT_OPERATION_STOP") from None
        finally:
            self.lock.release()

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        key = sha(canonical(as_plain(request)))
        if key not in self.pending or key not in self._accepted_source_hash:
            return False
        try:
            with self.ledger.locked():
                self.ledger.slots()
                fresh = self._source_reader(request)
                if sha(canonical(as_plain(fresh))) != self._accepted_source_hash[key]:
                    raise ValueError("P1_PILOT_SOURCE_CHANGED")
                self._snapshot(request, fresh)
                return self.pending[key].authorize(request=request)
        except Exception:
            self.pending.pop(key, None)
            self._accepted_source_hash.pop(key, None)
            cast(P0PilotMixedLedger, self.ledger).disarm()
            raise ValueError("P1_PILOT_OPERATION_STOP") from None

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        key = sha(canonical(as_plain(request)))
        adapter = self.pending.pop(key, None)
        source_hash = self._accepted_source_hash.pop(key, None)
        if adapter is None or source_hash is None:
            raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
        try:
            with self.ledger.locked():
                slots = self.ledger.slots()
                if len(slots) != self.base_slots_count + 1:
                    raise ValueError("P1_PILOT_RESERVED_CHILD_REQUIRED")
                fresh = self._source_reader(request)
                if sha(canonical(as_plain(fresh))) != source_hash:
                    raise ValueError("P1_PILOT_SOURCE_CHANGED")
                _, identities, proof = self._snapshot(request, fresh)
                if money(proof["cost_bound_usd"]) > self._approved_cost_bound:
                    raise ValueError("P1_PILOT_APPROVED_COST_BOUND_EXCEEDED")
                if (identities["request_sha256"] != adapter.grant["request_sha256"]
                    or proof["cost_bound_usd"] != slots[-1]["reserved_usd"]
                    or sha(canonical(proof)) != slots[-1]["preflight_sha256"]):
                    raise ValueError("P1_PILOT_FRESH_PREFLIGHT_CHANGED")
                # The normal adapter publishes RESERVED/ATTEMPTED/result and a
                # safe private diagnostic. No retry/fallback is configured.
                result = adapter.generate(request=request)
                self.ledger.slots()  # A success must be terminal and coherent.
                self._record_confirmation(request, result, adapter)
                return result
        finally:
            cast(P0PilotMixedLedger, self.ledger).disarm()
