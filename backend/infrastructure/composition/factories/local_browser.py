"""Explicit local READ-15 composition, with no provisioning, migrations or credentials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from backend.adapters.inbound.api.read15 import Read15Endpoint, Read15ValidationRejected
from backend.adapters.inbound.api.routes import ASSET_NAMES
from backend.adapters.inbound.api.server import LocalRead15Server, LocalRead15Service
from backend.adapters.inbound.application.resource_library import ResourceLibraryUseCaseInbound
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.sqlite import SQLiteResourceStoreAdapter
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    UseCaseRequest,
    UseCaseResult,
)
from backend.core_contracts.invocation import UseCaseContext
from backend.infrastructure.composition.bootstrap.observability import (
    LocalObservabilitySession,
    build_local_observability_session,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.infrastructure.filesystem import (
    assert_local_data_root,
    capture_secure_path,
    hash_file_nofollow,
    read_file_nofollow,
)
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.domain.errors import InvalidResourceRefError
from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_ROOT = Path(__file__).resolve().parents[4]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Read15RuntimeTarget:
    runtime_path: Path
    data_root: Path
    expected_sha256: str

    def validate(self) -> None:
        if _SHA256.fullmatch(self.expected_sha256) is None:
            raise ValueError("RUNTIME_IDENTITY_REQUIRED")
        root = assert_local_data_root(self.data_root)
        if root == _ROOT or root.is_relative_to(_ROOT):
            raise ValueError("RUNTIME_OUTSIDE_REPOSITORY_REQUIRED")
        snapshot = capture_secure_path(self.runtime_path, allowed_root=root)
        if not snapshot.is_file:
            raise ValueError("EXISTING_RUNTIME_REQUIRED")
        if hash_file_nofollow(snapshot.path, allowed_root=root) != self.expected_sha256:
            raise ValueError("RUNTIME_IDENTITY_MISMATCH")


@dataclass(slots=True)
class LocalRead15Composition:
    server: LocalRead15Server
    observability: LocalObservabilitySession
    _closed: bool = False

    @property
    def url(self) -> str:
        configuration = self.server.service.configuration
        host = "[::1]" if configuration.bind_host == "::1" else configuration.bind_host
        return f"http://{host}:{configuration.port}/"

    def serve_forever(self) -> None:
        if self._closed:
            raise ValueError("COMPOSITION_CLOSED")
        self.server.serve_forever()

    def close(self) -> float:
        if self._closed:
            return 0.0
        self._closed = True
        self.server.stop()
        return self.observability.shutdown()


def _application_reader(target: Read15RuntimeTarget) -> Read15Endpoint:
    def invoke(reference: str, correlation: str) -> UseCaseResult[object, object]:
        try:
            ResourceRef(reference)
        except (InvalidResourceRefError, TypeError):
            raise Read15ValidationRejected("READ15_REQUEST_REJECTED") from None
        target.validate()
        store = SQLiteResourceStoreAdapter(
            connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
        )
        try:
            inbound = ResourceLibraryUseCaseInbound(GetResourceQuery(store))
            correlation_id = CorrelationId(correlation)
            request = UseCaseRequest(
                meta=ContractMeta(
                    schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                    run_id="local-read15", step_id="local-read15-read", parent_step_id=None,
                    correlation_id=correlation_id, created_at=Instant(datetime.now(UTC)),
                    actor=ActorRef(ActorKind.APPLICATION, "local-read15"),
                    status=InvocationStatus.PLANNED,
                ),
                use_case_id="application.read_canonical_resource",
                payload={"resource_ref": reference},
                actor_context=UseCaseContext(correlation_id),
            )
            return inbound.invoke(request=request)
        finally:
            store.close()
    return Read15Endpoint(invoke)


def build_local_read15(
    configuration: LocalBrowserHttpConfiguration, target: Read15RuntimeTarget,
) -> LocalRead15Composition:
    """Receive an explicit existing target; never read ambient environment settings."""
    target.validate()
    # Verify that the authenticated supplied fixture can open as a query-only reader.
    connection = connect_sqlite(
        target.runtime_path, readonly=True, allowed_root=target.data_root
    )
    connection.close()
    assets_root = _ROOT / "frontend"
    assets = {
        name: read_file_nofollow(
            assets_root / name, allowed_root=assets_root, maximum_bytes=128 * 1_024
        )
        for name in sorted(ASSET_NAMES)
    }
    observability = build_local_observability_session(target.data_root)
    try:
        service = LocalRead15Service(configuration, _application_reader(target), observability, assets)
        server = LocalRead15Server(service)
    except Exception:
        observability.shutdown()
        raise
    observability.startup(
        app_version="v2.0", config_profile_id="local.read15", runtime_mode="LOCAL_BROWSER"
    )
    return LocalRead15Composition(server, observability)
