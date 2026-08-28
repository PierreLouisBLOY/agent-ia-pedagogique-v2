from __future__ import annotations

from typing import Protocol, runtime_checkable

from evaluation_harness.contracts.identity import (
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
)
from evaluation_harness.contracts.runner import (
    EvaluationDeadline,
    EvaluationRepetitionContext,
    TargetExecutionOutcome,
)
from evaluation_harness.contracts.target import EvaluationTargetRef


class FixtureNotFoundError(LookupError):
    pass


class InputFactoryNotFoundError(LookupError):
    pass


class TargetExecutorNotFoundError(LookupError):
    pass


@runtime_checkable
class PreparedEvaluationInput(Protocol):
    @property
    def evaluation_input_marker(self) -> None: ...


@runtime_checkable
class EvaluationFixtureHandle(Protocol):
    @property
    def evaluation_fixture_marker(self) -> None: ...


class EvaluationClockPort(Protocol):
    def now_seconds(self) -> int: ...


class EvaluationInputFactoryPort(Protocol):
    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput: ...


class EvaluationFixtureFactoryPort(Protocol):
    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle: ...

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None: ...


class EvaluationTargetExecutorPort(Protocol):
    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome: ...
