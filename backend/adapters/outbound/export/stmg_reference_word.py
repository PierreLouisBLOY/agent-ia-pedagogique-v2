"""Explicit student-only editorial projection; no reference media or teaching text copied."""
import json
import re
from io import BytesIO
from xml.etree.ElementTree import Element, SubElement, fromstring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter
from backend.adapters.outbound.export.opc_xml import opc_xml
from backend.adapters.outbound.export.word import _paragraph, _w, _xml
from backend.modules.materialization_export.contracts.dto.partial_word_document import (
    PartialWordDocument,
)
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"


def _opc_xml(root: Element, namespace: str) -> bytes:
    return opc_xml(root, namespace, error_code="FORMAT_REFERENCE_OPC_NAMESPACE")


class STMGReferenceWordWriter:
    def __init__(self, identification: dict[str, str], profile: dict[str, object] | None = None) -> None:
        self.identification = dict(identification)
        self.profile = profile

    def write(self, document: WordDocument) -> bytes:
        original = Lot1OOXMLWordWriter().write(document)
        if document.kind != "student":
            return original
        if not isinstance(document, PartialWordDocument):
            raise ValueError("FORMAT_REFERENCE_PARTIAL_STUDENT_REQUIRED")
        with ZipFile(BytesIO(original)) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        root = fromstring(parts["word/document.xml"])
        body = root.find(_w("body"))
        if body is None:
            raise ValueError("FORMAT_REFERENCE_WORD_BODY")
        paragraphs = body.findall(_w("p"))
        if (len(paragraphs) != len(document.blocks) + 1 or len(document.blocks) < 3
                or any(b.style != "Note" for b in document.blocks[:3])
                or document.blocks[0].text != "BROUILLON PARTIEL NON VALIDÉ"
                or not document.blocks[1].text.startswith("Version élève")
                or re.fullmatch(r"Capture [0-9a-f]{32} · Texte SHA256 [0-9a-f]{64}", document.blocks[2].text) is None):
            raise ValueError("FORMAT_REFERENCE_PROVENANCE_SHAPE")
        title = re.sub(r" Version élève(?: — Révision locale [^\r\n]{1,80})?$", "", document.title)
        if title == document.title:
            raise ValueError("FORMAT_REFERENCE_TITLE_SHAPE")
        title_holder = Element("temporary")
        _paragraph(title_holder, "Title", title)
        body.remove(paragraphs[0])
        body.insert(0, title_holder[0])
        internal_notes = []
        for index, block in enumerate(document.blocks):
            if index in {1, 2} or (index == 3 and block.style == "Note"
                    and block.text.startswith("Révision locale ")):
                internal_notes.append({"block_index": index, "text": block.text})
                body.remove(paragraphs[index + 1])
            elif block.style == "Note" and re.fullmatch(
                    r"Synthèse rédigée localement pour la révision [A-Za-z0-9-]+ — proposition soumise à validation enseignante\.", block.text):
                internal_notes.append({"block_index": index, "text": block.text})
                replacement = Element("temporary")
                _paragraph(replacement, "Note", "Synthèse locale proposée à la validation de l’enseignant.")
                position = list(body).index(paragraphs[index + 1])
                body.remove(paragraphs[index + 1])
                body.insert(position, replacement[0])
        # Traceability remains recoverable inside the DOCX, never shown as pupil text.
        custom_properties = Element("Properties", {"xmlns": CUSTOM, "xmlns:vt": VT})
        metadata = {"V2OriginalTitle": document.title,
            "V2InternalNotes": json.dumps(internal_notes, ensure_ascii=False, sort_keys=True),
            "V2ExportProfile": json.dumps(self.profile, ensure_ascii=False, sort_keys=True)}
        for pid, (name, metadata_value) in enumerate(metadata.items(), 2):
            prop = SubElement(custom_properties, "property", {"fmtid": "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}",
                "pid": str(pid), "name": name})
            SubElement(prop, "vt:lpwstr").text = metadata_value
        parts["docProps/custom.xml"] = _xml(custom_properties)
        intro = Element("temporary")
        for key in ("level", "theme", "chapter", "question", "finality", "notions"):
            _paragraph(intro, "Identification", self.identification[key])
        for index, paragraph in enumerate(list(intro)):
            body.insert(index + 1, paragraph)
        # Give the explanatory column of the synthesis room; preserve every cell.
        tables = body.findall(_w("tbl"))
        if tables:
            synthesis = tables[-1]
            grid = synthesis.find(_w("tblGrid"))
            if grid is not None and len(grid) == 3:
                widths = (2400, 4300, 3380)
                for column, width in zip(grid, widths, strict=True):
                    column.set(_w("w"), str(width))
                for row in synthesis.findall(_w("tr")):
                    for cell, width in zip(row.findall(_w("tc")), widths, strict=True):
                        cell_width = cell.find(_w("tcPr") + "/" + _w("tcW"))
                        assert cell_width is not None
                        cell_width.set(_w("w"), str(width))
        section = body.find(_w("sectPr"))
        if section is None:
            raise ValueError("FORMAT_REFERENCE_WORD_SECTION")
        page = section.find(_w("pgSz"))
        margins = section.find(_w("pgMar"))
        assert page is not None and margins is not None
        page.attrib.update({_w("w"): "11906", _w("h"): "16838"})
        margins.attrib.update({_w(k): "720" for k in ("top", "bottom", "left", "right")})
        margins.attrib.update({_w("header"): "360", _w("footer"): "360"})
        for index, kind in enumerate(("header", "footer"), 2):
            section.insert(index - 2, Element(_w(kind + "Reference"), {
                _w("type"): "default", "{" + R + "}id": "rId" + str(index)}))
            part = Element(_w("hdr" if kind == "header" else "ftr"))
            _paragraph(part, "Running", (
                self.identification["level"] + " · " + self.identification["chapter"]
                if kind == "header" else "Projet V2 · BROUILLON PARTIEL NON VALIDÉ · Page "))
            if kind == "footer":
                footer_paragraph = part.find(_w("p"))
                assert footer_paragraph is not None
                field = SubElement(footer_paragraph, _w("fldSimple"), {_w("instr"): " PAGE "})
                SubElement(SubElement(field, _w("r")), _w("t")).text = "1"
            parts["word/" + kind + "1.xml"] = _xml(part)
        styles = fromstring(parts["word/styles.xml"])
        for name, size in (("Identification", "21"), ("Running", "18")):
            style = SubElement(styles, _w("style"), {_w("type"): "paragraph", _w("styleId"): name})
            SubElement(style, _w("name"), {_w("val"): name})
            props = SubElement(style, _w("pPr"))
            SubElement(props, _w("spacing"), {_w("after"): "90"})
            run = SubElement(style, _w("rPr"))
            SubElement(run, _w("rFonts"), {_w("ascii"): "Calibri", _w("hAnsi"): "Calibri"})
            SubElement(run, _w("sz"), {_w("val"): size})
            SubElement(run, _w("color"), {_w("val"): "000000"})
        for style in styles.findall(_w("style")):
            style_id = style.get(_w("styleId"))
            properties = style.find(_w("pPr"))
            run_properties = style.find(_w("rPr"))
            assert properties is not None and run_properties is not None
            if style_id in {"Heading1", "Heading2"}:
                color = run_properties.find(_w("color"))
                assert color is not None
                color.set(_w("val"), "4F81BD")
                previous = properties.find(_w("spacing"))
                if previous is not None:
                    properties.remove(previous)
                SubElement(properties, _w("spacing"), {_w("before"): "220", _w("after"): "120"})
            if style_id == "Note":
                SubElement(properties, _w("shd"), {_w("fill"): "F1F4F6"})
                borders = SubElement(properties, _w("pBdr"))
                for side in ("top", "left", "bottom", "right"):
                    SubElement(borders, _w(side), {_w("val"): "single", _w("sz"): "4",
                        _w("space"): "5", _w("color"): "D9D9D9"})
        rels = fromstring(parts["word/_rels/document.xml.rels"])
        types = fromstring(parts["[Content_Types].xml"])
        package_rels = fromstring(parts["_rels/.rels"])
        SubElement(package_rels, "{" + PKG + "}Relationship", {"Id": "rIdV2Custom",
            "Type": R + "/custom-properties", "Target": "docProps/custom.xml"})
        SubElement(types, "{" + CT + "}Override", {"PartName": "/docProps/custom.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.custom-properties+xml"})
        for index, kind in enumerate(("header", "footer"), 2):
            SubElement(rels, "{" + PKG + "}Relationship", {"Id": "rId" + str(index),
                "Type": R + "/" + kind, "Target": kind + "1.xml"})
            SubElement(types, "{" + CT + "}Override", {"PartName": "/word/" + kind + "1.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml." + kind + "+xml"})
        for name, value in (("word/document.xml", root), ("word/styles.xml", styles)):
            parts[name] = _xml(value)
        for name, value, namespace in (("word/_rels/document.xml.rels", rels, PKG),
                ("[Content_Types].xml", types, CT), ("_rels/.rels", package_rels, PKG)):
            parts[name] = _opc_xml(value, namespace)
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for name, raw in parts.items():
                item = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                item.compress_type = ZIP_DEFLATED
                archive.writestr(item, raw)
        return output.getvalue()
