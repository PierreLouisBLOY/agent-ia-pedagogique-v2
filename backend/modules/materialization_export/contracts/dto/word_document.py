"""Provider- and format-engine-neutral, allowlisted document content."""
from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.modules.materialization_export.contracts.dto.media_asset import CourseMedia


@dataclass(frozen=True, slots=True)
class WordBlock:
    style: str
    text: str


@dataclass(frozen=True, slots=True)
class WordMedia:
    anchor_heading: str
    media: CourseMedia


@dataclass(frozen=True, slots=True)
class WordDocument:
    kind: str
    title: str
    blocks: tuple[WordBlock, ...]
    course_chapter: Mapping[str, object] | None = field(default=None, kw_only=True)
    course_media: tuple[CourseMedia, ...] = field(default=(), kw_only=True)
    production_media: tuple[WordMedia, ...] = field(default=(), kw_only=True)
    exercise_profile: str | None = field(default=None, kw_only=True)
    exercise_content: Mapping[str, object] | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if self.kind not in {"student", "correction", "marking"} or not self.title:
            raise ValueError("R4_EXPORT_KIND")
        if any(b.style not in {"Normal", "Heading1", "Heading2", "Note"} for b in self.blocks):
            raise ValueError("R4_EXPORT_STYLE")
        if self.exercise_profile is not None:
            if (self.exercise_profile != "EXERCISE-WORD-1.0" or self.course_chapter is not None
                    or self.course_media or self.production_media):
                raise ValueError("EXERCISE_WORD_PROFILE")
            from backend.modules.materialization_export.contracts.dto.exercise_word_projection import (
                validate_exercise_word_projection,
            )

            object.__setattr__(self, "exercise_content", validate_exercise_word_projection(self.exercise_content, self.kind))
        elif self.exercise_content is not None:
            raise ValueError("EXERCISE_WORD_LAYOUT")
        if self.course_media and self.course_chapter is None:
            raise ValueError("COURSE_MEDIA_WITHOUT_CHAPTER")
        if self.production_media:
            if self.course_chapter is not None or len(self.production_media) > 8:
                raise ValueError("PRODUCTION_WORD_MEDIA_SHAPE")
            for attachment in self.production_media:
                headings = [b for b in self.blocks if b.style in {"Heading1", "Heading2"} and b.text == attachment.anchor_heading]
                if len(headings) != 1 or not attachment.media.brief.data["student_visibility" if self.kind == "student" else "teacher_visibility"]:
                    raise ValueError("PRODUCTION_WORD_MEDIA_BINDING")

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"kind": self.kind, "title": self.title,
                "blocks": [{"style": b.style, "text": b.text} for b in self.blocks]}
        if self.course_chapter is not None:
            data["course_chapter"] = dict(self.course_chapter)
        if self.production_media:
            data["media_assets"] = [{"anchor_heading": attachment.anchor_heading,
                                      **attachment.media.asset.projection(attachment.media.brief)}
                                     for attachment in self.production_media]
        if self.exercise_profile is not None:
            data["exercise_profile"] = self.exercise_profile
            from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain

            data["exercise_content"] = as_plain(self.exercise_content)
        return data
