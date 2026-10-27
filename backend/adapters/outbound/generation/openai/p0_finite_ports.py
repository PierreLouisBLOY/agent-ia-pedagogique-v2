"""Existing SDK adapters, instrumented by the finite effect owner, no retries."""

from dataclasses import replace
from typing import cast

from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_finite_chain import FiniteChainBroker
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponsesTransport,
    OpenAIResponsesTransportFactory,
)
from backend.adapters.outbound.review.openai.adapter import OpenAIReviewAdapter
from backend.agent_runtime.agents.generation import GenerationPortRequest, GenerationPortResult
from backend.agent_runtime.agents.review import ReviewPortRequest, ReviewPortResult
from backend.agent_runtime.contracts import StepSpec
from backend.agent_runtime.runtime.execution.prelaunch import (
    PreLaunchDecision,
    PreLaunchDisposition,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState
from backend.infrastructure.config.secrets.provider import ProviderSecretValue
from backend.shared_kernel.time import Instant


class FiniteTransportFactory:
    def __init__(
        self, broker: FiniteChainBroker, underlying: OpenAIResponsesTransportFactory
    ) -> None:
        self.broker, self.underlying = broker, underlying

    def build(
        self, *, secret: ProviderSecretValue, timeout_seconds: float
    ) -> OpenAIResponsesTransport:
        self.broker._live()
        inner = self.underlying.build(secret=secret, timeout_seconds=timeout_seconds)
        return _Transport(self.broker, inner)


class _Transport:
    def __init__(self, broker: FiniteChainBroker, inner: OpenAIResponsesTransport) -> None:
        self.broker, self.inner = broker, inner

    def create(self, *, request: OpenAIResponsesRequest) -> OpenAIResponsesResponse:
        return self.broker.dispatch(request, lambda: self.inner.create(request=request))


def _mapping_failure(broker: FiniteChainBroker) -> None:
    if broker.current is not None and broker.current.receipt.exists("RESPONSE_CAPTURED"):
        broker.mapped(successful=False)


class FiniteGenerationPort:
    def __init__(self, broker: FiniteChainBroker, adapter: OpenAIGenerationAdapter) -> None:
        self.broker, self.adapter = broker, adapter

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        role = "CORRECT" if request.operation.value == "CORRECT" else "PROPOSE"
        if request.operation.value not in {"GENERATE", "TRANSFORM", "CORRECT"}:
            raise ValueError("P0_CHAIN_GENERATION_OPERATION")
        self.broker.enter_port(role=role, step_id=request.source_step_id)
        try:
            result = self.adapter.generate(request=request)
        except Exception:
            _mapping_failure(self.broker)
            raise
        proof = self.broker.mapped(successful=result.status.value == "SUCCEEDED")
        return replace(result, execution_metadata={**result.execution_metadata, **proof})


class FiniteReviewPort:
    def __init__(self, broker: FiniteChainBroker, adapter: OpenAIReviewAdapter) -> None:
        self.broker, self.adapter = broker, adapter

    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        active = self.broker.active
        count = 0 if active is None else len(cast(list[object], active["slots"]))
        role = "REVIEW_INITIAL" if count == 1 else "REVIEW_CORRECTED"
        self.broker.enter_port(role=role, step_id=request.source_step_id)
        try:
            result = self.adapter.review(request=request)
        except Exception:
            _mapping_failure(self.broker)
            raise
        required = result.structured_payload.get("correction_required") is True or any(
            f.get("severity") == "blocking" for f in result.technical_findings
        )
        proof = self.broker.mapped(
            successful=result.status.value == "SUCCEEDED", can_correct=required
        )
        return replace(
            result,
            limitations=(
                *result.limitations,
                {"code": "FINITE_EFFECT_RECEIPT", "message": canonical(proof).decode("utf-8")},
            ),
        )


class FinitePreLaunchGuard:
    def __init__(self, broker: FiniteChainBroker) -> None:
        self.broker = broker

    def check(
        self, *, plan: Plan, step: StepSpec, run_state: RunState, now: Instant
    ) -> PreLaunchDecision:
        try:
            self.broker._live()
            if (
                step.permission_scope_ref != "scope:finite:" + self.broker.policy_sha
                or step not in plan.steps
            ):
                raise ValueError("P0_CHAIN_PLAN_SCOPE")
        except ValueError:
            return PreLaunchDecision(PreLaunchDisposition.DENY, "P0_CHAIN_AUTHORITY_UNAVAILABLE")
        return PreLaunchDecision(PreLaunchDisposition.ALLOW)
