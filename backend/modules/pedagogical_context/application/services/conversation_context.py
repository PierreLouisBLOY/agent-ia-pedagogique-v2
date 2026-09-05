"""Limited French pilot extraction; every proposal requires explicit confirmation."""
from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal

from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    FIELDS,
    ContextRejected,
    ContextUpdate,
    text_value,
    validated_values,
)


class ConversationContextService:
    def propose(
        self, *, text: str, current: Mapping[str, object], patch: Mapping[str, object],
        previous_text: str = "",
    ) -> ContextUpdate:
        text = text_value(text, 4000, 12 * 1024)
        lower = text.casefold()
        proposal: dict[str, object] = {}
        conflicts: set[str] = set()
        if re.search(r"\b(contrôle|controle|évaluation|evaluation)\b", lower):
            proposal["resource_type"] = "ASSESSMENT"
            proposal["language"] = "fr"
        previous = previous_text.casefold()
        bts_context = ("bts" in lower and "cg" in lower) or (
            "bts" in previous and "cg" in previous and "stmg" not in lower
        )
        if bts_context:
            years = []
            if re.search(r"premi[èe]re|1[èe]re|année\s*1|annee\s*1", lower):
                years.append("BTS_CG_YEAR_1")
            if re.search(r"deuxi[èe]me|seconde|2[èe]me|année\s*2|annee\s*2", lower):
                years.append("BTS_CG_YEAR_2")
            if len(years) == 1:
                proposal["level"] = years[0]
            elif len(years) > 1:
                conflicts.add("level")
        elif "stmg" in lower:
            if "première" in lower or "premiere" in lower:
                proposal["level"] = "FIRST_STMG"
            elif "terminale" in lower:
                proposal["level"] = "FINAL_STMG"
        topics = tuple(topic for topic, marker in (
            ("bilan fonctionnel", "bilan fonctionnel"), ("BFR", "bfr")
        ) if marker in lower)
        if topics and ("topics" not in current or re.search(r"\b(sur|thème|notions?)\b", lower)):
            proposal["topics"] = topics
        if "analyse financière" in lower or "analyse financiere" in lower:
            proposal["discipline"] = "analyse financière"
        for marker, difficulty in (("standard", "STANDARD"), ("guidée", "GUIDED"),
                              ("guidé", "GUIDED"), ("avancée", "ADVANCED"),
                              ("avancé", "ADVANCED")):
            if marker in lower:
                if "difficulty" in proposal and proposal["difficulty"] != difficulty:
                    conflicts.add("difficulty")
                proposal["difficulty"] = difficulty
        durations = {int(n) * (60 if unit.startswith("h") else 1)
                     for n, unit in re.findall(r"\b([0-9]{1,3})\s*(heures?|h|min(?:utes?)?)\b", lower)}
        if len(durations) == 1:
            proposal["duration_minutes"] = durations.pop()
        elif durations:
            conflicts.add("duration_minutes")
        points = {format(Decimal(n.replace(",", ".")).normalize(), "f")
                  for n in re.findall(r"(?:not[ée]e?\s+sur|sur|/)\s*([0-9]{1,3}(?:[.,][0-9]{1,2})?)\b", lower)}
        if len(points) == 1:
            proposal["total_points"] = points.pop()
        elif points:
            conflicts.add("total_points")
        objectives = tuple(part.strip(" .") for part in re.split(r"[;\n,]", text)
                           if re.match(r"\s*(identifier|calculer|interpréter|interpreter|analyser)\b",
                                       part, re.IGNORECASE))
        if objectives:
            proposal["objectives"] = objectives
        validated = validated_values(proposal)
        explicit = validated_values(patch)
        for name, value in validated.items():
            if name in current and current[name] != value and name not in explicit:
                conflicts.add(name)
        result = dict(current)
        result.update(validated)
        result.update(explicit)
        conflicts.difference_update(explicit)
        if set(current) - set(FIELDS):
            raise ContextRejected()
        missing = tuple(name for name in FIELDS if name not in result or name in conflicts)
        return ContextUpdate(validated_values(result), missing, tuple(sorted(conflicts)),
                             tuple(validated))
