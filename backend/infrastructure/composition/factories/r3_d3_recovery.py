"""Private, explicitly injected recovery. No discovery, publication or live binding."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from uuid import uuid4

from backend.adapters.inbound.api.r3_review_modify import R3Endpoint
from backend.adapters.inbound.application.r3_review_modify import R3ApplicationInbound
from backend.adapters.outbound.generation.openai.locator_materialization import calculation_locators
from backend.adapters.outbound.persistence.conversation_memory import ConversationMemoryStore
from backend.adapters.outbound.system.r3_job import UnapprovedR3Job
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    as_plain,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    EditorialCorrectionPlan,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialAuthorizationEvidence,
    EditorialValidationScope,
    build_editorial_scope,
)
from backend.modules.work_orchestration.application.services.r3_review_modify import (
    R3ReviewModifyService,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationState
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.r3_restoration import R3RestorationSnapshot
from backend.modules.work_orchestration.ports.outbound.r3_job import R3JobPort

_SOURCES = frozenset(
    {
        "state",
        "parent_view",
        "child_view",
        "parent_bundle",
        "child_bundle",
        "review",
        "receipt",
        "plan",
        "owner_decision",
    }
)


def _decode(raw: bytes) -> dict[str, object]:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > 256 * 1024
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        raise ValueError("RESTORATION_SOURCE_INCOMPLETE")

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
            result[key] = value
        return result

    def nonfinite(_: str) -> object:
        raise ValueError("RESTORATION_SOURCE_INCOMPLETE")

    return object_data(
        json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    )


def verify_restoration_sources(
    sources: Mapping[str, bytes], *, expected_hashes: Mapping[str, str]
) -> dict[str, bytes]:
    """Expected hashes come from the independently approved grant, not candidate JSON."""
    if set(sources) != _SOURCES or set(expected_hashes) != _SOURCES:
        raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
    checked = dict(sources)
    for name, raw in checked.items():
        if (
            type(raw) is not bytes
            or not raw
            or len(raw) > 256 * 1024
            or type(expected_hashes[name]) is not str
            or hashlib.sha256(raw).hexdigest() != expected_hashes[name]
        ):
            raise ValueError("RESTORATION_SOURCE_IDENTITY")
    return checked


class R3RestorationAuthority:
    """One fresh process lease, never a deserialized seal or editorial execution grant."""

    def __init__(
        self,
        *,
        grant_raw: bytes,
        expected_grant_sha256: str,
        baseline_commit: str,
        sources: Mapping[str, bytes],
        clock: Callable[[], datetime],
    ) -> None:
        if (
            type(grant_raw) is not bytes
            or hashlib.sha256(grant_raw).hexdigest() != expected_grant_sha256
            or re.fullmatch(r"[0-9a-f]{40}", baseline_commit) is None
        ):
            raise ValueError("RESTORATION_NOT_AUTHORIZED")
        grant = object_data(
            _decode(grant_raw),
            {
                "contract",
                "purpose",
                "baseline_commit",
                "source_hashes",
                "conversation_id",
                "production_ref",
                "parent_version_ref",
                "child_version_ref",
                "child_bundle_sha256",
                "issued_at",
                "expires_at",
                "max_validations",
            },
        )
        issued, expiry = (
            datetime.fromisoformat(str(grant["issued_at"])),
            datetime.fromisoformat(str(grant["expires_at"])),
        )
        now = clock()
        if (
            grant["contract"] != "R3-RESTORE-EXISTING-1.0"
            or grant["purpose"] != "RESTORE_EXISTING"
            or grant["baseline_commit"] != baseline_commit
            or issued.tzinfo is None
            or expiry.tzinfo is None
            or now.tzinfo is None
            or not issued <= now < expiry
            or not 0 < (expiry - issued).total_seconds() <= 7200
            or type(grant["max_validations"]) is not int
            or not 1 <= grant["max_validations"] <= 8
        ):
            raise ValueError("RESTORATION_NOT_AUTHORIZED")
        hashes = object_data(grant["source_hashes"])
        if any(type(v) is not str for v in hashes.values()):
            raise ValueError("RESTORATION_SOURCE_IDENTITY")
        self.sources = verify_restoration_sources(
            sources, expected_hashes={k: str(v) for k, v in hashes.items()}
        )
        self._grant, self._grant_raw, self._grant_hash = grant, grant_raw, expected_grant_sha256
        self._clock, self._issued, self._expires = clock, issued, expiry
        self._open, self._count = True, 0
        self._lock = RLock()
        self._receipt = object()
        self._evidence: EditorialAuthorizationEvidence | None = None
        self._scope: EditorialValidationScope | None = None

    def ensure(self) -> None:
        if (
            not self._open
            or not self._issued <= self._clock() < self._expires
            or hashlib.sha256(self._grant_raw).hexdigest() != self._grant_hash
        ):
            raise ValueError("RESTORATION_NOT_AUTHORIZED")
        hashes = object_data(self._grant["source_hashes"])
        verify_restoration_sources(
            self.sources, expected_hashes={k: str(v) for k, v in hashes.items()}
        )

    def authenticate(self, evidence: EditorialAuthorizationEvidence) -> bool:
        try:
            self.ensure()
            return (
                evidence is self._evidence
                and evidence.receipt is self._receipt
                and evidence.conversation_id == self._grant["conversation_id"]
                and evidence.plan.raw == self.sources["plan"]
                and evidence.review_raw == self.sources["review"]
                and evidence.owner_decision_sha256
                == hashlib.sha256(self.sources["owner_decision"]).hexdigest()
            )
        except Exception:
            return False

    def authorize_validation(self, scope: EditorialValidationScope) -> bool:
        with self._lock:
            if (
                scope is not self._scope
                or not self.authenticate(scope.evidence)
                or self._count >= int(str(self._grant["max_validations"]))
            ):
                return False
            self._count += 1
            return True

    def snapshot(self) -> R3RestorationSnapshot:
        with self._lock:
            self.ensure()
            if self._evidence is not None:
                raise ValueError("RESTORATION_ALREADY_CONSUMED")
            raw = self.sources
            state_data = object_data(_decode(raw["state"]), {"conversation_id", "revision", "view"})
            if type(state_data["revision"]) is not int:
                raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
            state = ConversationState(
                str(state_data["conversation_id"]),
                state_data["revision"],
                object_data(state_data["view"]),
            )
            if datetime.fromisoformat(str(state.view.get("expiration"))) != self._expires:
                raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
            bundles = (
                AssessmentBundle(_decode(raw["parent_bundle"])),
                AssessmentBundle(_decode(raw["child_bundle"])),
            )
            parent, child = bundles
            if (
                state.conversation_id,
                child.production_ref,
                parent.version_ref,
                child.version_ref,
                child.sha256,
            ) != tuple(
                self._grant[k]
                for k in (
                    "conversation_id",
                    "production_ref",
                    "parent_version_ref",
                    "child_version_ref",
                    "child_bundle_sha256",
                )
            ):
                raise ValueError("RESTORATION_SOURCE_IDENTITY")
            views = tuple(
                ProductionReadView(
                    b.production_ref, b.version_ref, state.conversation_id, _decode(raw[n])
                )
                for b, n in zip(bundles, ("parent_view", "child_view"), strict=True)
            )
            plan = EditorialCorrectionPlan(raw["plan"])
            evidence = EditorialAuthorizationEvidence(
                plan,
                state.conversation_id,
                str(plan.data["implementation_baseline_commit"]),
                str(plan.data["contract_document_sha256"]),
                hashlib.sha256(raw["owner_decision"]).hexdigest(),
                raw["review"],
                self._receipt,
            )
            self._evidence = evidence
            try:
                receipt = _decode(raw["receipt"])
                scope = build_editorial_scope(
                    evidence,
                    parent,
                    child,
                    command_id=str(receipt["command_id"]),
                    operation_ref=str(receipt["operation_ref"]),
                    authenticate=self.authenticate,
                    calculate_locators=calculation_locators,
                )
                result = R3RestorationSnapshot(
                    state, (views[0], views[1]), bundles, evidence.review, receipt, scope
                )
                self._scope = scope
                return result
            except Exception:
                self.close()
                raise

    def close(self) -> None:
        self._open = False
        self._scope = self._evidence = None


@dataclass(frozen=True, slots=True)
class RestoredR3Session:
    authority: R3RestorationAuthority
    store: ConversationMemoryStore
    service: R3ReviewModifyService
    inbound: R3ApplicationInbound
    endpoint: R3Endpoint

    def capture_and_close(self, capture: Callable[[Mapping[str, object]], None]) -> None:
        """Export failure propagates as an incident; finally still revokes the lease."""
        try:
            self.authority.ensure()
            snapshot = self.authority._scope
            if snapshot is None:
                raise ValueError("RESTORATION_NOT_AUTHORIZED")
            child = snapshot.child
            capture(self.inbound.assessment(child.production_ref, child.version_ref))
        finally:
            self.close()

    def close(self) -> None:
        try:
            self.service.close()
        finally:
            self.authority.close()
            self.store.r3_clear()


def build_restored_r3(
    *,
    sources: Mapping[str, bytes],
    grant_raw: bytes,
    expected_grant_sha256: str,
    baseline_commit: str,
    clock: Callable[[], datetime],
    jobs: R3JobPort | None = None,
) -> RestoredR3Session:
    authority = R3RestorationAuthority(
        grant_raw=grant_raw,
        expected_grant_sha256=expected_grant_sha256,
        baseline_commit=baseline_commit,
        sources=sources,
        clock=clock,
    )
    try:
        snapshot = authority.snapshot()
        store = ConversationMemoryStore.from_r3_restoration(snapshot)

        def ensure() -> object:
            authority.ensure()
            state = store.read(snapshot.state.conversation_id)
            if state is None:
                raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
            return as_plain(state.view)

        service = R3ReviewModifyService(
            conversation_id=snapshot.state.conversation_id,
            store=store,
            jobs=jobs if jobs is not None else UnapprovedR3Job(),
            ensure_session=ensure,
            clock=clock,
            new_id=lambda prefix: prefix + ":" + uuid4().hex,
            restored_editorial_scope=snapshot.scope,
            restored_authenticate=authority.authorize_validation,
        )
        inbound = R3ApplicationInbound(service)
        return RestoredR3Session(authority, store, service, inbound, R3Endpoint(inbound))
    except Exception:
        authority.close()
        raise
