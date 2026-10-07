"""Closed, local illustration profile. Draws original fictional scenes in memory."""
from backend.adapters.outbound.export.local_media import _Canvas, _color
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief

PALETTE = ("E8F1EF", "FAEAD8", "E9EAF5", "F2E7E8", "EAF0F7")


def _oval(c: _Canvas, bounds: tuple[int, int, int, int], fill: str) -> None:
    brush = c.gdi.CreateSolidBrush(_color(fill))
    pen = c.gdi.CreatePen(0, 2, _color("315D73"))
    old_brush, old_pen = c.gdi.SelectObject(c.dc, brush), c.gdi.SelectObject(c.dc, pen)
    try:
        if not c.gdi.Ellipse(c.dc, *bounds):
            raise ValueError("MEDIA_RENDER_SHAPE")
    finally:
        c.gdi.SelectObject(c.dc, old_brush)
        c.gdi.SelectObject(c.dc, old_pen)
        c.gdi.DeleteObject(brush)
        c.gdi.DeleteObject(pen)


def _person(c: _Canvas, x: int, y: int, colour: str) -> None:
    # Deliberately schematic: appearance is not asserted by the scenario.
    _oval(c, (x-21, y, x+21, y+42), "FAEAD8")
    _oval(c, (x-41, y+43, x+41, y+110), colour)
    c.line((x-6, y+18), (x-5, y+18))
    c.line((x+6, y+18), (x+7, y+18))
    c.line((x-5, y+30), (x+5, y+30))


def _scene(c: _Canvas, nodes: tuple[dict[str, object], ...]) -> None:
    c.box((20, 20, 395, 210), "E8F1EF", rounded=False)
    c.text("Livres Rivage", (35, 25, 380, 65), size=32, bold=True)
    for shelf in (125, 185):
        c.line((45, shelf), (370, shelf))
        for i in range(8):
            c.box((50+i*40, shelf-45-(i % 2)*7, 78+i*40, shelf), PALETTE[i % 5], rounded=False)
    for i, node in enumerate(nodes):
        x = 540+i*240
        _person(c, x, 25, PALETTE[i])
        c.text(str(node["label"]), (x-100, 139, x+100, 177), size=29, bold=True)
        c.text(str(node["detail"]), (x-105, 178, x+105, 214), size=23)
    c.box((440, 220, 1170, 255), "FAEAD8", rounded=False)
    c.text("Permanence de prêt", (520, 220, 1120, 255), size=25)


def _portraits(c: _Canvas, nodes: tuple[dict[str, object], ...]) -> None:
    for i, node in enumerate(nodes):
        x = 190+i*400
        _person(c, x-100, 12, PALETTE[i])
        c.text(str(node["label"]), (x-35, 17, x+165, 56), size=32, bold=True)
        c.text(str(node["detail"]), (x-35, 59, x+177, 115), size=25)


def _timeline(c: _Canvas, nodes: tuple[dict[str, object], ...]) -> None:
    for i, node in enumerate(nodes):
        x = 115+i*240
        if i < 4:
            c.line((x+24, 40), (x+215, 40), arrow=True)
        _oval(c, (x-23, 17, x+23, 63), PALETTE[i])
        c.text(str(i+1), (x-20, 18, x+20, 61), size=27, bold=True)
        c.text(str(node["label"]), (x-105, 76, x+105, 141), size=26, bold=True)
        c.text(str(node["detail"]), (x-105, 145, x+105, 214), size=23)


def _workspace(c: _Canvas, nodes: tuple[dict[str, object], ...]) -> None:
    for i, node in enumerate(nodes):
        x = 25+i*400
        c.box((x, 10, x+350, 150), PALETTE[i], rounded=False)
        c.text(str(node["label"]), (x+10, 14, x+340, 48), size=27, bold=True)
        c.text(str(node["detail"]), (x+10, 55, x+340, 89), size=25)
        c.line((x+20, 127), (x+330, 127))


