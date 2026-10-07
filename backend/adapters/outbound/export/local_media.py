"""Deterministic local diagrams drawn in memory on the qualified Windows host.

GDI is used as a font/raster adapter only: no window, screen capture, process,
filesystem access or network. PNG encoding uses Python's standard library.
"""
import ctypes
import math
import struct
import sys
import zlib
from ctypes import wintypes
from typing import Any

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief


class _BitmapHeader(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG),
                ("planes", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
                ("image_size", wintypes.DWORD), ("xppm", wintypes.LONG), ("yppm", wintypes.LONG),
                ("colors", wintypes.DWORD), ("important", wintypes.DWORD)]


def _color(hex_color: str) -> int:
    return int(hex_color[:2], 16) | int(hex_color[2:4], 16) << 8 | int(hex_color[4:6], 16) << 16


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        if sys.platform != "win32":
            raise ValueError("MEDIA_WINDOWS_RENDERER_UNAVAILABLE")
        self.width, self.height = width, height
        self.gdi: Any = ctypes.WinDLL("gdi32", use_last_error=True)
        self.user: Any = ctypes.WinDLL("user32", use_last_error=True)
        signatures = {
            "CreateCompatibleDC": ([wintypes.HDC], wintypes.HDC),
            "CreateDIBSection": ([wintypes.HDC, ctypes.POINTER(_BitmapHeader), wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD], wintypes.HBITMAP),
            "SelectObject": ([wintypes.HDC, wintypes.HGDIOBJ], wintypes.HGDIOBJ),
            "DeleteObject": ([wintypes.HGDIOBJ], wintypes.BOOL),
            "DeleteDC": ([wintypes.HDC], wintypes.BOOL),
            "CreateSolidBrush": ([wintypes.DWORD], wintypes.HBRUSH),
            "CreatePen": ([ctypes.c_int, ctypes.c_int, wintypes.DWORD], wintypes.HPEN),
            "Rectangle": ([wintypes.HDC] + [ctypes.c_int]*4, wintypes.BOOL),
            "RoundRect": ([wintypes.HDC] + [ctypes.c_int]*6, wintypes.BOOL),
            "Ellipse": ([wintypes.HDC] + [ctypes.c_int]*4, wintypes.BOOL),
            "MoveToEx": ([wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p], wintypes.BOOL),
            "LineTo": ([wintypes.HDC, ctypes.c_int, ctypes.c_int], wintypes.BOOL),
            "SetBkMode": ([wintypes.HDC, ctypes.c_int], ctypes.c_int),
            "SetTextColor": ([wintypes.HDC, wintypes.DWORD], wintypes.DWORD),
            "CreateFontW": ([ctypes.c_int]*5+[wintypes.DWORD]*8+[wintypes.LPCWSTR], wintypes.HFONT),
            "GdiFlush": ([], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.gdi, name)
            function.argtypes, function.restype = arguments, result
        self.user.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
                                       ctypes.POINTER(wintypes.RECT), wintypes.UINT]
        self.user.DrawTextW.restype = ctypes.c_int
        self.dc = self.gdi.CreateCompatibleDC(None)
        if not self.dc:
            raise ValueError("MEDIA_RENDER_DC")
        header = _BitmapHeader(ctypes.sizeof(_BitmapHeader), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = ctypes.c_void_p()
        self.bitmap = self.gdi.CreateDIBSection(self.dc, ctypes.byref(header), 0, ctypes.byref(self.bits), None, 0)
        if not self.bitmap or not self.bits.value:
            self.gdi.DeleteDC(self.dc)
            raise ValueError("MEDIA_RENDER_BITMAP")
        self.old_bitmap = self.gdi.SelectObject(self.dc, self.bitmap)
        self.gdi.SetBkMode(self.dc, 1)
        self.box((0, 0, width, height), "FFFFFF", rounded=False)

    def close(self) -> None:
        self.gdi.SelectObject(self.dc, self.old_bitmap)
        self.gdi.DeleteObject(self.bitmap)
        self.gdi.DeleteDC(self.dc)

    def box(self, bounds: tuple[int, int, int, int], fill: str = "EFF5F7", *, rounded: bool = True) -> None:
        brush = self.gdi.CreateSolidBrush(_color(fill))
        pen = self.gdi.CreatePen(0, 2, _color("537487" if fill != "FFFFFF" else "FFFFFF"))
        old_brush, old_pen = self.gdi.SelectObject(self.dc, brush), self.gdi.SelectObject(self.dc, pen)
        try:
            if rounded:
                ok = self.gdi.RoundRect(self.dc, *bounds, 16, 16)
            else:
                ok = self.gdi.Rectangle(self.dc, *bounds)
            if not ok:
                raise ValueError("MEDIA_RENDER_SHAPE")
        finally:
            self.gdi.SelectObject(self.dc, old_brush)
            self.gdi.SelectObject(self.dc, old_pen)
            self.gdi.DeleteObject(brush)
            self.gdi.DeleteObject(pen)

    def line(self, start: tuple[int, int], end: tuple[int, int], *, arrow: bool = False) -> None:
        pen = self.gdi.CreatePen(0, 3, _color("315D73"))
        old = self.gdi.SelectObject(self.dc, pen)
        try:
            self.gdi.MoveToEx(self.dc, *start, None)
            self.gdi.LineTo(self.dc, *end)
            if arrow:
                angle = math.atan2(end[1]-start[1], end[0]-start[0])
                for side in (-0.5, 0.5):
                    point = (round(end[0]-15*math.cos(angle+side)), round(end[1]-15*math.sin(angle+side)))
                    self.gdi.MoveToEx(self.dc, *end, None)
                    self.gdi.LineTo(self.dc, *point)
        finally:
            self.gdi.SelectObject(self.dc, old)
            self.gdi.DeleteObject(pen)

    def ellipse(self, bounds: tuple[int, int, int, int]) -> None:
        pen = self.gdi.CreatePen(0, 3, _color("315D73"))
        old = self.gdi.SelectObject(self.dc, pen)
        try:
            self.gdi.Ellipse(self.dc, *bounds)
        finally:
            self.gdi.SelectObject(self.dc, old)
            self.gdi.DeleteObject(pen)

    def text(self, text: str, bounds: tuple[int, int, int, int], *, size: int = 25, bold: bool = False) -> None:
        font = self.gdi.CreateFontW(-size, 0, 0, 0, 700 if bold else 400, 0, 0, 0, 1, 0, 0, 3, 0, "Arial")
        if not font:
            raise ValueError("MEDIA_RENDER_FONT")
        previous = self.gdi.SelectObject(self.dc, font)
        self.gdi.SetTextColor(self.dc, _color("193646"))
        try:
            rect = wintypes.RECT(*bounds)
            flags = 1 | 16 | 2048
            needed = self.user.DrawTextW(self.dc, text, -1, ctypes.byref(rect), flags | 1024)
            if needed <= 0 or needed > bounds[3]-bounds[1]:
                raise ValueError("MEDIA_TEXT_OVERFLOW")
            rect = wintypes.RECT(bounds[0], bounds[1]+(bounds[3]-bounds[1]-needed)//2, bounds[2], bounds[3])
            if not self.user.DrawTextW(self.dc, text, -1, ctypes.byref(rect), flags):
                raise ValueError("MEDIA_RENDER_TEXT")
        finally:
            self.gdi.SelectObject(self.dc, previous)
            self.gdi.DeleteObject(font)

    def icon(self, kind: str, x: int, y: int) -> None:
        if kind == "PERSON":
            self.ellipse((x-9, y, x+9, y+18))
            self.line((x, y+18), (x, y+45))
            self.line((x-18, y+32), (x+18, y+32))
        elif kind == "COINS":
            for i in range(3):
                self.ellipse((x-25+i*12, y+10-i*5, x+5+i*12, y+40-i*5))
        elif kind == "BOX":
            self.box((x-24, y+3, x+24, y+42), "F8EFE0", rounded=False)
            self.line((x, y+4), (x, y+41))
        elif kind == "IDEA":
            self.ellipse((x-18, y, x+18, y+34))
            self.line((x-10, y+39), (x+10, y+39))
            self.line((x-7, y+44), (x+7, y+44))
        elif kind == "SCREEN":
            self.box((x-28, y, x+28, y+34), "EAF3EF", rounded=False)
            self.line((x, y+34), (x, y+43))
            self.line((x-17, y+44), (x+17, y+44))

    def png(self) -> bytes:
        self.gdi.GdiFlush()
        bgra = ctypes.string_at(self.bits, self.width*self.height*4)
        rgb = bytearray(self.width*self.height*3)
        rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
        scanlines = b"".join(b"\0" + rgb[y*self.width*3:(y+1)*self.width*3] for y in range(self.height))
        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data)&0xFFFFFFFF)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(scanlines, 9)) + chunk(b"IEND", b""))


