"""Binary IO remains behind an outbound port; no filesystem type crosses it."""
from typing import Protocol

from backend.modules.resource_library.contracts.dto.format_reference import FormatReference


class FormatReferenceStore(Protocol):
    def register(self, record: FormatReference, source_locator: str) -> FormatReference: ...

    def read(self, reference_id: str) -> FormatReference: ...
