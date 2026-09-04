from __future__ import annotations

import sqlite3
from typing import cast

import pytest

from backend.adapters.inbound.application import ResourceLibraryUseCaseInbound
from backend.adapters.outbound.resource_library import SQLiteResourceStoreAdapter
from backend.modules.resource_library.application.dto.input import GetResourceRequest
from backend.modules.resource_library.application.queries import GetResourceQuery
from backend.modules.resource_library.domain.errors import InvalidResourceRefError
from backend.modules.resource_library.domain.value_objects import (
    RESOURCE_REF_MAX_LENGTH,
    RESOURCE_REF_MIN_LENGTH,
    RESOURCE_REF_REGEX,
    ResourceAvailabilityStatus,
    ResourceCanonicalityStatus,
    ResourceRef,
    ResourceSemanticState,
)
from backend.modules.resource_library.ports.outbound import ResourceRecord
from tests.support.use_case_routing_fakes import make_request


@pytest.mark.parametrize(
    "value",
    (
        "A",
        "a1",
        "A._:-z9",
        "resource:1",
        "resource-assessment:" + "a" * 24,
        "resource:runtime:" + "a" * 32,
        "A" + "a" * 127,
    ),
)
def test_resource_ref_accepts_the_canonical_ascii_contract(value: str) -> None:
    assert ResourceRef(value).value == value


@pytest.mark.parametrize(
    "value",
    (
        "",
        "A" * 129,
        "-abc",
        "_abc",
        ".abc",
        ":abc",
        "a b",
        "a/b",
        "a?b",
        "a#b",
        "a\tb",
        "a\nb",
        "référence",
    ),
)
def test_resource_ref_rejects_values_outside_the_canonical_contract(
    value: str,
) -> None:
    with pytest.raises(
        InvalidResourceRefError,
        match="resource_ref does not satisfy the canonical contract",
    ):
        ResourceRef(value)


def test_resource_ref_contract_exports_the_approved_identity() -> None:
    assert RESOURCE_REF_REGEX == r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
    assert RESOURCE_REF_MIN_LENGTH == 1
    assert RESOURCE_REF_MAX_LENGTH == 128


def test_resource_ref_rejects_non_strings_without_disclosing_the_value() -> None:
    with pytest.raises(TypeError, match="resource_ref must be a string") as raised:
        ResourceRef(cast(str, object()))
    assert "object at" not in str(raised.value)


def test_application_input_requires_the_domain_value_object() -> None:
    with pytest.raises(TypeError, match="resource_ref must be a ResourceRef"):
        GetResourceRequest(cast(ResourceRef, "resource:1"))


class NeverCalledResourceStore:
    def __init__(self) -> None:
        self.call_count = 0

    def load_resource(self, resource_ref: ResourceRef) -> ResourceRecord | None:
        self.call_count += 1
        return None


def test_invalid_inbound_reference_fails_before_application_lookup() -> None:
    store = NeverCalledResourceStore()
    inbound = ResourceLibraryUseCaseInbound(GetResourceQuery(store))

    with pytest.raises(InvalidResourceRefError):
        inbound.invoke(request=make_request(payload={"resource_ref": "a/b"})[0])

    assert store.call_count == 0


@pytest.mark.parametrize("deprecated_field", ("version_ref", "include"))
def test_read15_rejects_deprecated_fields_before_application_lookup(
    deprecated_field: str,
) -> None:
    store = NeverCalledResourceStore()
    inbound = ResourceLibraryUseCaseInbound(GetResourceQuery(store))
    payload: dict[str, object] = {
        "resource_ref": "resource:1",
        deprecated_field: "deprecated",
    }

    with pytest.raises(
        ValueError, match="getResource payload contains unsupported fields"
    ):
        inbound.invoke(request=make_request(payload=payload)[0])

    assert store.call_count == 0


def test_sqlite_adapter_consumes_a_validated_ref_without_mutating_it() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE resource(
               id TEXT PRIMARY KEY,
               resource_type TEXT NOT NULL,
               canonical_title TEXT NOT NULL,
               identity_status TEXT NOT NULL
           )"""
    )
    connection.execute(
        "INSERT INTO resource VALUES (?, ?, ?, ?)",
        ("resource:1", "COURSE", "Management", "ACTIVE"),
    )
    adapter = SQLiteResourceStoreAdapter(connection)

    record = adapter.load_resource(ResourceRef("resource:1"))

    assert record is not None
    assert record.resource_ref == ResourceRef("resource:1")
    assert record.semantic_state == ResourceSemanticState(
        ResourceAvailabilityStatus.ACTIVE,
        ResourceCanonicalityStatus.UNKNOWN,
    )
    with pytest.raises(TypeError, match="resource_ref must be a ResourceRef"):
        adapter.load_resource(cast(ResourceRef, "resource:1"))
    adapter.close()
