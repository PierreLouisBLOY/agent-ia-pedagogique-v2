"""Inline, embedded PNG only; validated provenance remains outside the learner text."""
from xml.etree.ElementTree import Element, SubElement

from backend.modules.materialization_export.contracts.dto.media_asset import CourseMedia

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def draw_image(parent: Element, media: CourseMedia, number: int) -> None:
    width, height = int(str(media.asset.data["width"])), int(str(media.asset.data["height"]))
    cx, cy = 9638*635, round(9638*635*height/width)
    paragraph = SubElement(parent, "{"+W+"}p")
    properties = SubElement(paragraph, "{"+W+"}pPr")
    SubElement(properties, "{"+W+"}keepNext")
    SubElement(properties, "{"+W+"}spacing", {"{"+W+"}before": "120", "{"+W+"}after": "50"})
    drawing = SubElement(SubElement(paragraph, "{"+W+"}r"), "{"+W+"}drawing")
    inline = SubElement(drawing, "{"+WP+"}inline", {"distT": "0", "distB": "0", "distL": "0", "distR": "0"})
    SubElement(inline, "{"+WP+"}extent", {"cx": str(cx), "cy": str(cy)})
    SubElement(inline, "{"+WP+"}effectExtent", {"l": "0", "t": "0", "r": "0", "b": "0"})
    SubElement(inline, "{"+WP+"}docPr", {"id": str(100+number), "name": "Illustration "+str(number),
        "descr": str(media.brief.data["alt_text"]), "title": str(media.brief.data["caption"])})
    locks = SubElement(inline, "{"+WP+"}cNvGraphicFramePr")
    SubElement(locks, "{"+A+"}graphicFrameLocks", {"noChangeAspect": "1"})
    graphic = SubElement(inline, "{"+A+"}graphic")
    content = SubElement(graphic, "{"+A+"}graphicData", {"uri": PIC})
    picture = SubElement(content, "{"+PIC+"}pic")
    nv = SubElement(picture, "{"+PIC+"}nvPicPr")
    SubElement(nv, "{"+PIC+"}cNvPr", {"id": str(100+number), "name": "figure_"+str(number)+".png",
        "descr": str(media.brief.data["alt_text"])})
    SubElement(nv, "{"+PIC+"}cNvPicPr")
    fill = SubElement(picture, "{"+PIC+"}blipFill")
    SubElement(fill, "{"+A+"}blip", {"{"+R+"}embed": "rIdMedia"+str(number)})
    SubElement(SubElement(fill, "{"+A+"}stretch"), "{"+A+"}fillRect")
    shape = SubElement(picture, "{"+PIC+"}spPr")
    transform = SubElement(shape, "{"+A+"}xfrm")
    SubElement(transform, "{"+A+"}off", {"x": "0", "y": "0"})
    SubElement(transform, "{"+A+"}ext", {"cx": str(cx), "cy": str(cy)})
    SubElement(SubElement(shape, "{"+A+"}prstGeom", {"prst": "rect"}), "{"+A+"}avLst")
