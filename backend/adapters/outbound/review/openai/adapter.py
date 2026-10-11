"""ReviewPort adapter backed by one selected OpenAI Review profile."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import NoReturn, cast

from backend.adapters.outbound.openai.contracts import (
    OpenAIIncompleteReason,
    OpenAIReasoningEffort,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransportFactory,
    OpenAITransportError,
)
from backend.adapters.outbound.review.openai.mapping import (
    build_openai_review_request,
    evidence_ref_lookup,
)
from backend.agent_runtime.agents.review import (
    ReviewOperation,
    ReviewPortError,
    ReviewPortErrorCode,
    ReviewPortRequest,
    ReviewPortResult,
    ReviewPortResultStatus,
)
from backend.agent_runtime.contracts.common import ContractRef
from backend.agent_runtime.contracts.review import FindingSeverity, OverallAssessment
from backend.infrastructure.config.schemas.provider import (
    ModelProfileConfig,
    ProviderConfigurationError,
    ProviderConfigurationErrorCode,
    ProviderProfileConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderSecretError,
    ProviderSecretResolver,
)

_EXPECTED_KEYS = {
    "outcome",
    "structured_payload",
    "technical_findings",
    "limitations",
    "warnings",
    "uncertainties",
    "evidence_refs_used",
}
_SEMANTIC_PAYLOAD_KEYS = {
    "overall_assessment",
    "correction_required",
    "coverage",
    "confidence",
}
_ASSESSMENT_PAYLOAD_KEYS = {
    "assessed_finding_ids",
    "blocking_finding_ids",
    "correction_finding_ids",
    "overall_assessment",
    "correction_required",
    "confidence",
}
_FINDING_KEYS = {
    "finding_id",
    "dimension",
    "severity",
    "description",
    "target_locator",
    "rationale",
    "correction_required",
    "evidence_refs",
    "confidence",
    "suggested_action",
}


class _OpenAIReviewDiagnosticCode(StrEnum):
    CONTRACT_MISMATCH = "OPENAI_REVIEW_CONTRACT_MISMATCH"
    INCOMPLETE_MAX_OUTPUT_TOKENS = "OPENAI_REVIEW_INCOMPLETE_MAX_OUTPUT_TOKENS"


class _OpenAIReviewPortError(ReviewPortError):
    diagnostic_code: _OpenAIReviewDiagnosticCode

    def __init__(self, diagnostic_code: _OpenAIReviewDiagnosticCode) -> None:
        self.diagnostic_code = diagnostic_code
        super().__init__(ReviewPortErrorCode.INVALID_RESPONSE)


class OpenAIReviewAdapter:
    """Technical reviewer with no validation, gate, retry, or fallback authority."""

    __slots__ = (
        "_model_profile",
        "_provider_profile",
        "_reasoning_effort",
        "_secret_resolver",
        "_transport_factory",
    )

    def __init__(
        self,
        *,
        provider_profile: ProviderProfileConfig,
        model_profile: ModelProfileConfig,
        secret_resolver: ProviderSecretResolver,
        transport_factory: OpenAIResponsesTransportFactory,
        reasoning_effort: OpenAIReasoningEffort | None = None,
    ) -> None:
        _validate_configuration(provider_profile, model_profile)
        if not isinstance(secret_resolver, ProviderSecretResolver):
            raise TypeError("secret_resolver must satisfy ProviderSecretResolver")
        if reasoning_effort is not None and type(reasoning_effort) is not OpenAIReasoningEffort:
            raise TypeError("reasoning_effort must be an OpenAIReasoningEffort or None")
        self._provider_profile = provider_profile
        self._model_profile = model_profile
        self._reasoning_effort = reasoning_effort
        self._secret_resolver = secret_resolver
        self._transport_factory = transport_factory

    def __repr__(self) -> str:
        return (
            "OpenAIReviewAdapter("
            f"provider_profile_id={self._provider_profile.profile_id.value!r}, "
            f"model_profile_id={self._model_profile.model_profile_id.value!r})"
        )

    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        if type(request) is not ReviewPortRequest:
            raise TypeError("request must be a ReviewPortRequest")
        if ProviderWorkloadKind.REVIEW not in self._model_profile.supported_workloads:
            raise ProviderConfigurationError(
                ProviderConfigurationErrorCode.INCOMPATIBLE_MODEL_WORKLOAD
            )
        provider_request = build_openai_review_request(
            request=request,
            model_profile=self._model_profile,
            reasoning_effort=self._reasoning_effort,
        )
        try:
            secret = self._secret_resolver.resolve(self._provider_profile.credential_ref)
            transport = self._transport_factory.build(
                secret=secret,
                timeout_seconds=(
                    self._model_profile.invocation_limits.call_timeout_milliseconds
                    / 1_000.0
                ),
            )
            response = transport.create(request=provider_request)
        except ProviderSecretError:
            raise ReviewPortError(ReviewPortErrorCode.UNAVAILABLE) from None
        except OpenAITransportError:
            raise ReviewPortError(ReviewPortErrorCode.UNAVAILABLE) from None
        return _map_response(
            request=request,
            response=response,
            provider_profile=self._provider_profile,
            model_profile=self._model_profile,
        )


def _map_response(
    *,
    request: ReviewPortRequest,
    response: OpenAIResponsesResponse,
    provider_profile: ProviderProfileConfig,
    model_profile: ModelProfileConfig,
) -> ReviewPortResult:
    metadata = _execution_metadata(response, provider_profile, model_profile)
    if response.status is OpenAIResponseStatus.REFUSED:
        return ReviewPortResult(
            source_step_id=request.source_step_id,
            operation=request.operation,
            status=ReviewPortResultStatus.REFUSED,
            limitations=({"code": "OPENAI_PROVIDER_REFUSAL"},),
            execution_metadata=metadata,
        )
    if response.status is OpenAIResponseStatus.FAILED:
        raise ReviewPortError(ReviewPortErrorCode.UNAVAILABLE)

    payload = _parse_payload(response)
    if payload["outcome"] != "OUTPUT":
        _invalid_response()
    structured_payload = _structured_payload(payload["structured_payload"], request)
    lookup = evidence_ref_lookup(request.evidence_refs)
    evidence_refs_used = _evidence_refs(payload["evidence_refs_used"], lookup)
    findings = _findings(payload["technical_findings"], request, lookup)
    limitations = _diagnostics(payload["limitations"])
    warnings = _diagnostics(payload["warnings"])
    uncertainties = _diagnostics(payload["uncertainties"])
    _validate_review_coherence(structured_payload, findings, request.operation)
    if response.status is OpenAIResponseStatus.INCOMPLETE:
        warnings += ({"code": "OPENAI_RESPONSE_INCOMPLETE"},)
    # Completeness of a semantic review is separate from its declared knowledge
    # limits. Keep every limitation in the result; P0 quality remains reserved.
    partial = bool(warnings or uncertainties)
    if request.operation is ReviewOperation.SEMANTIC_REVIEW:
        coverage = cast(tuple[str, ...], structured_payload["coverage"])
        partial = partial or set(coverage) != {d.value for d in request.review_dimensions}
    else:
        partial = partial or bool(limitations)
    status = ReviewPortResultStatus.PARTIAL if partial else ReviewPortResultStatus.SUCCEEDED
    try:
        return ReviewPortResult(
            source_step_id=request.source_step_id,
            operation=request.operation,
            status=status,
            structured_payload=structured_payload,
            technical_findings=findings,
            evidence_refs_used=evidence_refs_used,
            limitations=limitations,
            warnings=warnings,
            uncertainties=uncertainties,
            execution_metadata=metadata,
        )
    except (TypeError, ValueError):
        _invalid_response()


def _parse_payload(response: OpenAIResponsesResponse) -> dict[str, object]:
    output_text = response.output_text
    diagnostic_code = _OpenAIReviewDiagnosticCode.CONTRACT_MISMATCH
    if (
        response.status is OpenAIResponseStatus.INCOMPLETE
        and response.incomplete_reason is OpenAIIncompleteReason.MAX_OUTPUT_TOKENS
    ):
        diagnostic_code = _OpenAIReviewDiagnosticCode.INCOMPLETE_MAX_OUTPUT_TOKENS
    if output_text is None:
        _invalid_response(diagnostic_code)
    try:
        payload = json.loads(output_text)
    except (json.JSONDecodeError, TypeError):
        _invalid_response(diagnostic_code)
    if type(payload) is not dict or set(payload) != _EXPECTED_KEYS:
        _invalid_response()
    return cast(dict[str, object], payload)


def _structured_payload(value: object, request: ReviewPortRequest) -> dict[str, object]:
    operation = request.operation
    expected = (
        _SEMANTIC_PAYLOAD_KEYS
        if operation is ReviewOperation.SEMANTIC_REVIEW
        else _ASSESSMENT_PAYLOAD_KEYS
    )
    if type(value) is not dict or set(value) != expected:
        _invalid_response()
    payload = cast(dict[str, object], value)
    if not _valid_confidence(payload["confidence"]):
        _invalid_response()
    if payload["overall_assessment"] not in {item.value for item in OverallAssessment}:
        _invalid_response()
    if type(payload["correction_required"]) is not bool:
        _invalid_response()
    sequence_fields = (
        ("coverage",)
        if operation is ReviewOperation.SEMANTIC_REVIEW
        else (
            "assessed_finding_ids",
            "blocking_finding_ids",
            "correction_finding_ids",
        )
    )
    for field_name in sequence_fields:
        raw = payload[field_name]
        if (
            type(raw) is not list
            or any(type(item) is not str or not item for item in raw)
            or len(raw) != len(set(raw))
        ):
            _invalid_response()
    if operation is ReviewOperation.SEMANTIC_REVIEW:
        coverage = payload["coverage"]
        allowed = {item.value for item in request.review_dimensions}
        if not coverage or not set(cast(list[str], coverage)).issubset(allowed):
            _invalid_response()
    return payload


def _findings(
    value: object,
    request: ReviewPortRequest,
    lookup: Mapping[str, ContractRef],
) -> tuple[Mapping[str, object], ...]:
    if type(value) is not list:
        _invalid_response()
    if request.operation is ReviewOperation.ASSESS_FINDINGS and value:
        _invalid_response()
    result: list[Mapping[str, object]] = []
    finding_ids: set[str] = set()
    allowed_dimensions = {item.value for item in request.review_dimensions}
    allowed_severities = {item.value for item in FindingSeverity}
    for raw in value:
        if type(raw) is not dict or set(raw) != _FINDING_KEYS:
            _invalid_response()
        item = cast(dict[str, object], raw)
        text_fields = ("finding_id", "dimension", "severity", "description", "rationale")
        if any(type(item[field]) is not str or not item[field] for field in text_fields):
            _invalid_response()
        if item["dimension"] not in allowed_dimensions:
            _invalid_response()
        if item["severity"] not in allowed_severities:
            _invalid_response()
        finding_id = cast(str, item["finding_id"])
        if finding_id in finding_ids:
            _invalid_response()
        finding_ids.add(finding_id)
        if type(item["correction_required"]) is not bool:
            _invalid_response()
        if not _valid_locator(item["target_locator"]):
            _invalid_response()
        if not _valid_confidence(item["confidence"]):
            _invalid_response()
        suggested = item["suggested_action"]
        if (
            type(suggested) is not dict
            or set(suggested) != {"code", "message"}
            or any(type(nested) is not str or not nested for nested in suggested.values())
        ):
            _invalid_response()
        normalized = dict(item)
        normalized["evidence_refs"] = _evidence_refs(item["evidence_refs"], lookup)
        result.append(normalized)
    if len(result) > 32:
        _invalid_response()
    return tuple(result)


def _evidence_refs(
    value: object,
    lookup: Mapping[str, ContractRef],
) -> tuple[ContractRef, ...]:
    if type(value) is not list:
        _invalid_response()
    refs: list[ContractRef] = []
    for raw in value:
        try:
            key = json.dumps(
                raw,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError):
            _invalid_response()
        resolved = lookup.get(key)
        if resolved is None or resolved in refs:
            _invalid_response()
        refs.append(resolved)
    return tuple(refs)


def _diagnostics(value: object) -> tuple[Mapping[str, object], ...]:
    if type(value) is not list or len(value) > 32:
        _invalid_response()
    result: list[Mapping[str, object]] = []
    for item in value:
        if type(item) is not dict or set(item) != {"code", "message"}:
            _invalid_response()
        if any(type(nested) is not str or not nested for nested in item.values()):
            _invalid_response()
        result.append(item)
    return tuple(result)


def _valid_confidence(value: object) -> bool:
    return (
        type(value) is dict
        and set(value) == {"level", "basis"}
        and value.get("level") in {"low", "medium", "high"}
        and type(value.get("basis")) is str
        and bool(value.get("basis"))
    )


def _valid_locator(value: object) -> bool:
    if type(value) is not dict:
        return False
    kind = value.get("kind")
    if kind == "whole_target":
        return set(value) == {"kind"}
    if kind == "text_span":
        return (
            set(value) == {"kind", "start", "end", "quote"}
            and type(value.get("start")) is int
            and type(value.get("end")) is int
            and cast(int, value["start"]) >= 0
            and cast(int, value["end"]) > cast(int, value["start"])
            and type(value.get("quote")) is str
            and bool(value.get("quote"))
        )
    if kind == "json_path":
        path = value.get("path")
        return (
            set(value) == {"kind", "path"}
            and type(path) is list
            and bool(path)
            and all(
                (type(segment) is int and segment >= 0)
                or (type(segment) is str and bool(segment))
                for segment in path
            )
        )
    return False


def _validate_review_coherence(
    payload: Mapping[str, object],
    findings: tuple[Mapping[str, object], ...],
    operation: ReviewOperation,
) -> None:
    assessment = payload["overall_assessment"]
    correction_required = payload["correction_required"]
    if assessment == OverallAssessment.ACCEPTABLE.value and correction_required is True:
        _invalid_response()
    if (
        assessment == OverallAssessment.CORRECTION_REQUIRED.value
        and correction_required is not True
    ):
        _invalid_response()
    if operation is ReviewOperation.ASSESS_FINDINGS:
        return
    if any(item["correction_required"] is True for item in findings) and not correction_required:
        _invalid_response()
    coverage = cast(list[str], payload["coverage"])
    if any(item["dimension"] not in coverage for item in findings):
        _invalid_response()


def _execution_metadata(
    response: OpenAIResponsesResponse,
    provider_profile: ProviderProfileConfig,
    model_profile: ModelProfileConfig,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "provider_code": provider_profile.provider_code.value,
        "provider_profile_id": provider_profile.profile_id.value,
        "model_profile_id": model_profile.model_profile_id.value,
        "model_code": model_profile.model_code.value,
        "response_status": response.status.value,
    }
    usage = {
        "input_tokens": response.usage.input_tokens,
        "cached_input_tokens": response.usage.cached_input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    metadata.update({key: value for key, value in usage.items() if value is not None})
    return metadata


def _validate_configuration(
    provider: ProviderProfileConfig,
    model: ModelProfileConfig,
) -> None:
    if type(provider) is not ProviderProfileConfig:
        raise TypeError("provider_profile must be a ProviderProfileConfig")
    if type(model) is not ModelProfileConfig:
        raise TypeError("model_profile must be a ModelProfileConfig")
    if (
        not provider.enabled
        or not model.enabled
        or provider.provider_code.value != "openai"
        or model.provider_profile_id != provider.profile_id
        or not model.structured_output_required
    ):
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
        )


def _invalid_response(
    diagnostic_code: _OpenAIReviewDiagnosticCode = (
        _OpenAIReviewDiagnosticCode.CONTRACT_MISMATCH
    ),
) -> NoReturn:
    raise _OpenAIReviewPortError(diagnostic_code) from None
