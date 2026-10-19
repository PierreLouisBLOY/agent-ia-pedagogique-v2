"""Inbound Application boundary for owner-approved local passage relations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from backend.modules.knowledge_reference.application.commands.admit_exact_passage_context import (
    AdmitExactPassageContext,
)


class ExactPassageContextInbound:
    def __init__(self, command: AdmitExactPassageContext) -> None:
        self.command = command

    def execute(self, request: Mapping[str, object], decision: Mapping[str, object],
                control: Mapping[str, object], *, now: datetime | None = None) -> dict[str, object]:
        return self.command.execute(request, decision, control, now=now)
