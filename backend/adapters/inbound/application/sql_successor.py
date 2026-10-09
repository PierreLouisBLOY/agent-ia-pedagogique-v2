"""Trusted owner-only inbound. Deliberately absent from HTTP, tools and launcher."""

from backend.modules.local_provisioning.application.sql_successor import (
    ApplySQLSuccessor,
    CurrentVersionResolution,
    ResolveSuccessorCurrentVersion,
    SQLSuccessorRequest,
    SQLSuccessorResult,
)


class SQLSuccessorInbound:
    def __init__(self, apply: ApplySQLSuccessor, resolve: ResolveSuccessorCurrentVersion) -> None:
        self._apply, self._resolve = apply, resolve

    def apply(self, request: SQLSuccessorRequest) -> SQLSuccessorResult:
        return self._apply.execute(request)

    def resolve_current(self, resource_ref: str) -> CurrentVersionResolution:
        return self._resolve.execute(resource_ref)
