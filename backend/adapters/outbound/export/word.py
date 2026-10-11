"""Deterministic editable OOXML. No macros, comments, hidden text or external targets."""
from io import BytesIO
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.modules.materialization_export.contracts.dto.word_document import WordDocument

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/package/2006/relationships"


def _w(name: str) -> str:
    return "{" + _W + "}" + name


def _xml(element: Element) -> bytes:
    raw = tostring(element, encoding="utf-8", xml_declaration=True)
    if not isinstance(raw, bytes):
        raise ValueError("R4_XML_ENCODING")
    return raw


def _paragraph(body: Element, style: str, text: str) -> None:
    if any(not (char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF
                or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF)
           for char in text):
        raise ValueError("R4_XML_CHARACTER_REJECTED")
    paragraph = SubElement(body, _w("p"))
    properties = SubElement(paragraph, _w("pPr"))
    SubElement(properties, _w("pStyle"), {_w("val"): style})
    for index, line in enumerate(text.split("\n")):
        run = SubElement(paragraph, _w("r"))
        if index:
            SubElement(run, _w("br"))
        SubElement(run, _w("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = line


class OOXMLWordWriter:
    def write(self, document: WordDocument) -> bytes:
        if document.production_media:
            raise ValueError("PRODUCTION_MEDIA_PRODUCT_WRITER_REQUIRED")
        root = Element(_w("document"))
        body = SubElement(root, _w("body"))
        _paragraph(body, "Title", document.title)
        for block in document.blocks:
            _paragraph(body, block.style, block.text)
        section = SubElement(body, _w("sectPr"))
        SubElement(section, _w("pgSz"), {_w("w"): "12240", _w("h"): "15840"})
        SubElement(section, _w("pgMar"), {_w("top"): "1080", _w("bottom"): "1080",
            _w("left"): "1080", _w("right"): "1080", _w("header"): "540", _w("footer"): "540"})
        styles = Element(_w("styles"))
        for name, size in (("Normal", "23"), ("Title", "40"), ("Heading1", "30"),
                           ("Heading2", "25"), ("Note", "21")):
            style = SubElement(styles, _w("style"), {_w("type"): "paragraph", _w("styleId"): name})
            SubElement(style, _w("name"), {_w("val"): name})
            props = SubElement(style, _w("pPr"))
            SubElement(props, _w("spacing"), {_w("after"): "140", _w("line"): "276",
                                              _w("lineRule"): "auto"})
            if name != "Normal" and name != "Note":
                SubElement(props, _w("keepNext"))
            run = SubElement(style, _w("rPr"))
            SubElement(run, _w("rFonts"), {_w("ascii"): "Calibri", _w("hAnsi"): "Calibri"})
            SubElement(run, _w("sz"), {_w("val"): size})
            SubElement(run, _w("color"), {_w("val"): "000000"})
            if name in {"Title", "Heading1", "Heading2"}:
                SubElement(run, _w("b"))
        relationships = Element("Relationships", {"xmlns": _R})
        SubElement(relationships, "Relationship", {"Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "Target": "word/document.xml"})
        doc_rels = Element("Relationships", {"xmlns": _R})
        SubElement(doc_rels, "Relationship", {"Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
            "Target": "styles.xml"})
        types = Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
        SubElement(types, "Default", {"Extension": "rels",
            "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
        for name, kind in (("document", "document.main"), ("styles", "styles")):
            SubElement(types, "Override", {"PartName": "/word/" + name + ".xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml."
                               + kind + "+xml"})
        parts = {"[Content_Types].xml": _xml(types), "_rels/.rels": _xml(relationships),
                 "word/document.xml": _xml(root), "word/styles.xml": _xml(styles),
                 "word/_rels/document.xml.rels": _xml(doc_rels)}
        target = BytesIO()
        with ZipFile(target, "w") as archive:
            for name, data in parts.items():
                item = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                item.compress_type = ZIP_DEFLATED
                archive.writestr(item, data)
        return target.getvalue()
