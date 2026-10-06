"""Bounded, immutable, self-contained media; no filesystem or URL resolution."""
import base64
import binascii
import hashlib
import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
from backend.shared_kernel._safe_data import freeze_safe_mapping

MAX_PNG_BYTES = 64 * 1024
LICENCES = {"LOCAL_ORIGINAL", "CC0", "CC-BY-4.0", "CC-BY-SA-4.0", "USER_PERMISSION", "GENERATED_WITH_REUSE_RIGHTS"}


def validate_png(raw: bytes) -> tuple[int, int]:
    if not isinstance(raw, bytes) or not 50 <= len(raw) <= MAX_PNG_BYTES or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("MEDIA_PNG_REJECTED")
    offset, width, height, channels = 8, 0, 0, 0
    compressed = bytearray()
    kinds: list[bytes] = []
    ended = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("MEDIA_PNG_TRUNCATED")
        size = struct.unpack_from(">I", raw, offset)[0]
        end = offset + 12 + size
        if end > len(raw):
            raise ValueError("MEDIA_PNG_TRUNCATED")
        kind, chunk = raw[offset+4:offset+8], raw[offset+8:offset+8+size]
        crc = struct.unpack_from(">I", raw, offset+8+size)[0]
        if zlib.crc32(kind + chunk) & 0xFFFFFFFF != crc:
            raise ValueError("MEDIA_PNG_CRC")
        if kind not in {b"IHDR", b"IDAT", b"IEND"}:
            raise ValueError("MEDIA_PNG_UNSUPPORTED_CHUNK")
        if kind == b"IHDR":
            if kinds or size != 13:
                raise ValueError("MEDIA_PNG_HEADER")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
            if not (64 <= width <= 1600 and 64 <= height <= 1000) or (depth, compression, filtering, interlace) != (8, 0, 0, 0) or color not in {2, 6}:
                raise ValueError("MEDIA_PNG_DIMENSIONS")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            if not kinds or kinds[-1] not in {b"IHDR", b"IDAT"}:
                raise ValueError("MEDIA_PNG_ORDER")
            compressed.extend(chunk)
        else:
            if size or not compressed or end != len(raw):
                raise ValueError("MEDIA_PNG_END")
            ended = True
        kinds.append(kind)
        offset = end
    if not ended:
        raise ValueError("MEDIA_PNG_END")
    expected = height * (1 + width * channels)
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(bytes(compressed), expected + 1)
    except zlib.error as exc:
        raise ValueError("MEDIA_PNG_COMPRESSION") from exc
    if len(decoded) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("MEDIA_PNG_DECODE_SIZE")
    if any(decoded[y*(1+width*channels)] > 4 for y in range(height)):
        raise ValueError("MEDIA_PNG_FILTER")
    return width, height


@dataclass(frozen=True, slots=True)
class MediaAsset:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        d = object_data(self.data, {"contract_id", "visual_id", "brief_sha256", "png_sha256", "bytes_base64",
                                    "width", "height", "mime_type", "renderer_id", "provenance"})
        if d["contract_id"] != "MEDIA-ASSET-1.0" or d["mime_type"] != "image/png":
            raise ValueError("MEDIA_CONTRACT")
        for key in ("visual_id", "brief_sha256", "png_sha256", "renderer_id"):
            nonempty(d[key], 160)
        if not isinstance(d["bytes_base64"], str) or len(d["bytes_base64"]) > MAX_PNG_BYTES*4//3+4:
            raise ValueError("MEDIA_PNG_SIZE")
        try:
            raw = base64.b64decode(d["bytes_base64"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("MEDIA_BASE64") from exc
        width, height = validate_png(raw)
        if (type(d["width"]) is not int or type(d["height"]) is not int or
                (d["width"], d["height"]) != (width, height) or hashlib.sha256(raw).hexdigest() != d["png_sha256"]):
            raise ValueError("MEDIA_IDENTITY")
        provenance = object_data(d["provenance"], {"source_kind", "source_ref", "source_sha256", "licence", "rights_basis", "admission_ref"})
        if provenance["licence"] not in LICENCES or provenance["source_kind"] not in {
                "LOCAL_DETERMINISTIC", "USER_SUPPLIED", "LICENSED_EXTERNAL", "GENERATED_ADMITTED"}:
            raise ValueError("MEDIA_PROVENANCE_REQUIRED")
        for value in provenance.values():
            nonempty(value, 1000)
        expected_source = d["brief_sha256"] if provenance["source_kind"] == "LOCAL_DETERMINISTIC" else d["png_sha256"]
        if provenance["source_sha256"] != expected_source:
            raise ValueError("MEDIA_SOURCE_HASH")
        object.__setattr__(self, "data", freeze_safe_mapping(d))

    @property
    def raw(self) -> bytes:
        return base64.b64decode(str(self.data["bytes_base64"]), validate=True)

    @property
    def sha256(self) -> str:
        return fingerprint(self.data)

    def bind(self, brief: VisualBrief) -> None:
        if (self.data["brief_sha256"] != brief.sha256 or self.data["visual_id"] != brief.data["visual_id"]
                or object_data(self.data["provenance"])["source_kind"] != brief.data["source_policy"]):
            raise ValueError("MEDIA_BRIEF_BINDING")

    def projection(self, brief: VisualBrief) -> dict[str, object]:
        self.bind(brief)
        return {**{key: self.data[key] for key in ("visual_id", "bytes_base64", "png_sha256", "width", "height", "mime_type")},
                **{key: brief.data[key] for key in ("section_ref", "preferred_position", "caption", "alt_text")}}


@dataclass(frozen=True, slots=True)
class CourseMedia:
    brief: VisualBrief
    asset: MediaAsset

    def __post_init__(self) -> None:
        self.asset.bind(self.brief)
