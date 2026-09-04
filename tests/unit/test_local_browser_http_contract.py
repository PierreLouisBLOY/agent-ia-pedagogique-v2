from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from backend.adapters.inbound.api import (
    LocalBrowserHttpDecisionCode,
    LocalBrowserHttpSecurityContract,
)
from backend.infrastructure.config.schemas.http import (
    DEFAULT_HTTP_BIND_HOST,
    LocalBrowserHttpConfiguration,
    LocalHttpConfigurationError,
    LocalHttpConfigurationErrorCode,
)


class RecordingObservability:
    def __init__(self) -> None:
        self.security: list[dict[str, object]] = []
        self.validation: list[dict[str, object]] = []
        self.requests: list[dict[str, object]] = []

    def correlation_id(self, incoming: str | None) -> str:
        return incoming if incoming == "corr-valid" else "corr-generated"

    def http_request(
        self,
        *,
        method: str,
        route_template: str,
        status_code: int,
        duration_ms: int,
        incoming_correlation_id: str | None,
    ) -> str:
        self.requests.append(
            {
                "method": method,
                "route_template": route_template,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "correlation_id": incoming_correlation_id,
            }
        )
        return cast(str, incoming_correlation_id)

    def validation_rejected(
        self,
        *,
        boundary: str,
        rule_code: str,
        field_code: str,
        correlation_id: str,
    ) -> None:
        self.validation.append(
            {
                "boundary": boundary,
                "rule_code": rule_code,
                "field_code": field_code,
                "correlation_id": correlation_id,
            }
        )

    def security_rejected(
        self,
        *,
        runtime_boundary: bool,
        boundary: str,
        policy_code: str,
        correlation_id: str | None = None,
    ) -> None:
        self.security.append(
            {
                "runtime_boundary": runtime_boundary,
                "boundary": boundary,
                "policy_code": policy_code,
                "correlation_id": correlation_id,
            }
        )


def _contract(
    configuration: LocalBrowserHttpConfiguration | None = None,
) -> tuple[LocalBrowserHttpSecurityContract, RecordingObservability]:
    observability = RecordingObservability()
    return (
        LocalBrowserHttpSecurityContract(
            configuration or LocalBrowserHttpConfiguration(port=8765),
            observability,
        ),
        observability,
    )


def test_default_configuration_is_loopback_same_origin_and_closed() -> None:
    configuration = LocalBrowserHttpConfiguration(port=8765)

    assert configuration.bind_host == DEFAULT_HTTP_BIND_HOST == "127.0.0.1"
    assert configuration.cors_enabled is False
    assert configuration.public_summary == {
        "execution_mode": "LOCAL_BROWSER",
        "bind_policy": "LOOPBACK_ONLY",
        "port_policy": "EXPLICIT_REQUIRED",
        "cors_policy": "SAME_ORIGIN_ONLY",
        "debug": False,
        "reload": False,
        "docs": False,
        "stateful_sessions": False,
    }


@pytest.mark.parametrize("bind_host", ["0.0.0.0", "::", "192.168.1.10", "host.local"])
def test_non_loopback_bind_is_rejected_without_echoing_value(bind_host: str) -> None:
    with pytest.raises(LocalHttpConfigurationError) as captured:
        LocalBrowserHttpConfiguration(port=8765, bind_host=bind_host)

    assert captured.value.code is LocalHttpConfigurationErrorCode.NON_LOOPBACK_BIND
    assert bind_host not in str(captured.value)


def test_ipv6_loopback_bind_is_supported_by_contract() -> None:
    configuration = LocalBrowserHttpConfiguration(port=8765, bind_host="::1")

    assert configuration.bind_host == "::1"
    assert "http://[::1]:8765" in configuration.local_origins


def test_explicit_http_default_port_uses_canonical_origin_without_suffix() -> None:
    configuration = LocalBrowserHttpConfiguration(port=80)
    contract, _ = _contract(configuration)

    decision = contract.authorize_request(
        method="GET",
        host_header="localhost",
        origin="http://localhost",
        incoming_correlation_id=None,
    )

    assert "http://localhost" in configuration.local_origins
    assert decision.allowed is True


@pytest.mark.parametrize("port", [0, 65_536, True, "8765"])
def test_port_is_explicit_and_bounded(port: object) -> None:
    with pytest.raises(LocalHttpConfigurationError) as captured:
        LocalBrowserHttpConfiguration(port=cast(int, port))

    assert captured.value.code is LocalHttpConfigurationErrorCode.INVALID_PORT


@pytest.mark.parametrize(
    "host_header",
    ["localhost", "localhost:8765", "127.0.0.1:8765", "[::1]:8765"],
)
def test_local_host_headers_are_allowed(host_header: str) -> None:
    contract, _ = _contract()

    decision = contract.authorize_request(
        method="GET",
        host_header=host_header,
        origin=None,
        incoming_correlation_id="corr-valid",
    )

    assert decision.allowed is True
    assert decision.code is LocalBrowserHttpDecisionCode.ALLOWED
    assert decision.correlation_id == "corr-valid"


