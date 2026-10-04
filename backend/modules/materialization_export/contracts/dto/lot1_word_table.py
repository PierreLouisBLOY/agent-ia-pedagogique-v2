"""Versioned, bounded table projection for a saved student Word document."""

from dataclasses import dataclass

from backend.modules.materialization_export.contracts.dto.word_document import WordDocument


@dataclass(frozen=True, slots=True)
class Lot1WordTable:
    after_block_index: int
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if (type(self.after_block_index) is not int or self.after_block_index < 0
                or not 2 <= len(self.rows) <= 12
                or not 2 <= len(self.rows[0]) <= 5
                or any(len(row) != len(self.rows[0]) or any(
                    type(cell) is not str or len(cell) > 300 for cell in row)
                    for row in self.rows)
                or any(not cell.strip() for cell in self.rows[0])):
            raise ValueError("LOT1_WORD_TABLE_REJECTED")


@dataclass(frozen=True, slots=True)
class Lot1WordDocument(WordDocument):
    tables: tuple[Lot1WordTable, ...] = ()

    def __post_init__(self) -> None:
        super(Lot1WordDocument, self).__post_init__()
        if self.kind != "student" or any(t.after_block_index >= len(self.blocks) for t in self.tables):
            raise ValueError("LOT1_WORD_TABLE_REJECTED")
        if len({t.after_block_index for t in self.tables}) != len(self.tables):
            raise ValueError("LOT1_WORD_TABLE_REJECTED")

    def as_dict(self) -> dict[str, object]:
        value = super(Lot1WordDocument, self).as_dict()
        value["tables"] = [{"after_block_index": t.after_block_index,
                            "rows": [list(row) for row in t.rows]} for t in self.tables]
        return value
