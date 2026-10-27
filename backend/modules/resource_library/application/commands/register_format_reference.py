"""Explicit local binary admission, distinct from textual contributions."""
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference
from backend.modules.resource_library.ports.outbound.format_reference_store import (
    FormatReferenceStore,
)


class RegisterFormatReference:
    def __init__(self, store: FormatReferenceStore, admitted: FormatReference, *, enabled: bool = False) -> None:
        self.store, self.admitted, self.enabled = store, admitted, enabled

    def execute(self, record: FormatReference, source_locator: str) -> FormatReference:
        if not self.enabled or record.as_dict() != self.admitted.as_dict():
            raise ValueError("FORMAT_REFERENCE_NOT_ADMITTED")
        return self.store.register(record, source_locator)
