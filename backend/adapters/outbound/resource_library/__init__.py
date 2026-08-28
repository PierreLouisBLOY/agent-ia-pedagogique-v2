"""Resource-library outbound adapters."""

from backend.adapters.outbound.resource_library.sqlite import (
    SQLiteResourceStoreAdapter,
)

__all__ = ["SQLiteResourceStoreAdapter"]
