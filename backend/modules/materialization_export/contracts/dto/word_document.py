"""Provider- and format-engine-neutral, allowlisted document content."""
from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.modules.materialization_export.contracts.dto.media_asset import CourseMedia


@dataclass(frozen=True, slots=True)
class WordBlock:
    style: str
    text: str


@dataclass(frozen=True, slots=True)
class WordDocument:
    kind: str
    title: str
    blocks: tuple[WordBlock, ...]
    course_chapter: Mapping[str, object] | None = field(default=None, kw_only=True)
    course_media: tuple[CourseMedia, ...] = field(default=(), kw_only=True)

    def __post_init__(self) -> None:
        if self.kind not in {"student", "correction", "marking"} or not self.title:
            raise ValueError("R4_EXPORT_KIND")
        if any(b.style not in {"Normal", "Heading1", "Heading2", "Note"} for b in self.blocks):
            raise ValueError("R4_EXPORT_STYLE")
        if self.course_media and self.course_chapter is None:
            raise ValueError("COURSE_MEDIA_WITHOUT_CHAPTER")

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"kind": self.kind, "title": self.title,
                "blocks": [{"style": b.style, "text": b.text} for b in self.blocks]}
        if self.course_chapter is not None:
            data["course_chapter"] = dict(self.course_chapter)
        return data