class WindowsLocalDiagramRenderer:
    renderer_id = "WINDOWS_GDI_ARIAL_NO_AA_RGB_V1"

    def render(self, brief: VisualBrief) -> bytes:
        if brief.data["source_policy"] != "LOCAL_DETERMINISTIC":
            raise ValueError("MEDIA_DRAW_LOCAL_ONLY")
        if brief.data["style_policy"] != "COURSE_LOCAL_DIAGRAM_V1":
            raise ValueError("MEDIA_RENDERER_PROFILE")
        diagram = object_data(brief.data["diagram"])
        layout = diagram["layout"]
        if layout == "FLOW":
            height = 300
            boxes = [(30+i*295, 35, 275+i*295, 215) for i in range(4)]
        elif layout == "RESOURCES":
            height = 500
            boxes = [(30+i*395, 20, 380+i*395, 205) for i in range(3)] + [(230+i*395, 235, 580+i*395, 420) for i in range(2)]
        elif layout == "CYCLE":
            height = 520
            boxes = [(40, 30, 535, 185), (665, 30, 1160, 185), (665, 275, 1160, 430), (40, 275, 535, 430)]
        else:
            height = 580
            boxes = [(350, 15, 850, 130), (350, 190, 850, 305), (80, 365, 540, 485), (660, 365, 1120, 485)]
        canvas = _Canvas(1200, height)
        try:
            nodes = items(diagram["nodes"], 5)
            lookup = {str(n["id"]): box for n, box in zip(nodes, boxes, strict=True)}
            for edge in items(diagram["edges"], 8):
                a, b = lookup[str(edge["source"])], lookup[str(edge["target"])]
                ac, bc = ((a[0]+a[2])//2, (a[1]+a[3])//2), ((b[0]+b[2])//2, (b[1]+b[3])//2)
                if a[2] <= b[0] or b[2] <= a[0]:
                    start, end = ((a[2], ac[1]), (b[0], bc[1])) if bc[0] > ac[0] else ((a[0], ac[1]), (b[2], bc[1]))
                else:
                    start, end = ((ac[0], a[3]), (bc[0], b[1])) if bc[1] > ac[1] else ((ac[0], a[1]), (bc[0], b[3]))
                canvas.line(start, end, arrow=True)
                if edge["label"]:
                    x, y = (start[0]+end[0])//2, (start[1]+end[1])//2
                    canvas.text(str(edge["label"]), (x-100, y-36, x+100, y-7), size=19)
            for node, bounds in zip(nodes, boxes, strict=True):
                canvas.box(bounds)
                x1, y1, x2, y2 = bounds
                if node["icon"] != "NONE":
                    canvas.icon(str(node["icon"]), (x1+x2)//2, y1+12)
                    y1 += 56
                label_height = 58 if layout == "FLOW" else 48
                canvas.text(str(node["label"]), (x1+12, y1+8, x2-12, y1+8+label_height), size=25, bold=True)
                canvas.text(str(node["detail"]), (x1+14, y1+label_height+10, x2-14, y2-10), size=22)
            canvas.text(str(diagram["note"]), (30, height-65, 1170, height-10), size=22)
            return canvas.png()
        finally:
            canvas.close()
