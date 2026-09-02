from enum import StrEnum


class SessionLifecycleStatus(StrEnum):
    """M05-owned session lifecycle vocabulary accepted by the canonical DDL."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
