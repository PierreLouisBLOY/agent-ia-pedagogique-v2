"""Only the outbound adapter knows how to draw pixels."""
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief


class MediaRenderer(Protocol):
    renderer_id: str

    def render(self, brief: VisualBrief) -> bytes: ...
