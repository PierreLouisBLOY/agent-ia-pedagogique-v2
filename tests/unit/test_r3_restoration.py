"""Exact, independent source authentication and fresh-store construction."""

import hashlib
import json
from dataclasses import replace
from datetime import timedelta

import pytest

from backend.adapters.outbound.persistence.conversation_memory import ConversationMemoryStore
from backend.infrastructure.composition.factories.r3_d3_recovery import R3RestorationAuthority
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded
from tests.support.r3_d3_fixtures import BASELINE, NOW, synthetic_restoration


def test_two_exact_versions_without_publication_or_fabricated_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = synthetic_restoration()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("RESTORATION_MUST_NOT_PUBLISH")

    for method in ("publish", "r3_reserve", "r3_complete"):
        monkeypatch.setattr(ConversationMemoryStore, method, forbidden)
    session = fixture.build()
    assert len(session.store._versions) == len(session.store._r3_bundles) == 2
    assert not session.store._r3_commands and session.store._r3_lease is None
    assert len(session.store._r3_consumed_editorial_plans) == 1
    assert (
        session.store._versions[(fixture.child.production_ref, fixture.child.version_ref)].data
        == fixture.views[1].data
    )
    session.close()


@pytest.mark.parametrize(
    "name",
    [
        "state",
        "parent_view",
        "child_view",
        "parent_bundle",
        "child_bundle",
        "review",
        "receipt",
        "plan",
        "owner_decision",
    ],
)
@pytest.mark.parametrize("kind", ["missing", "mutation"])
def test_every_source_is_exact(name: str, kind: str) -> None:
    fixture = synthetic_restoration()
    if kind == "missing":
        del fixture.sources[name]
    else:
        fixture.sources[name] += b" "
    with pytest.raises(ValueError):
        fixture.build()


@pytest.mark.parametrize("name", ["parent_view", "child_view", "receipt", "plan", "review"])
def test_rehashed_inconsistent_source_is_not_authority(name: str) -> None:
    fixture = synthetic_restoration()
    value = json.loads(fixture.sources[name])
    value[
        "version_ref"
        if name in {"parent_view", "child_view", "review", "receipt"}
        else "parent_version_ref"
    ] = "ver:" + "f" * 32
    fixture.sources[name] = encoded(value)
    fixture.grant["source_hashes"][name] = hashlib.sha256(fixture.sources[name]).hexdigest()
    with pytest.raises(ValueError):
        fixture.build()


@pytest.mark.parametrize(
    "change", ["baseline", "expiry", "too_long", "limit_bool", "extra", "target"]
)
def test_grant_is_closed_and_bounded(change: str) -> None:
    fixture = synthetic_restoration()
    if change == "baseline":
        fixture.grant["baseline_commit"] = "f" * 40
    elif change == "expiry":
        fixture.grant["expires_at"] = NOW.isoformat()
    elif change == "too_long":
        fixture.grant["expires_at"] = (NOW + timedelta(hours=3)).isoformat()
    elif change == "limit_bool":
        fixture.grant["max_validations"] = True
    elif change == "extra":
        fixture.grant["extra"] = True
    else:
        fixture.grant["child_bundle_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        fixture.build()


def test_copied_scope_evidence_expiry_revocation_and_one_snapshot() -> None:
    fixture = synthetic_restoration()
    raw = encoded(fixture.grant)
    time = [NOW]
    authority = R3RestorationAuthority(
        grant_raw=raw,
        expected_grant_sha256=hashlib.sha256(raw).hexdigest(),
        baseline_commit=BASELINE,
        sources=fixture.sources,
        clock=lambda: time[0],
    )
    snapshot = authority.snapshot()
    assert authority.authenticate(snapshot.scope.evidence)
    assert not authority.authenticate(replace(snapshot.scope.evidence))
    assert not authority.authorize_validation(replace(snapshot.scope))
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        authority.snapshot()
    time[0] += timedelta(hours=2)
    assert not authority.authenticate(snapshot.scope.evidence)
    authority.close()
    assert not authority.authenticate(snapshot.scope.evidence)
