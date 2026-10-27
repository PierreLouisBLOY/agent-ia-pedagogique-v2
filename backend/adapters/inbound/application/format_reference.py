"""Owner Application boundary for the isolated format-reference library."""
from backend.modules.resource_library.application.commands.register_format_reference import (
    RegisterFormatReference,
)
from backend.modules.resource_library.application.queries.read_format_reference import (
    ReadFormatReference,
)
from backend.modules.resource_library.contracts.dto.format_reference import FormatReference


class FormatReferenceInbound:
    def __init__(self, register: RegisterFormatReference, read: ReadFormatReference) -> None:
        self._register, self._read = register, read

    def register(self, record: FormatReference, source_locator: str) -> FormatReference:
        return self._register.execute(record, source_locator)

    def read(self, reference_id: str) -> FormatReference:
        return self._read.execute(reference_id)
