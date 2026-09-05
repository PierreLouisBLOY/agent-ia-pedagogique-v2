"""C-12/C-13 bridge for the registered application.read_production capability."""
from collections.abc import Mapping

from backend.agent_runtime.contracts import ContractMeta, UseCaseRequest, UseCaseResult
from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.work_orchestration.application.dto.input.read_production import (
    ReadProductionRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import identity, plain
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.ports.inbound.production_read import ProductionReadInbound

PRODUCTION_USE_CASE_ID = "application.read_production"


def validate_production_projection(data: Mapping[str, object]) -> None:
    lineage = data.get("lineage")
    if not isinstance(lineage, Mapping):
        raise ValueError("INVALID_PRODUCTION_VIEW")
    ProductionReadView(identity(data.get("production_ref"), "prod"),
        identity(data.get("version_ref"), "ver"), identity(lineage.get("conversation_id"), "conv"), data)


class ProductionUseCaseInbound:
    def __init__(self, query: ProductionReadInbound, *, conversation_id: str) -> None:
        if not isinstance(query, ProductionReadInbound):
            raise TypeError("PRODUCTION_READ_INBOUND_REQUIRED")
        self._query = query
        self._conversation_id = identity(conversation_id, "conv")

    def invoke(self, *, request: UseCaseRequest) -> UseCaseResult[object, object]:
        if type(request) is not UseCaseRequest or request.use_case_id != PRODUCTION_USE_CASE_ID:
            raise ValueError("UNSUPPORTED_PRODUCTION_USE_CASE")
        if set(request.payload) != {"production_ref", "version_ref"}:
            raise ValueError("VALIDATION_REJECTED")
        typed = ReadProductionRequest(identity(request.payload["production_ref"], "prod"),
                                      identity(request.payload["version_ref"], "ver"))
        result = self._query.execute(typed, conversation_id=self._conversation_id,
                                     correlation_id=request.meta.correlation_id)
        if (result.correlation_id != request.meta.correlation_id or result.side_effects
                or result.operation_ref is not None or result.task_ref is not None):
            raise ValueError("INVALID_PRODUCTION_OUTCOME")
        outcome: ApplicationOutcome[object, object] = ApplicationOutcome(
            outcome_status=result.outcome_status, success=result.success,
            correlation_id=result.correlation_id,
            data=plain(result.data.data) if result.data else None,
            business_errors=result.business_errors, application_failure=result.application_failure,
            warnings=result.warnings, subject_refs=result.subject_refs,
        )
        return UseCaseResult(
            meta=ContractMeta(schema_version=request.meta.schema_version,
                              run_id=request.meta.run_id, step_id=request.meta.step_id,
                              parent_step_id=request.meta.parent_step_id,
                              correlation_id=request.meta.correlation_id,
                              created_at=request.meta.created_at, actor=request.meta.actor,
                              status=outcome.outcome_status, trace_flags=request.meta.trace_flags),
            use_case_id=request.use_case_id, outcome=outcome,
        )
