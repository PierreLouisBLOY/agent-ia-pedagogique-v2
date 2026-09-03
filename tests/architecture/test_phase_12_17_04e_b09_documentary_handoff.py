from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_INDEX = ROOT / "docs" / "legacy-review" / "README.md"
LEGACY_TRACE = ROOT / "docs" / "legacy-review" / "phase_7_sqlite_runtime_reuse.md"
HANDOFF = (
    ROOT
    / "docs"
    / "development"
    / "phase_12_17_04e_b09_legacy_review_api_handoff"
    / "API_HANDOFF.json"
)


def _handoff() -> dict[str, object]:
    value = json.loads(HANDOFF.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_legacy_review_is_explicitly_retrospective_and_linked() -> None:
    index = LEGACY_INDEX.read_text(encoding="utf-8")
    trace = LEGACY_TRACE.read_text(encoding="utf-8")

    assert "phase_7_sqlite_runtime_reuse.md" in index
    assert "RETROSPECTIVE_DOCUMENTATION = TRUE" in trace
    assert "RETROACTIVE_APPROVAL = FALSE" in trace
    assert "PAST_APPROVAL_EVIDENCE = NOT_ASSERTED" in trace
    assert "PHASE_12_15_C0_SQLITE_RUNTIME_INTEGRATION_BASELINE.md" in trace
    assert "PHASE_12_15_LIVRABLE_COMPLET_CANONIQUE_FINAL.md" in trace
    assert "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102" in trace


def test_application_owner_handoff_is_ordered_and_not_implemented() -> None:
    handoff = _handoff()
    owners = handoff["application_owners"]
    assert isinstance(owners, list)

    assert handoff["application_delivery_order"] == ["CAP-R02", "CAP-A01", "CAP-A02"]
    assert [owner["capability_id"] for owner in owners] == ["CAP-R02", "CAP-A01", "CAP-A02"]
    assert all(owner["implementation_status"] == "NOT_IMPLEMENTED" for owner in owners)


def test_read15_handoff_is_resource_only_and_cannot_authorize_sql() -> None:
    handoff = _handoff()
    http = handoff["http_handoff"]
    assert isinstance(http, dict)

    assert handoff["implementation_started"] is False
    assert http["scope"] == "RESOURCE_READ_15_ONLY"
    assert http["method"] == "GET"
    assert http["route"] == "/api/v2/resources/{resource_ref}"
    assert http["path_parameters"] == ["resource_ref"]
    assert http["query_parameters"] == []
    assert http["endpoint_implemented"] is False
    assert http["authority"] == "APPLICATION"
    assert http["direct_sql_authorized"] is False
    assert http["repository_import_authorized"] is False
    assert http["other_endpoints_authorized"] == []


def test_read15_deprecations_and_local_browser_constraints_are_closed() -> None:
    handoff = _handoff()
    deprecation = handoff["read15_deprecation"]
    local = handoff["local_browser_downstream"]
    assert isinstance(deprecation, dict)
    assert isinstance(local, dict)

    assert deprecation["version_ref"] == "DEPRECATED_FOR_ACTIVE_READ15"
    assert deprecation["include"] == "DEPRECATED_FOR_ACTIVE_READ15"
    assert local == {
        "V2_EXECUTION_MODE": "LOCAL_BROWSER",
        "BACKEND_BIND_DEFAULT": "LOOPBACK_ONLY",
        "GOOGLE_DRIVE_RUNTIME_DEPENDENCY": "NONE",
        "WINDOWS_EXE_REQUIRED_FOR_V2": False,
    }
