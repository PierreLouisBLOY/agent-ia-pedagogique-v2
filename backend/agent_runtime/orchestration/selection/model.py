from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

from backend.agent_runtime.orchestration.workflows import (
    WorkflowKind,
    WorkflowResponsibility,
)


@dataclass(frozen=True, slots=True)
class WorkflowRequirements:
    application_action_required: bool = False
    external_evidence_required: bool = False
    production_required: bool = False
    independent_review_required: bool = False
    deterministic_validation_required: bool = False
    correction_required: bool = False
    promotion_required: bool = False
    human_gate_required: bool = False
    blocking_ambiguity: bool = False
    parallel_evidence_branches: int = 0
    parallel_evidence_independent: bool = False
    variant_count: int = 0
    variants_explicitly_useful: bool = False

    def __post_init__(self) -> None:
        self._validate_strict_types()
        if self.correction_required and self.production_required:
            raise ValueError("correction_required and production_required are mutually exclusive")
        if self.parallel_evidence_branches > 0 and not self.external_evidence_required:
            raise ValueError("parallel evidence branches require external evidence")
        if (
            self.parallel_evidence_independent
            and self.parallel_evidence_branches < 2
        ):
            raise ValueError("independent parallel evidence requires at least two branches")
        if self.variant_count > 0 and not self.production_required:
            raise ValueError("variants require production")
        if self.variant_count >= 2 and not self.variants_explicitly_useful:
            raise ValueError("multiple variants must be explicitly useful")
        if self.variants_explicitly_useful and self.variant_count < 2:
            raise ValueError("explicitly useful variants require at least two variants")
        if self.blocking_ambiguity and not self.human_gate_required:
            raise ValueError("blocking ambiguity requires a human gate")
        if not self._has_substantive_requirement() and not self.blocking_ambiguity:
            raise ValueError("at least one substantive workflow requirement is required")

    def _validate_strict_types(self) -> None:
        count_fields = {"parallel_evidence_branches", "variant_count"}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in count_fields:
                if type(value) is not int:
                    raise TypeError(f"{field.name} must be an integer")
                if value < 0:
                    raise ValueError(f"{field.name} must be >= 0")
            elif type(value) is not bool:
                raise TypeError(f"{field.name} must be a bool")

    def _has_substantive_requirement(self) -> bool:
        return any(
            (
                self.application_action_required,
                self.external_evidence_required,
                self.production_required,
                self.independent_review_required,
                self.deterministic_validation_required,
                self.correction_required,
                self.promotion_required,
                self.human_gate_required,
            )
        )


class WorkflowSelectionStatus(StrEnum):
    SELECTED = "selected"
    WAITING_HUMAN = "waiting_human"


class WorkflowSelectionReason(StrEnum):
    DIRECT_APPLICATION_REQUIRED = "DIRECT_APPLICATION_REQUIRED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    GENERATION_REQUIRED = "GENERATION_REQUIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    DETERMINISTIC_VALIDATION_REQUIRED = "DETERMINISTIC_VALIDATION_REQUIRED"
    PARALLEL_EVIDENCE_ADMISSIBLE = "PARALLEL_EVIDENCE_ADMISSIBLE"
    PARALLEL_EVIDENCE_NOT_ADMISSIBLE = "PARALLEL_EVIDENCE_NOT_ADMISSIBLE"
    VARIANTS_EXPLICITLY_USEFUL = "VARIANTS_EXPLICITLY_USEFUL"
    HUMAN_GATE_REQUIRED = "HUMAN_GATE_REQUIRED"
    BLOCKING_AMBIGUITY = "BLOCKING_AMBIGUITY"
    PROMOTION_REQUIRED = "PROMOTION_REQUIRED"
    MINIMAL_CANONICAL_PATH = "MINIMAL_CANONICAL_PATH"


@dataclass(frozen=True, slots=True)
class WorkflowSelectionStage:
    workflow_kind: WorkflowKind
    materialized_optional_responsibilities: tuple[WorkflowResponsibility, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_kind, WorkflowKind):
            raise TypeError("workflow_kind must be a WorkflowKind")
        if not isinstance(self.materialized_optional_responsibilities, tuple):
            raise TypeError("materialized_optional_responsibilities must be a tuple")
        if any(
            not isinstance(item, WorkflowResponsibility)
            for item in self.materialized_optional_responsibilities
        ):
            raise TypeError(
                "materialized_optional_responsibilities must contain "
                "WorkflowResponsibility values"
            )
        if len(set(self.materialized_optional_responsibilities)) != len(
            self.materialized_optional_responsibilities
        ):
            raise ValueError("materialized_optional_responsibilities must be unique")


@dataclass(frozen=True, slots=True)
class WorkflowSelectionDecision:
    status: WorkflowSelectionStatus
    stages: tuple[WorkflowSelectionStage, ...]
    overlays: tuple[WorkflowKind, ...]
    reasons: tuple[WorkflowSelectionReason, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, WorkflowSelectionStatus):
            raise TypeError("status must be a WorkflowSelectionStatus")
        self._validate_tuples()
        if any(item is not WorkflowKind.WF_10 for item in self.overlays):
            raise ValueError("overlays may contain only WF-10")
        if len(set(self.overlays)) != len(self.overlays):
            raise ValueError("overlays must be unique")
        if not self.reasons:
            raise ValueError("reasons must not be empty")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("reasons must be unique")
        if any(
            left == right
            for left, right in zip(self.stages, self.stages[1:], strict=False)
        ):
            raise ValueError("identical adjacent stages are forbidden")
        if self.status is WorkflowSelectionStatus.SELECTED:
            if not self.stages:
                raise ValueError("SELECTED requires at least one stage")
        elif self.stages != () or self.overlays != (WorkflowKind.WF_10,):
            raise ValueError("WAITING_HUMAN requires no stages and exactly the WF-10 overlay")

    def _validate_tuples(self) -> None:
        if not isinstance(self.stages, tuple):
            raise TypeError("stages must be a tuple")
        if any(not isinstance(item, WorkflowSelectionStage) for item in self.stages):
            raise TypeError("stages must contain WorkflowSelectionStage values")
        if not isinstance(self.overlays, tuple):
            raise TypeError("overlays must be a tuple")
        if any(not isinstance(item, WorkflowKind) for item in self.overlays):
            raise TypeError("overlays must contain WorkflowKind values")
        if not isinstance(self.reasons, tuple):
            raise TypeError("reasons must be a tuple")
        if any(not isinstance(item, WorkflowSelectionReason) for item in self.reasons):
            raise TypeError("reasons must contain WorkflowSelectionReason values")
