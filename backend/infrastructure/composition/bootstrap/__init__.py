"""Explicit infrastructure bootstrap composition surfaces."""

from backend.infrastructure.composition.bootstrap.observability import (
    MINIMUM_OBSERVABILITY_SIGNAL_COUNT,
    LocalObservabilitySession,
    build_local_observability_session,
)

__all__ = [
    "MINIMUM_OBSERVABILITY_SIGNAL_COUNT",
    "LocalObservabilitySession",
    "build_local_observability_session",
]
