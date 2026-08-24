from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.orchestration.selection.model import (
    WorkflowRequirements,
    WorkflowSelectionDecision,
    WorkflowSelectionReason,
    WorkflowSelectionStage,
    WorkflowSelectionStatus,
)
from backend.agent_runtime.orchestration.workflows import (
    BASELINE_WORKFLOW_CATALOG,
    WorkflowCatalog,
    WorkflowKind,
    WorkflowResponsibility,
    WorkflowTopologyDescriptor,
)

R = WorkflowResponsibility
Reason = WorkflowSelectionReason


class WorkflowSelectionError(ValueError):
    """Safe refusal when explicit requirements cannot map to the catalogue."""


@dataclass(frozen=True, slots=True)
class WorkflowSelector:
    catalog: WorkflowCatalog = BASELINE_WORKFLOW_CATALOG

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, WorkflowCatalog):
            raise TypeError("catalog must be a WorkflowCatalog")

    def select(self, requirements: WorkflowRequirements) -> WorkflowSelectionDecision:
        if not isinstance(requirements, WorkflowRequirements):
            raise WorkflowSelectionError("requirements must be WorkflowRequirements")
        if requirements.blocking_ambiguity:
            self._require_overlay(WorkflowKind.WF_10)
            return WorkflowSelectionDecision(
                status=WorkflowSelectionStatus.WAITING_HUMAN,
                stages=(),
                overlays=(WorkflowKind.WF_10,),
                reasons=(Reason.BLOCKING_AMBIGUITY, Reason.HUMAN_GATE_REQUIRED),
            )
        if requirements.application_action_required and self._has_agentic_work(
            requirements
        ):
            raise WorkflowSelectionError(
                "an additional Application action with agentic work must be normalized"
            )

        reasons = self._explicit_reasons(requirements)
        stages = self._select_stages(requirements, reasons)
        overlays: tuple[WorkflowKind, ...] = ()
        if requirements.human_gate_required:
            self._require_overlay(WorkflowKind.WF_10)
            overlays = (WorkflowKind.WF_10,)
        reasons.add(Reason.MINIMAL_CANONICAL_PATH)
        return self._decision(stages, overlays, reasons)

    @staticmethod
    def _has_agentic_work(requirements: WorkflowRequirements) -> bool:
        return any(
            (
                requirements.external_evidence_required,
                requirements.production_required,
                requirements.independent_review_required,
                requirements.correction_required,
            )
        )

    @staticmethod
    def _explicit_reasons(
        requirements: WorkflowRequirements,
    ) -> set[WorkflowSelectionReason]:
        reasons: set[WorkflowSelectionReason] = set()
        if requirements.application_action_required:
            reasons.add(Reason.DIRECT_APPLICATION_REQUIRED)
        if requirements.external_evidence_required:
            reasons.add(Reason.EVIDENCE_REQUIRED)
        if requirements.production_required:
            reasons.add(Reason.GENERATION_REQUIRED)
        if requirements.independent_review_required:
            reasons.add(Reason.REVIEW_REQUIRED)
        if requirements.correction_required:
            reasons.add(Reason.CORRECTION_REQUIRED)
        if requirements.deterministic_validation_required:
            reasons.add(Reason.DETERMINISTIC_VALIDATION_REQUIRED)
        if requirements.variants_explicitly_useful:
            reasons.add(Reason.VARIANTS_EXPLICITLY_USEFUL)
        if requirements.human_gate_required:
            reasons.add(Reason.HUMAN_GATE_REQUIRED)
        if requirements.promotion_required:
            reasons.add(Reason.PROMOTION_REQUIRED)
        return reasons

    def _select_stages(
        self,
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> list[WorkflowSelectionStage]:
        stages: list[WorkflowSelectionStage]
        if requirements.correction_required:
            stages = self._correction_stages(requirements, reasons)
        elif requirements.variant_count >= 2:
            stages = self._variant_stages(requirements, reasons)
        elif requirements.production_required:
            stages = self._production_stages(requirements, reasons)
        else:
            stages = self._non_production_stages(requirements, reasons)

        if requirements.promotion_required:
            stages.append(self._stage(WorkflowKind.WF_11))
        if not stages:
            raise WorkflowSelectionError("requirements do not identify a selectable base workflow")
        return stages

    def _correction_stages(
        self,
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> list[WorkflowSelectionStage]:
        stages = self._evidence_prefix(requirements, reasons)
        optional = (R.REVIEW,) if requirements.independent_review_required else ()
        stages.append(self._stage(WorkflowKind.WF_7, optional))
        if requirements.deterministic_validation_required:
            stages.append(self._stage(WorkflowKind.WF_0))
        return stages

    def _variant_stages(
        self,
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> list[WorkflowSelectionStage]:
        stages = self._evidence_prefix(requirements, reasons)
        stages.append(self._stage(WorkflowKind.WF_9))
        if requirements.deterministic_validation_required:
            stages.append(self._stage(WorkflowKind.WF_0))
        if requirements.independent_review_required:
            stages.append(self._stage(WorkflowKind.WF_3))
        return stages

    def _production_stages(
        self,
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> list[WorkflowSelectionStage]:
        validation = (
            (R.DETERMINISTIC_VALIDATION,)
            if requirements.deterministic_validation_required
            else ()
        )
        if requirements.external_evidence_required and requirements.independent_review_required:
            stages = self._parallel_evidence_handoff(requirements, reasons)
            stages.append(self._stage(WorkflowKind.WF_6))
            return stages
        if requirements.external_evidence_required:
            stages = self._parallel_evidence_handoff(requirements, reasons)
            stages.append(self._stage(WorkflowKind.WF_4, validation))
            return stages
        if requirements.independent_review_required:
            return [self._stage(WorkflowKind.WF_5, validation)]
        return [self._stage(WorkflowKind.WF_2, validation)]

    def _non_production_stages(
        self,
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> list[WorkflowSelectionStage]:
        stages = self._evidence_prefix(requirements, reasons)
        if requirements.deterministic_validation_required:
            stages.append(self._stage(WorkflowKind.WF_0))
        elif requirements.application_action_required:
            stages.append(self._stage(WorkflowKind.WF_0))
        if requirements.independent_review_required:
            stages.append(self._stage(WorkflowKind.WF_3))
        return stages

    def _parallel_evidence_handoff(
        self,
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> list[WorkflowSelectionStage]:
        if self._parallel_evidence_admissible(requirements, reasons):
            return [self._stage(WorkflowKind.WF_8)]
        return []

    def _evidence_prefix(
        self,
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> list[WorkflowSelectionStage]:
        if not requirements.external_evidence_required:
            return []
        kind = (
            WorkflowKind.WF_8
            if self._parallel_evidence_admissible(requirements, reasons)
            else WorkflowKind.WF_1
        )
        return [self._stage(kind)]

    @staticmethod
    def _parallel_evidence_admissible(
        requirements: WorkflowRequirements,
        reasons: set[WorkflowSelectionReason],
    ) -> bool:
        if requirements.parallel_evidence_branches < 2:
            return False
        if requirements.parallel_evidence_independent:
            reasons.add(Reason.PARALLEL_EVIDENCE_ADMISSIBLE)
            return True
        reasons.add(Reason.PARALLEL_EVIDENCE_NOT_ADMISSIBLE)
        return False

    def _stage(
        self,
        workflow_kind: WorkflowKind,
        optional: tuple[WorkflowResponsibility, ...] = (),
    ) -> WorkflowSelectionStage:
        descriptor = self._descriptor(workflow_kind)
        if any(item not in descriptor.optional_responsibilities for item in optional):
            raise WorkflowSelectionError(
                f"optional responsibilities are incompatible with {workflow_kind.value}"
            )
        return WorkflowSelectionStage(workflow_kind, optional)

    def _require_overlay(self, workflow_kind: WorkflowKind) -> None:
        descriptor = self._descriptor(workflow_kind)
        if not descriptor.overlay:
            raise WorkflowSelectionError(f"{workflow_kind.value} is not an overlay")

    def _descriptor(self, workflow_kind: WorkflowKind) -> WorkflowTopologyDescriptor:
        try:
            return self.catalog.get(workflow_kind)
        except LookupError as error:
            raise WorkflowSelectionError(
                f"catalog is missing required workflow {workflow_kind.value}"
            ) from error

    def _decision(
        self,
        stages: list[WorkflowSelectionStage],
        overlays: tuple[WorkflowKind, ...],
        reasons: set[WorkflowSelectionReason],
    ) -> WorkflowSelectionDecision:
        for stage in stages:
            descriptor = self._descriptor(stage.workflow_kind)
            if any(
                item not in descriptor.optional_responsibilities
                for item in stage.materialized_optional_responsibilities
            ):
                raise WorkflowSelectionError(
                    f"optional responsibilities are incompatible with {stage.workflow_kind.value}"
                )
        ordered_reasons = tuple(reason for reason in WorkflowSelectionReason if reason in reasons)
        return WorkflowSelectionDecision(
            status=WorkflowSelectionStatus.SELECTED,
            stages=tuple(stages),
            overlays=overlays,
            reasons=ordered_reasons,
        )
