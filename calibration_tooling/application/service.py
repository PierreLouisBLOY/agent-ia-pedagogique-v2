from __future__ import annotations

from calibration_tooling.application.ports import (
    CalibrationOutputParserPort,
    ProviderTransportPort,
)
from calibration_tooling.contracts.errors import (
    CalibrationError,
    CalibrationErrorCode,
    fail_execution,
)
from calibration_tooling.contracts.models import (
    CalibrationObservationSpec,
    ScoredCall,
)


class CalibrationService:
    """One transport invocation followed by the single active parser."""

    def __init__(
        self,
        transport: ProviderTransportPort,
        parser: CalibrationOutputParserPort,
    ) -> None:
        self._transport = transport
        self._parser = parser

    def evaluate(self, spec: CalibrationObservationSpec) -> ScoredCall:
        try:
            response = self._transport.invoke(spec)
        except CalibrationError:
            raise
        except Exception:
            fail_execution(CalibrationErrorCode.PROVIDER_UNAVAILABLE)
        try:
            result = self._parser.parse(spec, response)
        except CalibrationError:
            raise
        except Exception:
            fail_execution(CalibrationErrorCode.PROVIDER_UNAVAILABLE)
        return ScoredCall(result=result, measured_cost_usd=response.measured_cost_usd)
