"""One explicitly configured normal CREATE; disabled by absence of configuration.

No ambient grant or credential lookup. Tests inject declared transports and proofs.
The immutable receipt is committed before any secret resolution/provider attempt.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal_agents import (
    agent_preparation,
    guard_and_bind,
    parse_content,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    preflight,
    sha,
    validate_grant,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    P0NormalReceipt,
    pinned_receipt_root,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponseStatus,
    OpenAIResponsesTransportFactory,
)
from backend.agent_runtime.agents.generation.generation_agent import GeneratorAgent
from backend.agent_runtime.agents.generation.generation_coordinator import GenerationCoordinator
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationOperation,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
)
from backend.infrastructure.composition.factories.conversation import r2_request_parameters
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretResolver,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain

IdentitySource = Callable[[Mapping[str, object], bytes], Mapping[str, object]]
TokenizerSource = Callable[[bytes], Mapping[str, object]]


class _TechnicalP0Port:
    def __init__(self, owner: NormalP0GenerationAdapter, dispatch: Mapping[str, object],
                 wire: OpenAIResponsesRequest, proof: Mapping[str, object], now: datetime) -> None:
        self.owner, self.dispatch, self.wire, self.proof, self.now = owner, dispatch, wire, proof, now

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        # Keep the physical receipt root retained across resolution and network
        # latency, including capture; per-file publication pins alone leave gaps.
        with pinned_receipt_root(self.owner.receipt.root):
            return self._generate_pinned(request=request)

    def _generate_pinned(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        if request.operation is not GenerationOperation.GENERATE:
            raise ValueError("P0_NORMAL_CREATE_ONLY")
        expected = GenerationCoordinator(self).prepare(request=agent_preparation(self.dispatch, self.now)).port_request
        if request != expected:
            raise ValueError("P0_NORMAL_CANONICAL_BINDING")
        owner = self.owner
        owner.receipt.reserve(grant=owner.grant, dispatch=self.dispatch, body=owner.body(self.wire), preflight=self.proof)
        # A consumed namespace cannot be reopened if any later step fails.
        attempted = 0
        try:
            secret = owner.resolver.resolve(owner.credential_ref)
            owner._check(self.dispatch, require_unused=False)
            transport = owner.transport.build(secret=secret, timeout_seconds=owner.timeout)
            _, latest, _ = owner._check(self.dispatch, require_unused=False)
            if latest != self.proof:
                raise ValueError("P0_NORMAL_PREFLIGHT_CHANGED")
            owner.receipt.publish("PROVIDER_ATTEMPTED", owner.receipt.event("PROVIDER_ATTEMPTED", owner.grant, self.proof))
            attempted = 1
            response = transport.create(request=self.wire)
            usage = asdict(response.usage)
            artifact = {"schema": "P0-NORMAL-CONFIRMED-RESULT-1.0", "grant_sha256": sha(canonical(owner.grant)),
                "request_sha256": owner.grant["request_sha256"], "dispatch_sha256": sha(canonical(as_plain(self.dispatch))),
                "response_status": response.status.value, "output_text": response.output_text, "usage": usage}
            artifact_sha = owner.receipt.publish("RESULT", artifact)
            owner.receipt.publish("RESPONSE_CAPTURED", owner.receipt.event("RESPONSE_CAPTURED", owner.grant,
                self.proof, artifact=artifact_sha, status=response.status.value, usage=usage))
        except Exception:
            owner.receipt.publish("UNKNOWN", owner.receipt.event("UNKNOWN", owner.grant, self.proof, provider_attempts=attempted))
            raise ValueError("P0_NORMAL_OUTCOME_UNKNOWN") from None
        if (response.status is not OpenAIResponseStatus.COMPLETED or response.service_tier not in {None, "default"}
                or response.output_text is None):
            owner.receipt.publish("PARSING_REJECTED", owner.receipt.event("PARSING_REJECTED", owner.grant, self.proof))
            raise ValueError("P0_NORMAL_RESPONSE_REJECTED")
        owner.receipt.confirmed(owner.grant)
        return owner.technical_result(self.dispatch, response.output_text)


class NormalP0GenerationAdapter:
    """Grant/identities/tokenizer/tariff/resolver are explicit infrastructure inputs.

    Constructing this object performs no provider call or credential resolution.
    Composition with generation=None remains the ordinary disabled mode.
    """
    def __init__(self, *, grant: Mapping[str, object], identity_source: IdentitySource,
                 tariff: Mapping[str, object], tokenizer: TokenizerSource,
                 receipt_root: Path, resolver: ProviderSecretResolver,
                 credential_ref: ProviderCredentialRef, transport: OpenAIResponsesTransportFactory,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC), timeout_seconds: float = 120.0) -> None:
        if type(timeout_seconds) is not float or not 0 < timeout_seconds <= 120:
            raise ValueError("P0_NORMAL_TIMEOUT")
        self.grant = cast(dict[str, object], as_plain(grant))
        self.tariff = cast(dict[str, object], as_plain(tariff))
        self.identities, self.tokenizer = identity_source, tokenizer
        self.resolver, self.credential_ref, self.transport = resolver, credential_ref, transport
        self.clock, self.timeout = clock, timeout_seconds
        self.receipt = P0NormalReceipt(receipt_root, cast(str, self.grant.get("namespace_sha256")))
        self._lock = threading.Lock()
        self._authorized: tuple[str, str] | None = None
        self._controls: dict[str, object] | None = None

    @staticmethod
    def body(wire: OpenAIResponsesRequest) -> bytes:
        return canonical(r2_request_parameters(wire))

    def _check(self, request: Mapping[str, object], *, require_unused: bool = True) -> tuple[OpenAIResponsesRequest, dict[str, object], datetime]:
        wire = build_p0_content_request(request)
        raw, now = self.body(wire), self.clock()
        identities = dict(self.identities(request, raw))
        if identities.get("receipt_root_sha256") != self.receipt.root_sha256:
            raise ValueError("P0_NORMAL_RECEIPT_ROOT_BINDING")
        # These intrinsic bindings cannot be asserted differently by a factory.
        actual = {"context_sha256": request["context_sha256"], "preparation_sha256": sha(canonical(as_plain(request))),
                  "reference_set_sha256": sha(canonical(as_plain(request["references"]))),
                  "request_sha256": sha(raw), "request_bytes": len(raw),
                  "output_schema_sha256": sha(canonical(wire.output_schema)),
                  "tariff_sha256": sha(canonical(self.tariff)), "namespace_sha256": self.receipt.namespace}
        if any(identities.get(key) != val for key, val in actual.items()):
            raise ValueError("P0_NORMAL_INTRINSIC_BINDING")
        validate_grant(self.grant, identities=identities, now=now)
        proof = preflight(raw, self.grant, self.tariff, self.tokenizer(raw), now=now)
        agent_preparation(request, now)
        if require_unused and self.receipt.exists("RESERVED"):
            raise ValueError("P0_RECEIPT_ALREADY_USED")
        return wire, proof, now

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        with self._lock:
            wire, proof, _ = self._check(request)
            self._authorized = sha(self.body(wire)), sha(canonical(proof))
        return True

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        # try-lock stops simultaneous calls; no queue and no implicit retry.
        if not self._lock.acquire(blocking=False):
            raise ValueError("P0_NORMAL_CONCURRENT_DISPATCH")
        try:
            wire, proof, now = self._check(request)
            identity = sha(self.body(wire)), sha(canonical(proof))
            if self._authorized != identity:
                raise ValueError("P0_NORMAL_AUTHORIZE_REQUIRED")
            self._authorized = None
            technical = _TechnicalP0Port(self, request, wire, proof, now)
            coordinator = GenerationCoordinator(technical)
            preparation = agent_preparation(request, now)
            try:
                _, result = GeneratorAgent(coordinator).generate_production(request=preparation)
                output = guard_and_bind(request, coordinator, preparation, result, observer=self._observe_controls)
            except Exception:
                if self.receipt.exists("RESPONSE_CAPTURED") and not self.receipt.exists("PARSING_REJECTED"):
                    self.receipt.publish("PARSING_REJECTED", self.receipt.event("PARSING_REJECTED", self.grant, proof))
                raise
            self.receipt.publish("PARSED", self.receipt.event("PARSED", self.grant, proof))
            self.receipt.publish("CONSUMED", self.receipt.event("CONSUMED", self.grant, proof))
            return output
        finally:
            self._lock.release()

    @staticmethod
    def technical_result(request: Mapping[str, object], text: str) -> GenerationPortResult:
        lineage = cast(Mapping[str, object], request["lineage"])
        return GenerationPortResult(str(lineage["source_step_id"]), GenerationOperation.GENERATE,
            GenerationPortResultStatus.SUCCEEDED, structured_payload=parse_content(text),
            evidence_refs_used=(), execution_metadata={"source_usage_declaration": "NOT_IN_OUTPUT_SCHEMA", "retry": 0,
                                                        "fallback": "NONE", "review": "NOT_RUN"})

    def confirmed_dispatch(self) -> Mapping[str, object] | None:
        captured = self.receipt.confirmed(self.grant)
        return None if captured is None else captured[0]

    def recover_confirmed(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        captured = self.receipt.confirmed(self.grant)
        if captured is None or canonical(captured[0]) != canonical(as_plain(request)):
            raise ValueError("P0_NORMAL_RECOVERY_BINDING")
        # Compare rebuilt body without identity/clock/tokenizer or authorization.
        wire = build_p0_content_request(request)
        if sha(self.body(wire)) != self.grant["request_sha256"]:
            raise ValueError("P0_NORMAL_RECOVERY_BODY")
        now = self.clock()
        preparation = agent_preparation(request, now)
        # This technical port is never executed by the recovery branch.
        coordinator = GenerationCoordinator(_TechnicalP0Port(self, request, wire, {}, now))
        return guard_and_bind(request, coordinator, preparation, self.technical_result(request, captured[1]), observer=self._observe_controls)

    def _observe_controls(self, value: Mapping[str, object]) -> None:
        self._controls = cast(dict[str, object], as_plain(value))

    def control_evidence(self, *, request: Mapping[str, object], bundle_sha256: str) -> Mapping[str, object]:
        if (self._controls is None or self._controls["bundle_sha256"] != bundle_sha256
                or any(self._controls[key] != request[key] for key in ("production_ref", "version_ref", "context_sha256"))):
            raise ValueError("P0_NORMAL_CONTROLS_BINDING")
        return cast(dict[str, object], as_plain(self._controls))
