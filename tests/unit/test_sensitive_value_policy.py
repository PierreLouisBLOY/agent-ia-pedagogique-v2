from __future__ import annotations

import pytest

from backend.agent_runtime.security import (
    SensitiveValueClass,
    SensitiveValuePolicy,
    SensitiveValueRejected,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping
from tests.support.synthetic_secret_fixtures import (
    fake_api_credential,
    fake_bearer_token,
    fake_connection_secret,
    fake_private_key,
    fake_private_path,
)


@pytest.mark.parametrize(
    ("value_factory", "classification"),
    (
        (fake_api_credential, SensitiveValueClass.CREDENTIAL_LIKE),
        (fake_bearer_token, SensitiveValueClass.AUTH_TOKEN_LIKE),
        (fake_private_key, SensitiveValueClass.PRIVATE_KEY_LIKE),
        (fake_connection_secret, SensitiveValueClass.CONNECTION_SECRET_LIKE),
        (fake_private_path, SensitiveValueClass.PRIVATE_PATH_LIKE),
    ),
)
def test_sensitive_value_policy_classifies_without_retaining_raw_value(
    value_factory: object,
    classification: SensitiveValueClass,
) -> None:
    value = value_factory()  # type: ignore[operator]
    assessment = SensitiveValuePolicy().assess(
        {"note": {"value": value}},
        root_location="boundary",
    )

    assert assessment.findings[0].classification is classification
    assert assessment.findings[0].logical_location == "boundary.note.value"
    assert value not in repr(assessment)


def test_sensitive_value_rejection_and_safe_mapping_never_echo_raw_value() -> None:
    value = fake_api_credential()

    with pytest.raises(SensitiveValueRejected) as raised:
        freeze_safe_mapping({"note": value})

    assert value not in str(raised.value)
    assert raised.value.finding.classification is SensitiveValueClass.CREDENTIAL_LIKE


@pytest.mark.parametrize(
    "value",
    (
        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "550e8400-e29b-41d4-a716-446655440000",
        "contract:course:v2",
        "source = {'api_key': config.example_value}",
        "password = example",
        "Legal and cyber lesson about credential hygiene and data exfiltration.",
        "checksum:v3:sha256:abcdef0123456789",
        "idempotency-fingerprint:effect-2026-08-27",
    ),
)
def test_documented_false_positive_examples_remain_safe(value: str) -> None:
    assessment = SensitiveValuePolicy().assess(value, root_location="lesson")

    assert assessment.safe
    assert assessment.findings == ()
