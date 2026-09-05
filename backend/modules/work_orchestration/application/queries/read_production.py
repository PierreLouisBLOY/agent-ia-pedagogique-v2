"""CAP-R02 exact-version query over the read port only."""
from dataclasses import dataclass

from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationFailureKind,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.modules.work_orchestration.application.dto.input.read_production import (
    ReadProductionRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import identity
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.ports.outbound.production_store import ProductionStore
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.errors import (
    BusinessError,
    BusinessErrorCategory,
    BusinessErrorCode,
    BusinessErrorDomain,
    BusinessErrorSeverity,
)


@dataclass(frozen=True, slots=True)
class ReadProductionQuery:
    productions: ProductionStore

    def execute(self, request: ReadProductionRequest, *, conversation_id: str,
                correlation_id: CorrelationId) -> ApplicationOutcome[ProductionReadView, object]:
        if type(request) is not ReadProductionRequest or type(correlation_id) is not CorrelationId:
            raise TypeError("INVALID_PRODUCTION_REQUEST")
        identity(conversation_id, "conv")
        try:
            view = self.productions.read_version(conversation_id=conversation_id,
                                                production_ref=request.production_ref,
                                                version_ref=request.version_ref)
            if view is not None:
                if (type(view) is not ProductionReadView or view.conversation_id != conversation_id
                        or view.production_ref != request.production_ref
                        or view.version_ref != request.version_ref):
                    raise ValueError("INCOHERENT_PRODUCTION_STORE")
                return ApplicationOutcome(outcome_status=OutcomeStatus.SUCCESS, success=True,
                                          correlation_id=correlation_id, data=view)
            exists = self.productions.contains_production(
                conversation_id=conversation_id, production_ref=request.production_ref,
            )
        except Exception:
            return ApplicationOutcome(
                outcome_status=OutcomeStatus.FAILED, success=False, correlation_id=correlation_id,
                application_failure=ApplicationFailure(ApplicationFailureKind.AF_PERSISTENCE,
                                                       message_key="production.read_failed"),
            )
        code = "PRODUCTION_VERSION_NOT_FOUND" if exists else "PRODUCTION_NOT_FOUND"
        return ApplicationOutcome(
            outcome_status=OutcomeStatus.REJECTED, success=False, correlation_id=correlation_id,
            business_errors=(BusinessError(
                code=BusinessErrorCode(code), domain=BusinessErrorDomain.PROD,
                category=BusinessErrorCategory.NOT_FOUND, severity=BusinessErrorSeverity.ERROR,
                blocking=True, retryable=False, message_key="production.not_found",
            ),),
        )
