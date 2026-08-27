"""Synthetic secret-shaped values used only by defensive security tests."""

from __future__ import annotations


def fake_api_credential() -> str:
    return "sk-" + ("SyntheticOnly" * 4)


def fake_bearer_token() -> str:
    return "Bearer " + ("SyntheticToken" * 4)


def fake_private_key() -> str:
    return "-----BEGIN " + "PRIVATE KEY-----\nSYNTHETIC\n-----END PRIVATE KEY-----"


def fake_connection_secret() -> str:
    return "postgresql://student:" + "synthetic-pass@example.invalid/course"


def fake_private_path() -> str:
    return "C:" + "\\Users\\Synthetic\\private.txt"
