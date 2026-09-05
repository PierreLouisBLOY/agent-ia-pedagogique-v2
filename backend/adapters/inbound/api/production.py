"""CAP-R02 HTTP projection over a closed Application invocation."""
import re
from collections.abc import Callable, Mapping

from backend.adapters.inbound.api.conversation import conversation_error, envelope
from backend.adapters.inbound.application.conversation import ConversationInputError
from backend.adapters.inbound.application.production import validate_production_projection
from backend.agent_runtime.contracts import UseCaseResult


class ProductionEndpoint:
    def __init__(self, invoke: Callable[[str, str, str], UseCaseResult[object, object]]) -> None:
        self._invoke = invoke

    def get(self, production: str, version: str, correlation: str) -> tuple[int, bytes]:
        if (re.fullmatch(r"prod:[0-9a-f]{32}", production) is None
                or re.fullmatch(r"ver:[0-9a-f]{32}", version) is None):
            return conversation_error("VALIDATION_REJECTED", correlation)
        try:
            result = self._invoke(production, version, correlation)
            outcome = result.outcome
            if (result.use_case_id != "application.read_production"
                    or result.meta.correlation_id.value != correlation
                    or outcome.correlation_id.value != correlation or outcome.side_effects
                    or outcome.operation_ref is not None or outcome.task_ref is not None
                    or outcome.application_failure is not None or result.error is not None
                    or result.domain_events):
                raise ValueError("INVALID_PRODUCTION_OUTCOME")
            if not outcome.success:
                if len(outcome.business_errors) == 1 and outcome.business_errors[0].code.value in {
                    "PRODUCTION_NOT_FOUND", "PRODUCTION_VERSION_NOT_FOUND",
                }:
                    return conversation_error(outcome.business_errors[0].code.value, correlation)
                raise ValueError("INVALID_PRODUCTION_OUTCOME")
            data = outcome.data
            if (not isinstance(data, Mapping) or data.get("production_ref") != production
                    or data.get("version_ref") != version or data.get("validation_state") != "CANDIDATE"):
                raise ValueError("INVALID_PRODUCTION_VIEW")
            validate_production_projection(data)
            return 200, envelope(dict(data), correlation)
        except ConversationInputError as error:
            return conversation_error(error.code, correlation)
        except Exception:
            return conversation_error("APPLICATION_FAILURE", correlation)
