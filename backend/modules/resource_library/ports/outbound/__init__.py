"""Outbound ports owned by the resource-library module."""

from backend.modules.resource_library.ports.outbound.resource_store import (
    ResourceRecord,
    ResourceStorePort,
)

__all__ = ["ResourceRecord", "ResourceStorePort"]
