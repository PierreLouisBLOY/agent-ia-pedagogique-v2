from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime

import pytest

from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.errors import (
    BusinessError,
    BusinessErrorCategory,
    BusinessErrorCode,
    BusinessErrorDomain,
    BusinessErrorSeverity,
)
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import BusinessDate, Instant


def _business_error() -> BusinessError:
    return BusinessError(
        code=BusinessErrorCode("COURSE_REQUIRED"),
        domain=BusinessErrorDomain.COURSE,
        category=BusinessErrorCategory.REQUIRED,
        severity=BusinessErrorSeverity.ERROR,
        blocking=True,
        retryable=True,
        message_key="course.required",
        details={"field": "course", "path": ["input", "course"]},
    )


@pytest.mark.parametrize(
    ("factory", "args"),
    [
        (TypedEntityId, (" ", "123")),
        (TypedEntityId, ("course", "")),
        (VersionRef, ("",)),
        (CorrelationId, ("\t",)),
        (BusinessErrorCode, ("",)),
    ],
)
def test_identifier_strings_must_be_non_empty(
    factory: type[object], args: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        factory(*args)


def test_identity_and_version_references_use_composition() -> None:
    entity_id = TypedEntityId(entity_type="course", value="Course-A")
    entity_ref = TypedEntityRef(entity_id)
    version_ref = VersionRef("v1")

    exact_ref = ObjectVersionRef(object_ref=entity_ref, version_ref=version_ref)

    assert exact_ref.object_ref.entity_id.value == "Course-A"
    assert exact_ref.version_ref.value == "v1"


def test_reference_composition_rejects_arbitrary_objects() -> None:
    entity_ref = TypedEntityRef(TypedEntityId("course", "course-1"))

    with pytest.raises(TypeError):
        TypedEntityRef(RuntimeError("raw"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ObjectVersionRef(RuntimeError("raw"), VersionRef("v1"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ObjectVersionRef(entity_ref, RuntimeError("raw"))  # type: ignore[arg-type]


def test_value_objects_are_immutable() -> None:
    correlation_id = CorrelationId("corr-1")

    with pytest.raises(FrozenInstanceError):
        correlation_id.value = "corr-2"  # type: ignore[misc]


def test_business_error_enums_have_exact_canonical_values() -> None:
    assert [item.value for item in BusinessErrorDomain] == [
        "CORE",
        "KNOWLEDGE",
        "REF",
        "DOC",
        "RESOURCE",
        "PROD",
        "PED",
        "COURSE",
        "ANALYSIS",
        "CONTEXT",
        "TASK",
        "VALIDATION",
        "QUALITY",
        "LIFECYCLE",
        "AUDIT",
    ]
    assert [item.value for item in BusinessErrorCategory] == [
        "NOT_FOUND",
        "REQUIRED",
        "INVALID",
        "CONFLICT",
        "AMBIGUOUS",
        "STATE",
        "DEPENDENCY",
        "ALIGNMENT",
        "VISIBILITY",
        "PROVENANCE",
        "VERSION",
        "POLICY",
        "INDETERMINATE",
        "INVARIANT",
        "IMMUTABILITY",
    ]
    assert [item.value for item in BusinessErrorSeverity] == [
        "INFO",
        "WARNING",
        "ERROR",
        "FATAL",
    ]


def test_business_error_details_are_safe_and_deeply_immutable() -> None:
    error = _business_error()

    assert error.details is not None
    with pytest.raises(TypeError):
        error.details["field"] = "other"  # type: ignore[index]
    assert error.details["path"] == ("input", "course")

    with pytest.raises(TypeError):
        BusinessError(
            code=BusinessErrorCode("UNSAFE"),
            domain=BusinessErrorDomain.CORE,
            category=BusinessErrorCategory.INVALID,
            severity=BusinessErrorSeverity.ERROR,
            blocking=True,
            retryable=False,
            message_key="unsafe",
            details={"exception": ValueError("raw")},
        )


@pytest.mark.parametrize(
    "details",
    [
        {"password": "x"},
        {"auth_token": "x"},
        {"access_token": "x"},
        {"refresh-token": "x"},
        {"BearerToken": "x"},
        {"api_key": "x"},
        {"sql": "SELECT * FROM private_table"},
        {"sql_query": "SELECT * FROM private_table"},
        {"raw-sql-query": "SELECT * FROM private_table"},
        {"stack_trace": "private stack"},
        {"provider_payload": {"raw": "payload"}},
        {"local_path": "C:/private/data"},
    ],
)
def test_business_error_details_reject_sensitive_keys(
    details: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        BusinessError(
            code=BusinessErrorCode("UNSAFE"),
            domain=BusinessErrorDomain.CORE,
            category=BusinessErrorCategory.INVALID,
            severity=BusinessErrorSeverity.ERROR,
            blocking=True,
            retryable=False,
            message_key="unsafe",
            details=details,
        )


@pytest.mark.parametrize(
    "details",
    [
        {"token_count": 42},
        {"input_tokens": 10, "output_tokens": 20},
        {"search_query": "notion TVA"},
        {"query_kind": "semantic_search"},
    ],
)
def test_business_error_details_accept_provider_neutral_metadata(
    details: dict[str, object],
) -> None:
    error = BusinessError(
        code=BusinessErrorCode("REMEDIATION_METADATA"),
        domain=BusinessErrorDomain.CORE,
        category=BusinessErrorCategory.INDETERMINATE,
        severity=BusinessErrorSeverity.INFO,
        blocking=False,
        retryable=True,
        message_key="remediation.metadata",
        details=details,
    )

    assert error.details == details
    assert error.details is not None
    with pytest.raises(TypeError):
        error.details["new_key"] = "blocked"  # type: ignore[index]


def test_provider_neutral_metadata_is_deeply_frozen() -> None:
    error = BusinessError(
        code=BusinessErrorCode("REMEDIATION_METADATA"),
        domain=BusinessErrorDomain.CORE,
        category=BusinessErrorCategory.INDETERMINATE,
        severity=BusinessErrorSeverity.INFO,
        blocking=False,
        retryable=True,
        message_key="remediation.metadata",
        details={
            "usage": {"input_tokens": 10, "output_tokens": 20},
            "queries": [{"search_query": "notion TVA"}],
        },
    )

    assert error.details is not None
    usage = error.details["usage"]
    queries = error.details["queries"]
    assert isinstance(usage, Mapping)
    assert isinstance(queries, tuple)
    assert isinstance(queries[0], Mapping)
    with pytest.raises(TypeError):
        usage["input_tokens"] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        queries[0]["search_query"] = "other"  # type: ignore[index]


def test_business_error_details_preserve_safe_references() -> None:
    entity_ref = TypedEntityRef(TypedEntityId("course", "course-1"))
    object_version_ref = ObjectVersionRef(entity_ref, VersionRef("v1"))
    error = BusinessError(
        code=BusinessErrorCode("VERSION_CONFLICT"),
        domain=BusinessErrorDomain.CORE,
        category=BusinessErrorCategory.VERSION,
        severity=BusinessErrorSeverity.ERROR,
        blocking=True,
        retryable=True,
        message_key="version.conflict",
        details={
            "subject": entity_ref,
            "expected": {"object_version": object_version_ref},
        },
    )

    assert error.details is not None
    assert error.details["subject"] is entity_ref
    expected = error.details["expected"]
    assert isinstance(expected, Mapping)
    assert expected["object_version"] is object_version_ref


def test_time_primitives_accept_supplied_values_without_reading_a_clock() -> None:
    instant_value = datetime(2026, 8, 24, 12, 30, tzinfo=UTC)
    business_date = date(2026, 8, 24)

    assert Instant(instant_value).value is instant_value
    assert BusinessDate(business_date).value is business_date

    with pytest.raises(ValueError):
        Instant(datetime(2026, 8, 24, 12, 30))
    with pytest.raises(TypeError):
        BusinessDate(instant_value)
