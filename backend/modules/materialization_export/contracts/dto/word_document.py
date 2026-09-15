"""Provider- and format-engine-neutral, allowlisted document content."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WordBlock:
    style: str
    text: str


@dataclass(frozen=True, slots=True)
class WordDocument:
    kind: str
    title: str
    blocks: tuple[WordBlock, ...]

    def __post_init__(self) -> None:
        if self.kind not in {"student", "correction", "marking"} or not self.title:
            raise ValueError("R4_EXPORT_KIND")
        if any(b.style not in {"Normal", "Heading1", "Heading2", "Note"} for b in self.blocks):
            raise ValueError("R4_EXPORT_STYLE")

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "title": self.title,
                "blocks": [{"style": b.style, "text": b.text} for b in self.blocks]}
