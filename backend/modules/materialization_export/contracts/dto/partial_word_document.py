"""An explicitly unvalidated captured document; never a CourseChapter."""
from dataclasses import dataclass

from backend.modules.materialization_export.contracts.dto.lot1_word_table import (
    Lot1WordTable,
)
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordDocument,
)


@dataclass(frozen=True, slots=True)
class PartialWordDocument(WordDocument):
    tables: tuple[Lot1WordTable, ...] = ()
    table_min_row_heights: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        super(PartialWordDocument, self).__post_init__()
        if (self.kind not in {"student", "correction"} or type(self.tables) is not tuple
                or any(type(t) is not Lot1WordTable or t.after_block_index >= len(self.blocks)
                    for t in self.tables)
                or len({t.after_block_index for t in self.tables}) != len(self.tables)
                or self.course_chapter is not None or self.course_media or self.production_media):
            raise ValueError("PARTIAL_DOCUMENT_REJECTED")
        if (type(self.table_min_row_heights) is not tuple
                or (self.table_min_row_heights and len(self.table_min_row_heights) != len(self.tables))
                or any(type(h) is not int or (h != 0 and not 360 <= h <= 2000)
                    for h in self.table_min_row_heights)):
            raise ValueError("PARTIAL_HEIGHT_REJECTED")

    def as_dict(self) -> dict[str, object]:
        result = super(PartialWordDocument, self).as_dict()
        result.update(status="PARTIAL_UNVALIDATED", tables=[{
            "after_block_index": t.after_block_index, "rows": [list(row) for row in t.rows]}
            for t in self.tables])
        if self.table_min_row_heights:
            result["table_min_row_heights"] = list(self.table_min_row_heights)
        return result
