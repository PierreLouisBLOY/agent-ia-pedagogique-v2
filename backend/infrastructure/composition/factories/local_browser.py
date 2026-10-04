"""Explicit local READ-15 composition, with no provisioning, migrations or credentials."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe

from backend.adapters.inbound.api.read15 import Read15Endpoint, Read15ValidationRejected
from backend.adapters.inbound.api.routes import ASSET_NAMES
from backend.adapters.inbound.api.saved_production import SavedProductionEndpoint
from backend.adapters.inbound.api.search import SearchEndpoint, SearchValidationRejected
from backend.adapters.inbound.api.server import LocalRead15Server, LocalRead15Service
from backend.adapters.inbound.application.local_search import LocalSearchUseCaseInbound
from backend.adapters.inbound.application.lot2_saved_production import Lot2SavedProductionInbound
from backend.adapters.inbound.application.resource_library import ResourceLibraryUseCaseInbound
from backend.adapters.inbound.application.saved_production import SavedProductionInbound
from backend.adapters.outbound.export.diffusion_word import diffusion_document
from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter
from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.sqlite import SQLiteResourceStoreAdapter
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
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
from backend.infrastructure.composition.factories.conversation import (
    ConversationComposition,
    build_conversation,
)
from backend.infrastructure.composition.factories.p0_creation import build_p0_creation
from backend.infrastructure.composition.factories.r3_review_modify import R3Composition, build_r3
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from backend.infrastructure.filesystem import (
    assert_local_data_root,
    capture_secure_path,
    hash_file_nofollow,
    read_file_nofollow,
)
from backend.modules.materialization_export.application.commands.export_saved import (
    ExportSavedCommand,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.application.queries.search_local import SearchLocalQuery
from backend.modules.resource_library.domain.errors import InvalidResourceRefError
from backend.modules.resource_library.domain.value_objects import ResourceRef
from backend.modules.resource_library.domain.value_objects.search_text import (
    InvalidSearchTextError,
    SearchText,
)
from backend.modules.work_orchestration.application.queries.read_production import (
    ReadProductionQuery,
)
from backend.modules.work_orchestration.application.services.saved_production import (
    SavedProductionService,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_CONTRACT,
    SavedProduction,
)
from backend.modules.work_orchestration.ports.outbound.generation_job import GenerationJobPort
from backend.modules.work_orchestration.ports.outbound.r3_job import R3JobPort
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
    conversation: ConversationComposition | None = None
    r3: R3Composition | None = None
    saved: SavedProductionInbound | None = None

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
        try:
            if self.r3 is not None:
                self.r3.service.close()
            if self.conversation is not None:
                self.conversation.service.close()
        finally:
            duration = self.observability.shutdown()
        return duration


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


def _application_searcher(target: Read15RuntimeTarget) -> SearchEndpoint:
    def invoke(text: str, limit: int, correlation: str) -> UseCaseResult[object, object]:
        # Validate the Application-owned intention before any target metadata access.
        try:
            typed = SearchLocalRequest(SearchText(text), limit)
        except InvalidSearchTextError:
            raise SearchValidationRejected("SEARCH_REQUEST_REJECTED") from None
        target.validate()
        connection = connect_sqlite(
            target.runtime_path, readonly=True, allowed_root=target.data_root,
        )
        try:
            search = SQLiteLocalSearchAdapter(connection)
            resources = GetResourceQuery(SQLiteResourceStoreAdapter(connection))
            inbound = LocalSearchUseCaseInbound(SearchLocalQuery(search, resources))
            correlation_id = CorrelationId(correlation)
            request = UseCaseRequest(
                meta=ContractMeta(
                    schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                    run_id="local-search", step_id="local-search-read", parent_step_id=None,
                    correlation_id=correlation_id, created_at=Instant(datetime.now(UTC)),
                    actor=ActorRef(ActorKind.APPLICATION, "local-search"),
                    status=InvocationStatus.PLANNED,
                ),
                use_case_id="application.search_local_passages",
                payload={"q": typed.text.value, "limit": typed.limit},
                actor_context=UseCaseContext(correlation_id),
            )
            with search.read_snapshot():
                return inbound.invoke(request=request)
        finally:
            connection.close()
    return SearchEndpoint(invoke)


def build_local_read15(
    configuration: LocalBrowserHttpConfiguration, target: Read15RuntimeTarget,
    *, enable_conversation: bool = False, generation_jobs: GenerationJobPort | None = None,
    enable_review_modify: bool = False, r3_jobs: R3JobPort | None = None,
    saved_root: Path | None = None, create_saved: bool = False,
    p0_generation: P0GenerationPort | None = None,
    observability_root: Path | None = None,
) -> LocalRead15Composition:
    """Receive an explicit existing target; never read ambient environment settings."""
    if generation_jobs is not None and not enable_conversation:
        raise ValueError("R2_NOT_ENABLED")
    if (enable_review_modify and not enable_conversation) or (r3_jobs is not None and not enable_review_modify):
        raise ValueError("R3_NOT_ENABLED")
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
    observability = build_local_observability_session(observability_root or target.data_root)
    conversation = build_conversation(jobs=generation_jobs) if enable_conversation else None
    r3 = build_r3(conversation, r3_jobs) if enable_review_modify and conversation else None
    p0, p0_endpoint = build_p0_creation(target, token_urlsafe(32), p0_generation)
    saved = None
    if saved_root is not None:
        def source(production_ref: str, version_ref: str) -> SavedProduction:
            if version_ref in p0.records:
                return p0.saved_source(production_ref, version_ref)
            if conversation is None:
                raise ValueError("R4_SOURCE_NOT_AVAILABLE")
            view = conversation.store.read_version(conversation_id=str(conversation.service.snapshot()["conversation_id"]),
                production_ref=production_ref, version_ref=version_ref)
            if view is None:
                raise ValueError("R4_SOURCE_NOT_AVAILABLE")
            snapshot = conversation.store.r3_snapshot(production_ref, version_ref)
            return SavedProduction({"contract_id": SAVED_CONTRACT, "view": as_plain(view.data),
                "bundle": snapshot["bundle"], "reviews": snapshot["reviews"],
                "validations": snapshot["validations"], "origin": "LOCAL_APPLICATION",
                "provenance": {}, "reservations": []})
        saved = build_saved_application(saved_root, create=create_saved, source=source)
    def harvest() -> None:
        if conversation:
            conversation.service.poll()
        if r3:
            r3.service.poll()
    try:
        service = LocalRead15Service(
            configuration, _application_reader(target), observability, assets,
            search_endpoint=_application_searcher(target),
            conversation_endpoint=conversation.endpoint if conversation else None,
            production_endpoint=conversation.production if conversation else None,
            harvest=harvest if conversation else None,
            r3_endpoint=r3.endpoint if r3 else None,
            saved_endpoint=SavedProductionEndpoint(saved.execute, nonce=token_urlsafe(32)) if saved else None,
            p0_endpoint=p0_endpoint,
        )
        server = LocalRead15Server(service)
    except Exception:
        if r3 is not None:
            r3.service.close()
        if conversation is not None:
            conversation.service.close()
        observability.shutdown()
        raise
    observability.startup(
        app_version="v2.0", config_profile_id="local.read15", runtime_mode="LOCAL_BROWSER"
    )
    return LocalRead15Composition(server, observability, conversation=conversation, r3=r3, saved=saved)


def build_saved_application(root: Path, *, create: bool = False,
        source: Callable[[str, str], SavedProduction] | None = None) -> SavedProductionInbound:
    store = LocalSavedProductionStore(root, create=create)
    return Lot2SavedProductionInbound(SavedProductionService(store), ReadProductionQuery(store),
                                  ExportSavedCommand(R6ReadableWordWriter(profile="diffusion-v5"), presentation=diffusion_document), source=source)


def build_local_saved(configuration: LocalBrowserHttpConfiguration, root: Path, *,
                      create: bool = False,
                      source: Callable[[str, str], SavedProduction] | None = None) -> LocalRead15Composition:
    """Existing local app in R4-only mode: no library target, SQLite or generation job."""
    saved = build_saved_application(root, create=create, source=source)
    assets_root = _ROOT / "frontend"
    assets = {name: read_file_nofollow(assets_root / name, allowed_root=assets_root,
                                      maximum_bytes=128 * 1024) for name in sorted(ASSET_NAMES)}
    observability = build_local_observability_session(root)
    def unavailable(reference: str, correlation: str) -> UseCaseResult[object, object]:
        raise Read15ValidationRejected("READ15_REQUEST_REJECTED")
    try:
        service = LocalRead15Service(configuration, Read15Endpoint(unavailable), observability, assets,
            saved_endpoint=SavedProductionEndpoint(saved.execute, nonce=token_urlsafe(32)))
        server = LocalRead15Server(service)
    except Exception:
        observability.shutdown()
        raise
    observability.startup(app_version="v2.0", config_profile_id="local.r4", runtime_mode="LOCAL_BROWSER")
    return LocalRead15Composition(server, observability, saved=saved)
