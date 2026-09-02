"""Anthropic implementation of the active B02 provider transport port."""

from __future__ import annotations

from typing import NoReturn

from calibration_tooling.adapters.anthropic.contracts import (
    AnthropicProjectionPayload,
    AnthropicProjectionSource,
    AnthropicScoringTransport,
    AnthropicTransportError,
    AnthropicTransportErrorCode,
    ResolvedAnthropicConfiguration,
)
from calibration_tooling.adapters.anthropic.mapping import (
    build_anthropic_scoring_request,
)
from calibration_tooling.adapters.anthropic.parser import parse_anthropic_response
from calibration_tooling.contracts.errors import (
    CalibrationError,
    CalibrationErrorCode,
    fail_contract,
    fail_execution,
)
from calibration_tooling.contracts.models import (
    AbsoluteObservationSpec,
    CalibrationObservationSpec,
    PairwiseObservationSpec,
    RawProviderResponse,
)


class AnthropicCalibrationScorer:
    """Map one active spec to one Anthropic request without retry or persistence."""

    __slots__ = ("_configuration", "_projection_source", "_transport")

    def __init__(
        self,
        *,
        configuration: ResolvedAnthropicConfiguration,
        projection_source: AnthropicProjectionSource,
        transport: AnthropicScoringTransport,
    ) -> None:
        if type(configuration) is not ResolvedAnthropicConfiguration:
            raise TypeError("configuration must be resolved")
        self._configuration = configuration
        self._projection_source = projection_source
        self._transport = transport

    def __repr__(self) -> str:
        return f"AnthropicCalibrationScorer(model={self._configuration.model!r})"

    def invoke(self, spec: CalibrationObservationSpec) -> RawProviderResponse:
        if type(spec) not in (AbsoluteObservationSpec, PairwiseObservationSpec):
            fail_contract(CalibrationErrorCode.INVALID_CONTRACT)
        try:
            payload = self._projection_source.load(spec.call_ref)
        except CalibrationError:
            raise
        except Exception:
            fail_contract(CalibrationErrorCode.TRANSFER_SCOPE_MISMATCH)
        if type(payload) is not AnthropicProjectionPayload or payload.call_ref != spec.call_ref:
            fail_contract(CalibrationErrorCode.TRANSFER_SCOPE_MISMATCH)
        request = build_anthropic_scoring_request(
            spec=spec,
            payload=payload,
            configuration=self._configuration,
        )
        try:
            response = self._transport.create(request=request)
        except AnthropicTransportError as error:
            _fail_for_transport(error)
        except Exception:
            fail_execution(CalibrationErrorCode.PROVIDER_UNAVAILABLE)
        return parse_anthropic_response(
            spec=spec,
            response=response,
            pricing=self._configuration.pricing,
        )


def _fail_for_transport(error: AnthropicTransportError) -> NoReturn:
    if error.code is AnthropicTransportErrorCode.CREDENTIAL_UNAVAILABLE:
        fail_execution(CalibrationErrorCode.CREDENTIAL_UNAVAILABLE)
    if error.code is AnthropicTransportErrorCode.RESPONSE_INVALID:
        fail_contract(CalibrationErrorCode.RESPONSE_INVALID)
    fail_execution(CalibrationErrorCode.PROVIDER_UNAVAILABLE)