def _resources(c: _Canvas, nodes: tuple[dict[str, object], ...]) -> None:
    for i, node in enumerate(nodes):
        x = 120+i*240
        _oval(c, (x-43, 15, x+43, 91), PALETTE[i])
        c.icon(str(node["icon"]), x, 28)
        c.text(str(node["label"]), (x-110, 105, x+110, 160), size=27, bold=True)
        c.text(str(node["detail"]), (x-110, 164, x+110, 269), size=25)


def _graph(c: _Canvas, diagram: dict[str, object], *, cycle: bool) -> None:
    nodes = items(diagram["nodes"], 5)
    boxes = ([(35, 15, 540, 145), (660, 15, 1165, 145), (660, 215, 1165, 345), (35, 215, 540, 345)]
             if cycle else [(360, 10, 840, 105), (360, 145, 840, 240), (30, 285, 530, 380), (670, 285, 1170, 380)])
    lookup = {str(n["id"]): box for n, box in zip(nodes, boxes, strict=True)}
    for edge in items(diagram["edges"], 8):
        a, b = lookup[str(edge["source"])], lookup[str(edge["target"])]
        ax, ay, bx, by = (a[0]+a[2])//2, (a[1]+a[3])//2, (b[0]+b[2])//2, (b[1]+b[3])//2
        if a[2] < b[0] or b[2] < a[0]:
            start, end = ((a[2], ay), (b[0], by)) if bx > ax else ((a[0], ay), (b[2], by))
        else:
            start, end = ((ax, a[3]), (bx, b[1])) if by > ay else ((ax, a[1]), (bx, b[3]))
        c.line(start, end, arrow=True)
    for i, (node, box) in enumerate(zip(nodes, boxes, strict=True)):
        if cycle or i == 0:
            _oval(c, box, PALETTE[i])
        else:
            c.box(box, PALETTE[i], rounded=i == 1)
        x1, y1, x2, y2 = box
        c.text(str(node["label"]), (x1+55, y1+17, x2-55, y1+53), size=27, bold=True)
        c.text(str(node["detail"]), (x1+60, y1+48, x2-60, y2-9), size=23)


class WindowsLocalIllustrationRenderer:
    renderer_id = "WINDOWS_GDI_ARIAL_NO_AA_RGB_CONTEXTUAL_V2"

    def render(self, brief: VisualBrief) -> bytes:
        if brief.data["source_policy"] != "LOCAL_DETERMINISTIC" or brief.data["style_policy"] != "COURSE_LOCAL_ILLUSTRATION_V2":
            raise ValueError("MEDIA_RENDERER_PROFILE")
        diagram = object_data(brief.data["diagram"])
        layout = str(diagram["layout"])
        heights = {"LIBRARY_SCENE": 310, "CHARACTERS": 175, "TIMELINE": 280, "WORKSPACE": 215,
                   "RESOURCES": 335, "CYCLE": 410, "RESPONSIBILITIES": 445}
        if layout not in heights:
            raise ValueError("MEDIA_CONTEXTUAL_LAYOUT_UNSUPPORTED")
        height = heights[layout]
        c = _Canvas(1200, height)
        try:
            nodes = items(diagram["nodes"], 5)
            if layout in {"CYCLE", "RESPONSIBILITIES"}:
                _graph(c, diagram, cycle=layout == "CYCLE")
            elif layout == "LIBRARY_SCENE":
                _scene(c, nodes)
            elif layout == "CHARACTERS":
                _portraits(c, nodes)
            elif layout == "TIMELINE":
                _timeline(c, nodes)
            elif layout == "WORKSPACE":
                _workspace(c, nodes)
            elif layout == "RESOURCES":
                _resources(c, nodes)
            c.text(str(diagram["note"]), (20, height-54, 1180, height-5), size=24)
            return c.png()
        finally:
            c.close()
