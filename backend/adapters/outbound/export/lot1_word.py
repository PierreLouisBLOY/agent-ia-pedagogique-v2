"""Versioned OOXML table writer; delegates unchanged R4 documents to R4."""

from io import BytesIO
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.adapters.outbound.export.word import OOXMLWordWriter, _paragraph
from backend.modules.materialization_export.contracts.dto.lot1_word_table import (
    Lot1WordDocument,
    Lot1WordTable,
)
from backend.modules.materialization_export.contracts.dto.partial_word_document import (
    PartialWordDocument,
)
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordDocument,
)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _w(name: str) -> str:
    return "{" + _W + "}" + name


def _table(value: Lot1WordTable, *, keep_rows: bool = False, min_height: int = 0) -> Element:
    table = Element(_w("tbl"))
    props = SubElement(table, _w("tblPr"))
    SubElement(props, _w("tblW"), {_w("w"): "0", _w("type"): "auto"})
    borders = SubElement(props, _w("tblBorders"))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        SubElement(borders, _w(edge), {_w("val"): "single", _w("sz"): "6",
                                      _w("color"): "D9D9D9"})
    margins = SubElement(props, _w("tblCellMar"))
    for side in ("top", "left", "bottom", "right"):
        SubElement(margins, _w(side), {_w("w"): "100", _w("type"): "dxa"})
    columns = len(value.rows[0])
    first_width = 4032 if columns > 2 else 5040
    other_width = (10080 - first_width) // (columns - 1)
    widths = [first_width] + [other_width] * (columns - 1)
    grid = SubElement(table, _w("tblGrid"))
    for width in widths:
        SubElement(grid, _w("gridCol"), {_w("w"): str(width)})
    for index, row in enumerate(value.rows):
        tr = SubElement(table, _w("tr"))
        if index == 0 or keep_rows:
            row_props = SubElement(tr, _w("trPr"))
            if keep_rows:
                SubElement(row_props, _w("cantSplit"))
            if index == 0:
                SubElement(row_props, _w("tblHeader"), {_w("val"): "true"})
            elif min_height:
                SubElement(row_props, _w("trHeight"), {_w("val"): str(min_height), _w("hRule"): "atLeast"})
        for column, cell in enumerate(row):
            tc = SubElement(tr, _w("tc"))
            tc_props = SubElement(tc, _w("tcPr"))
            SubElement(tc_props, _w("tcW"), {_w("w"): str(widths[column]),
                                             _w("type"): "dxa"})
            SubElement(tc_props, _w("vAlign"), {_w("val"): "center"})
            if index == 0:
                SubElement(tc_props, _w("shd"), {_w("fill"): "EAF2F8"})
            _paragraph(tc, "Normal", cell)
            if keep_rows and index == 0:
                header_props = tc.find(_w("p") + "/" + _w("pPr"))
                if header_props is not None:
                    SubElement(header_props, _w("keepNext"))
            if column > 0:
                paragraph = tc.find(_w("p"))
                if paragraph is not None:
                    ppr = paragraph.find(_w("pPr"))
                    if ppr is not None:
                        SubElement(ppr, _w("jc"), {_w("val"): "center"})
    return table


class Lot1OOXMLWordWriter(OOXMLWordWriter):
    def write(self, document: WordDocument) -> bytes:
        original = super().write(document)
        if not isinstance(document, (Lot1WordDocument, PartialWordDocument)) or not document.tables:
            return original
        with ZipFile(BytesIO(original)) as source:
            parts = {name: source.read(name) for name in source.namelist()}
        root = fromstring(parts["word/document.xml"])
        body = root.find(_w("body"))
        if body is None:
            raise ValueError("LOT1_WORD_BODY_REJECTED")
        # Title is paragraph zero; WordBlock i follows at body index i + 1.
        for value in sorted(document.tables, key=lambda t: t.after_block_index, reverse=True):
            height = 0
            if isinstance(document, PartialWordDocument) and document.table_min_row_heights:
                height = document.table_min_row_heights[document.tables.index(value)]
            body.insert(value.after_block_index + 2, _table(value,
                keep_rows=isinstance(document, PartialWordDocument), min_height=height))
        parts["word/document.xml"] = tostring(root, encoding="utf-8", xml_declaration=True)
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for name, data in parts.items():
                item = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                item.compress_type = ZIP_DEFLATED
                archive.writestr(item, data)
        return output.getvalue()
