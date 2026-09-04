from __future__ import annotations

import json
from datetime import UTC, datetime

from backend.adapters.inbound.api import LocalBrowserHttpSecurityContract
from backend.infrastructure.composition.bootstrap.observability import (
    LocalObservabilitySession,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.infrastructure.observability import FailureIsolatedOperationalEventSink

NOW = datetime(2026, 9, 5, 8, 0, tzinfo=UTC)


class MemoryWriter:
    def __init__(self) -> None:
        self.records: list[str] = []

    def write(self, record: str) -> int:
        self.records.append(record)
        return len(record)

    def flush(self) -> None:
        return

    def close(self) -> None:
        return


def test_http_contract_reuses_b03_without_exposing_untrusted_metadata() -> None:
    writer = MemoryWriter()
    monotonic = iter((1.0, 1.1))
    session = LocalObservabilitySession(
        FailureIsolatedOperationalEventSink(writer),
        clock=lambda: NOW,
        monotonic=lambda: next(monotonic),
        correlation_id_factory=lambda: "corr-generated",
    )
    contract = LocalBrowserHttpSecurityContract(
        LocalBrowserHttpConfiguration(port=8765),
        session,
    )

    session.startup(
        app_version="v2.0",
        config_profile_id="local.browser",
        runtime_mode="LOCAL_BROWSER",
    )
    accepted = contract.authorize_request(
        method="GET",
        host_header="localhost:8765",
        origin="http://localhost:8765",
        incoming_correlation_id="corr-incoming",
    )
    contract.record_completion(
        accepted,
        method="GET",
        route_template="/{unmatched}",
        status_code=204,
        duration_ms=4,
    )
    hostile_host = "192.168.1.40:8765"
    hostile_origin = "https://evil.test"
    rejected_host = contract.authorize_request(
        method="GET",
        host_header=hostile_host,
        origin=None,
        incoming_correlation_id=None,
    )
    rejected_origin = contract.authorize_request(
        method="GET",
        host_header="localhost:8765",
        origin=hostile_origin,
        incoming_correlation_id=None,
    )
    contract.record_completion(
        rejected_host,
        method="GET",
        route_template="/{unmatched}",
        status_code=403,
        duration_ms=1,
    )
    session.shutdown()

    events = [json.loads(record) for record in writer.records]
    codes = [event["event"] for event in events]
    serialized = "".join(writer.records)
    assert accepted.correlation_id == "corr-incoming"
    assert rejected_host.allowed is False
    assert rejected_origin.allowed is False
    assert "app.startup" in codes
    assert "http.request.completed" in codes
    assert "http.request.failed" in codes
    assert codes.count("security.runtime_boundary.rejected") == 2
    assert "app.shutdown" in codes
    assert hostile_host not in serialized
    assert hostile_origin not in serialized
    assert "traceback" not in serialized.casefold()


def test_configuration_and_contract_construction_perform_no_network_io() -> None:
    writer = MemoryWriter()
    session = LocalObservabilitySession(
        FailureIsolatedOperationalEventSink(writer),
        clock=lambda: NOW,
        correlation_id_factory=lambda: "corr-generated",
    )

    contract = LocalBrowserHttpSecurityContract(
        LocalBrowserHttpConfiguration(port=8765, bind_host="::1"),
        session,
    )

    assert contract is not None
    assert writer.records == []
