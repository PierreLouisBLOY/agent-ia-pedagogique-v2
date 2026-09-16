from typing import Protocol

from backend.modules.materialization_export.contracts.dto.word_document import WordDocument


class WordWriter(Protocol):
    def write(self, document: WordDocument) -> bytes: ...
