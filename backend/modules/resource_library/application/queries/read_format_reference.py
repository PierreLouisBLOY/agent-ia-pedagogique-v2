"""Integrity-checked binary-reference read, with no registration side effect."""
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference
from backend.modules.resource_library.ports.outbound.format_reference_store import (
    FormatReferenceStore,
)


class ReadFormatReference:
    def __init__(self, store: FormatReferenceStore, admitted: FormatReference) -> None:
        self.store, self.admitted = store, admitted

    def execute(self, reference_id: str) -> FormatReference:
        if reference_id != self.admitted.reference_id:
            raise ValueError("FORMAT_REFERENCE_NOT_ADMITTED")
        record = self.store.read(reference_id)
        if record.as_dict() != self.admitted.as_dict():
            raise ValueError("FORMAT_REFERENCE_IDENTITY_CHANGED")
        return record
