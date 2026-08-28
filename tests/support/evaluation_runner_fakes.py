from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from evaluation_harness import (
    EvaluationDeadline,
    EvaluationFixtureHandle,
    EvaluationFixtureRef,
    EvaluationInputFactoryRef,
    EvaluationRepetitionContext,
    EvaluationTargetRef,
    FixtureNotFoundError,
    InputFactoryNotFoundError,
    PreparedEvaluationInput,
    TargetExecutionOutcome,
    TargetExecutorNotFoundError,
)


@dataclass(slots=True)
class FreshPreparedInput:
    repetition_index: int
    state: list[str] = field(default_factory=list)

    @property
    def evaluation_input_marker(self) -> None:
        return None


@dataclass(slots=True)
class FreshFixtureHandle:
    repetition_index: int
    state: list[str] = field(default_factory=list)

    @property
    def evaluation_fixture_marker(self) -> None:
        return None


class RecordingClock:
    def __init__(self, current_second: int = 0) -> None:
        self.current_second = current_second
        self.calls: list[int] = []

    def now_seconds(self) -> int:
        self.calls.append(self.current_second)
        return self.current_second


class RecordingInputFactory:
    def __init__(
        self,
        *,
        error: BaseException | None = None,
        missing: bool = False,
    ) -> None:
        self.error = error
        self.missing = missing
        self.calls: list[
            tuple[EvaluationInputFactoryRef, EvaluationRepetitionContext]
        ] = []
        self.inputs: list[FreshPreparedInput] = []

    def build(
        self,
        input_factory_ref: EvaluationInputFactoryRef,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        self.calls.append((input_factory_ref, context))
        if self.missing:
            raise InputFactoryNotFoundError
        if self.error is not None:
            raise self.error
        prepared = FreshPreparedInput(context.repetition_index)
        self.inputs.append(prepared)
        return prepared


class RecordingFixtureFactory:
    def __init__(
        self,
        *,
        create_error: BaseException | None = None,
        cleanup_error: BaseException | None = None,
        missing: bool = False,
    ) -> None:
        self.create_error = create_error
        self.cleanup_error = cleanup_error
        self.missing = missing
        self.create_calls: list[
            tuple[EvaluationFixtureRef, EvaluationRepetitionContext]
        ] = []
        self.cleanup_calls: list[
            tuple[FreshFixtureHandle, EvaluationRepetitionContext]
        ] = []
        self.handles: list[FreshFixtureHandle] = []

    def create(
        self,
        fixture_ref: EvaluationFixtureRef,
        context: EvaluationRepetitionContext,
    ) -> EvaluationFixtureHandle:
        self.create_calls.append((fixture_ref, context))
        if self.missing:
            raise FixtureNotFoundError
        if self.create_error is not None:
            raise self.create_error
        handle = FreshFixtureHandle(context.repetition_index)
        self.handles.append(handle)
        return handle

    def cleanup(
        self,
        handle: EvaluationFixtureHandle,
        context: EvaluationRepetitionContext,
    ) -> None:
        if not isinstance(handle, FreshFixtureHandle):
            raise TypeError("test fixture handle must be FreshFixtureHandle")
        self.cleanup_calls.append((handle, context))
        if self.cleanup_error is not None:
            raise self.cleanup_error


type TargetBehavior = Callable[
    [
        EvaluationTargetRef,
        PreparedEvaluationInput,
        EvaluationFixtureHandle | None,
        EvaluationRepetitionContext,
        EvaluationDeadline,
    ],
    TargetExecutionOutcome,
]


class RecordingTargetExecutor:
    def __init__(
        self,
        *outcomes: TargetExecutionOutcome | BaseException | TargetBehavior,
        missing: bool = False,
    ) -> None:
        self._outcomes = outcomes
        self.missing = missing
        self.calls: list[
            tuple[
                EvaluationTargetRef,
                PreparedEvaluationInput,
                EvaluationFixtureHandle | None,
                EvaluationRepetitionContext,
                EvaluationDeadline,
            ]
        ] = []

    def execute(
        self,
        target: EvaluationTargetRef,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        self.calls.append((target, prepared_input, fixture, context, deadline))
        if self.missing:
            raise TargetExecutorNotFoundError
        index = len(self.calls) - 1
        if index >= len(self._outcomes):
            raise RuntimeError("no synthetic target outcome configured")
        outcome = self._outcomes[index]
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome(target, prepared_input, fixture, context, deadline)
        return outcome
