"""Trusted maintenance inbound; never registered in HTTP, agent tools or launcher."""

from backend.modules.local_provisioning.application.sql_rollback import (
    RollbackSQLSuccessor,
    SQLRollbackRequest,
    SQLRollbackResult,
)


class SQLRollbackInbound:
    def __init__(self, use_case: RollbackSQLSuccessor) -> None:
        self._use_case = use_case

    def prepare(self, request: SQLRollbackRequest) -> SQLRollbackResult:
        return self._use_case.prepare(request)

    def execute(self, request: SQLRollbackRequest, intention_sha256: str) -> SQLRollbackResult:
        return self._use_case.execute(request, intention_sha256)
