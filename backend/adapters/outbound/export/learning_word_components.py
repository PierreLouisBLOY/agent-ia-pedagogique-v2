"""Existing chapter components shared by its explicit pedagogical formats."""
from io import BytesIO
from typing import cast
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _w(name: str) -> str:
    return "{" + W + "}" + name


def _p(parent: Element, text: str, style: str = "Normal", *, before: bool = False) -> Element:
    p = SubElement(parent, _w("p"))
    pr = SubElement(p, _w("pPr"))
    SubElement(pr, _w("pStyle"), {_w("val"): style})
    if before:
        SubElement(pr, _w("pageBreakBefore"))
    for i, line in enumerate(text.split("\n")):
        run = SubElement(p, _w("r"))
        if i:
            SubElement(run, _w("br"))
        SubElement(run, _w("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = line
    return p


def _table(parent: Element, value: object, *, response: bool = False,
           keep_together: bool = False) -> None:
    data = object_data(value)
    columns = cast(tuple[str, ...], data["columns"])
    rows = cast(tuple[tuple[str, ...], ...], data["rows"])
    table = SubElement(parent, _w("tbl"))
    props = SubElement(table, _w("tblPr"))
    SubElement(props, _w("tblW"), {_w("w"): "9638", _w("type"): "dxa"})
    SubElement(props, _w("tblLayout"), {_w("type"): "fixed"})
    margins = SubElement(props, _w("tblCellMar"))
    for side in ("top", "bottom", "left", "right"):
        SubElement(margins, _w(side), {_w("w"): "100", _w("type"): "dxa"})
    borders = SubElement(props, _w("tblBorders"))
    for side in ("top", "bottom", "left", "right", "insideH", "insideV"):
        SubElement(borders, _w(side), {_w("val"): "single", _w("sz"): "4", _w("color"): "CCD4DE"})
    grid = SubElement(table, _w("tblGrid"))
    width = 9638 // len(columns)
    for _ in columns:
        SubElement(grid, _w("gridCol"), {_w("w"): str(width)})
    for i, row in enumerate((columns, *rows)):
        tr = SubElement(table, _w("tr"))
        pr = SubElement(tr, _w("trPr"))
        SubElement(pr, _w("cantSplit"))
        if i == 0:
            SubElement(pr, _w("tblHeader"))
        elif response:
            SubElement(pr, _w("trHeight"), {_w("val"): "460", _w("hRule"): "atLeast"})
        for text in row:
            cell = SubElement(tr, _w("tc"))
            cp = SubElement(cell, _w("tcPr"))
            SubElement(cp, _w("tcW"), {_w("w"): str(width), _w("type"): "dxa"})
            SubElement(cp, _w("vAlign"), {_w("val"): "center"})
            SubElement(cp, _w("shd"), {_w("fill"): "F5E6CC" if i == 0 else "F4F7FA" if i % 2 == 0 else "FFFFFF"})
            paragraph = _p(cell, text, "TableHeader" if i == 0 else "TableText")
            if keep_together and i < len(rows):
                properties = paragraph.find(_w("pPr"))
                assert properties is not None
                SubElement(properties, _w("keepNext"))
    _p(parent, "", "Spacer")


def _document(parent: Element, row: dict[str, object], number: int, *, grouped: bool = False) -> None:
    title = _p(parent, f"Document {number} — {row['title']}", "DocumentTitle")
    title_properties = title.find(_w("pPr"))
    assert title_properties is not None
    SubElement(title_properties, _w("keepNext"))
    SubElement(title_properties, _w("keepLines"))
    paragraph = _p(parent, str(row["text"]), "DocumentText")
    if grouped:
        properties = paragraph.find(_w("pPr"))
        assert properties is not None
        SubElement(properties, _w("keepLines"))
        # A document ends here unless its own table follows. Linking a plain
        # document to the next document/question creates an oversized keep chain.
        if row["table"] is not None:
            SubElement(properties, _w("keepNext"))
    if row["table"] is not None:
        _table(parent, row["table"], keep_together=grouped)


def _question(parent: Element, row: dict[str, object], answer: dict[str, object] | None, *, keep_responses: bool = False,
              student_criteria: str | None = None, keep_answer_criteria: bool = True) -> None:
    _p(parent, f"{row['number']}. {row['prompt']}", "Question")
    if student_criteria is not None and answer is None:
        _p(parent, "Réussir — " + student_criteria, "DocumentText")
    if answer is not None:
        for label, field in (("Réponse attendue", "expected_answer"), ("Justification", "rationale"),
                             ("Point de vigilance", "vigilance"), ("Remédiation", "remediation")):
            answer_p = _p(parent, label + " — " + str(answer[field]), "TeacherAnswer")
            if "criteria" in answer and keep_answer_criteria:
                properties = answer_p.find(_w("pPr"))
                assert properties is not None
                SubElement(properties, _w("keepNext"))
                SubElement(properties, _w("keepLines"))
        if "criteria" in answer:
            _p(parent, "Critères de réussite — " + str(answer["criteria"]), "TeacherAnswer")
        return
    response = object_data(row["response"])
    if response["table"] is not None:
        _table(parent, response["table"], response=True, keep_together=keep_responses)
    else:
        lines = cast(int, response["lines"])
        for i in range(lines):
            p = _p(parent, " ", "Response")
            if keep_responses and i < lines-1:
                pr = p.find(_w("pPr"))
                if pr is not None:
                    SubElement(pr, _w("keepNext"))


def _styles(*, reference001: bool = False, exercise_compact: bool = False) -> Element:
    root = Element(_w("styles"))
    defaults = SubElement(root, _w("docDefaults"))
    rd = SubElement(SubElement(defaults, _w("rPrDefault")), _w("rPr"))
    SubElement(rd, _w("rFonts"), {_w("ascii"): "Calibri", _w("hAnsi"): "Calibri"})
    SubElement(rd, _w("lang"), {_w("val"): "fr-FR"})
    specs = {"Normal": (22, False, 100), "Title": (38, True, 200), "Chapter": (24, True, 120),
             "Heading1": (29, True, 160), "Heading2": (24, True, 120), "DocumentTitle": (22, True, 90),
             "DocumentText": (22, False, 100), "Question": (22, True, 80), "Response": (22, False, 80),
             "ConceptTitle": (22, True, 60), "ConceptText": (22, False, 140),
             "TeacherAnswer": (21, False, 80), "TableHeader": (21, True, 30), "TableText": (21, False, 30),
             "Footer": (18, False, 0), "Header": (20, True, 0), "Spacer": (8, False, 20)}
    for name, (size, bold, after) in specs.items():
        if exercise_compact:
            after = {"TeacherAnswer": 20, "Normal": 60, "Heading2": 60}.get(name, after)
        s = SubElement(root, _w("style"), {_w("type"): "paragraph", _w("styleId"): name})
        SubElement(s, _w("name"), {_w("val"): name})
        p = SubElement(s, _w("pPr"))
        line = "240" if exercise_compact and name in {"Footer", "Normal", "DocumentText", "TeacherAnswer"} else "260"
        SubElement(p, _w("spacing"), {_w("after"): str(after), _w("line"): line, _w("lineRule"): "auto"})
        SubElement(p, _w("widowControl"))
        if name in {"Title", "Chapter", "Heading1", "Heading2", "DocumentTitle", "ConceptTitle", "Question"}:
            SubElement(p, _w("keepNext"))
        if name.startswith("Concept"):
            SubElement(p, _w("shd"), {_w("fill"): "E7F2F0"})
            SubElement(p, _w("ind"), {_w("left"): "120", _w("right"): "120"})
        if name == "Response":
            border = SubElement(p, _w("pBdr"))
            SubElement(border, _w("bottom"), {_w("val"): "dotted", _w("sz"): "4", _w("color"): "A6AFBB"})
        if name == "DocumentTitle":
            SubElement(p, _w("shd"), {_w("fill"): "F5E6CC"})
        run = SubElement(s, _w("rPr"))
        SubElement(run, _w("sz"), {_w("val"): str(size)})
        SubElement(run, _w("color"), {_w("val"): "000000"})
        if bold:
            SubElement(run, _w("b"))
    if reference001:
        for style in root.findall(_w("style")):
            style_name = style.get(_w("styleId"))
            color = {"Heading1": "4B3268", "Heading2": "0D666A", "ConceptTitle": "0D666A", "Question": "0D666A", "TableHeader": "FFFFFF"}.get(style_name or "")
            if style_name == "DocumentTitle":
                shade = style.find(_w("pPr") + "/" + _w("shd"))
                assert shade is not None
                shade.set(_w("fill"), "F0EDF5")
            if color:
                color_node = style.find(_w("rPr") + "/" + _w("color"))
                assert color_node is not None
                color_node.set(_w("val"), color)
    return root



def page_section(body: Element, *, reference001: bool = False) -> Element:
    section = SubElement(body, _w("sectPr"))
    SubElement(section, _w("headerReference"), {_w("type"): "default", "{" + R + "}id": "rId2"})
    SubElement(section, _w("footerReference"), {_w("type"): "default", "{" + R + "}id": "rId3"})
    SubElement(section, _w("pgSz"), {_w("w"): "11906", _w("h"): "16838"})
    SubElement(section, _w("pgMar"), {_w("top"): "1134", _w("bottom"): "1134", _w("left"): "1134", _w("right"): "1134", _w("header"): "567", _w("footer"): "567"})
    if reference001:
        margin = section.find(_w("pgMar"))
        assert margin is not None
        for key, value in {"left": "850", "right": "850", "top": "765", "bottom": "765", "header": "340", "footer": "312"}.items():
            margin.set(_w(key), value)
    return section


def page_header(subject: str, level: str) -> Element:
    header = Element(_w("hdr"))
    _p(header, subject.upper() + " • " + level.upper(), "Header")
    return header


def page_footer(label: str) -> Element:
    footer = Element(_w("ftr"))
    p = _p(footer, label + " | ", "Footer")
    field = SubElement(p, _w("fldSimple"), {_w("instr"): " PAGE "})
    SubElement(SubElement(field, _w("r")), _w("t")).text = "1"
    return footer


def package_word(root: Element, styles: Element, header: Element, footer: Element,
                 media: tuple[bytes, ...] = ()) -> bytes:
    rels = Element("Relationships", {"xmlns": PKG})
    SubElement(rels, "Relationship", {"Id": "rId1", "Type": R + "/officeDocument", "Target": "word/document.xml"})
    doc_rels = Element("Relationships", {"xmlns": PKG})
    for number, kind, name in ((1, "styles", "styles.xml"), (2, "header", "header1.xml"), (3, "footer", "footer1.xml")):
        SubElement(doc_rels, "Relationship", {"Id": "rId" + str(number), "Type": R + "/" + kind, "Target": name})
    for number, _ in enumerate(media, 1):
        SubElement(doc_rels, "Relationship", {"Id": "rIdMedia"+str(number), "Type": R+"/image", "Target": "media/figure_"+str(number)+".png"})
    types = Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
    SubElement(types, "Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    if media:
        SubElement(types, "Default", {"Extension": "png", "ContentType": "image/png"})
    for name, kind in (("document.xml", "document.main"), ("styles.xml", "styles"), ("header1.xml", "header"), ("footer1.xml", "footer")):
        SubElement(types, "Override", {"PartName": "/word/" + name, "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml." + kind + "+xml"})
    parts = {"[Content_Types].xml": types, "_rels/.rels": rels, "word/document.xml": root,
             "word/styles.xml": styles, "word/header1.xml": header,
             "word/footer1.xml": footer, "word/_rels/document.xml.rels": doc_rels}
    result = BytesIO()
    with ZipFile(result, "w") as archive:
        for name, node in parts.items():
            info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, tostring(node, encoding="utf-8", xml_declaration=True))
        for number, raw in enumerate(media, 1):
            info = ZipInfo("word/media/figure_"+str(number)+".png", (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, raw)
    return result.getvalue()


def keep_short_group(body: Element, start: int, *, maximum_characters: int = 2600) -> None:
    """Opt-in protection; long answers retain their normal pagination."""
    nodes = list(body)[start:]
    if sum(len("".join(node.itertext())) for node in nodes) > maximum_characters:
        return
    for index, node in enumerate(nodes):
        props = node.find(_w("pPr"))
        if props is None:
            continue
        if props.find(_w("keepLines")) is None:
            SubElement(props, _w("keepLines"))
        if index < len(nodes)-1 and props.find(_w("keepNext")) is None:
            SubElement(props, _w("keepNext"))