@pytest.mark.parametrize(
    "host_header",
    [
        "0.0.0.0:8765",
        "192.168.1.4:8765",
        "example.test",
        "127.0.0.1:9000",
        "http://localhost:8765",
        "localhost@evil.test",
        "::1",
        "[::]",
    ],
)
def test_non_local_or_malformed_host_is_rejected(host_header: str) -> None:
    contract, observability = _contract()

    decision = contract.authorize_request(
        method="GET",
        host_header=host_header,
        origin=None,
        incoming_correlation_id=None,
    )

    assert decision.code is LocalBrowserHttpDecisionCode.HOST_REJECTED
    assert decision.allowed is False
    assert observability.security[-1]["policy_code"] == "HOST_REJECTED"
    assert host_header not in repr(observability.security)


def test_same_origin_is_allowed_and_cross_origin_is_rejected_by_default() -> None:
    contract, _ = _contract()

    allowed = contract.authorize_request(
        method="GET",
        host_header="localhost:8765",
        origin="http://localhost:8765",
        incoming_correlation_id=None,
    )
    rejected = contract.authorize_request(
        method="GET",
        host_header="127.0.0.1:8765",
        origin="http://localhost:8765",
        incoming_correlation_id=None,
    )
    non_local = contract.authorize_request(
        method="GET",
        host_header="localhost:8765",
        origin="https://evil.test",
        incoming_correlation_id=None,
    )

    assert allowed.allowed is True
    assert rejected.code is LocalBrowserHttpDecisionCode.ORIGIN_REJECTED
    assert non_local.code is LocalBrowserHttpDecisionCode.ORIGIN_REJECTED


def test_strict_local_cors_preflight_accepts_only_allowlisted_metadata() -> None:
    configuration = LocalBrowserHttpConfiguration(
        port=8765,
        cors_allowed_origins=("http://localhost:8765",),
    )
    contract, _ = _contract(configuration)

    allowed = contract.authorize_request(
        method="OPTIONS",
        host_header="127.0.0.1:8765",
        origin="http://localhost:8765",
        incoming_correlation_id=None,
        preflight_method="GET",
        preflight_headers=("X-Correlation-ID",),
    )
    rejected_method = contract.authorize_request(
        method="OPTIONS",
        host_header="127.0.0.1:8765",
        origin="http://localhost:8765",
        incoming_correlation_id=None,
        preflight_method="POST",
    )
    rejected_header = contract.authorize_request(
        method="OPTIONS",
        host_header="127.0.0.1:8765",
        origin="http://localhost:8765",
        incoming_correlation_id=None,
        preflight_method="GET",
        preflight_headers=("Authorization",),
    )

    assert allowed.allowed is True
    assert rejected_method.code is LocalBrowserHttpDecisionCode.PREFLIGHT_REJECTED
    assert rejected_header.code is LocalBrowserHttpDecisionCode.PREFLIGHT_REJECTED


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"cors_allowed_origins": ("*",)}, LocalHttpConfigurationErrorCode.WILDCARD_CORS_FORBIDDEN),
        ({"cors_allow_credentials": True}, LocalHttpConfigurationErrorCode.CORS_CREDENTIALS_FORBIDDEN),
        ({"debug": True}, LocalHttpConfigurationErrorCode.DEBUG_FORBIDDEN),
        ({"reload": True}, LocalHttpConfigurationErrorCode.RELOAD_FORBIDDEN),
        ({"docs_enabled": True}, LocalHttpConfigurationErrorCode.DOCS_FORBIDDEN),
        ({"stateful_sessions": True}, LocalHttpConfigurationErrorCode.STATEFUL_SESSION_FORBIDDEN),
    ],
)
def test_permissive_runtime_options_are_rejected(
    overrides: Mapping[str, object],
    code: LocalHttpConfigurationErrorCode,
) -> None:
    with pytest.raises(LocalHttpConfigurationError) as captured:
        LocalBrowserHttpConfiguration(port=8765, **overrides)  # type: ignore[arg-type]

    assert captured.value.code is code


def test_method_rejection_uses_validation_event_and_sanitized_error() -> None:
    contract, observability = _contract()
    decision = contract.authorize_request(
        method="POST",
        host_header="localhost:8765",
        origin=None,
        incoming_correlation_id=None,
    )

    envelope = contract.client_error(decision, status_code=405).as_mapping()

    assert envelope == {
        "status": 405,
        "error_code": "METHOD_REJECTED",
        "correlation_id": "corr-generated",
    }
    assert observability.validation[-1]["rule_code"] == "METHOD_REJECTED"
    assert set(envelope).isdisjoint({"message", "detail", "traceback", "path"})


def test_internal_error_has_no_exception_or_traceback_surface() -> None:
    contract, _ = _contract()

    envelope = contract.internal_error(correlation_id="corr-valid").as_mapping()

    assert envelope == {
        "status": 500,
        "error_code": "INTERNAL_ERROR",
        "correlation_id": "corr-valid",
    }
    assert set(envelope) == {"status", "error_code", "correlation_id"}


def test_completion_reuses_the_b03_correlation_id() -> None:
    contract, observability = _contract()
    decision = contract.authorize_request(
        method="GET",
        host_header="localhost:8765",
        origin=None,
        incoming_correlation_id="corr-valid",
    )

    returned = contract.record_completion(
        decision,
        method="GET",
        route_template="/{unmatched}",
        status_code=204,
        duration_ms=3,
    )

    assert returned == "corr-valid"
    assert observability.requests == [
        {
            "method": "GET",
            "route_template": "/{unmatched}",
            "status_code": 204,
            "duration_ms": 3,
            "correlation_id": "corr-valid",
        }
    ]
