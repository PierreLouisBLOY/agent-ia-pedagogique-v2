"""Short-lived M03 Application inbound for native AG-02 lexical discovery."""

from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.sqlite import SQLiteResourceStoreAdapter
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
from backend.core_contracts.outcome import ApplicationOutcome
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.application.dto.output.local_search_view import (
    LocalSearchView,
)
from backend.modules.resource_library.application.queries.get_resource import GetResourceQuery
from backend.modules.resource_library.application.queries.search_local import SearchLocalQuery
from backend.shared_kernel.correlation import CorrelationId


class ScopedApplicationSearch:
    def __init__(self, target: Read15RuntimeTarget) -> None:
        self.target = target

    def search_local(
        self, *, request: SearchLocalRequest, correlation_id: CorrelationId
    ) -> ApplicationOutcome[LocalSearchView, object]:
        self.target.validate()
        connection = connect_sqlite(
            self.target.runtime_path, readonly=True, allowed_root=self.target.data_root
        )
        try:
            search = SQLiteLocalSearchAdapter(connection)
            inbound = SearchLocalQuery(
                search, GetResourceQuery(SQLiteResourceStoreAdapter(connection))
            )
            with search.read_snapshot():
                return inbound.search_local(request=request, correlation_id=correlation_id)
        finally:
            connection.close()
