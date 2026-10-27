"""Bounded French intention proposals, with no authority, effect or provider call."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping, Sequence

from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ContextRejected,
    text_value,
)

INTENTION_CONTRACT = "P0-INTENTION-PROPOSAL-1.0"
_FAMILIES = (
    ("COURSE", r"\b(?:cours|course)\b"),
    ("EXERCISE", r"\b(?:exercice[s]?|exercise[s]?)\b"),
    ("OPEN_QUESTIONS", r"\bquestions?\s+ouvertes?\b"),
    ("QCM", r"\bqcm\b|\bquestions?\s+a\s+choix\s+multiples?\b"),
    ("QUIZ", r"\bquiz\b"),
    ("ASSESSMENT", r"\b(?:evaluation|controle|assessment)\b"),
)
_LEVELS = (
    ("FIRST_STMG", r"\b(?:premiere|1ere|1re)\s+(?:en\s+)?stmg\b"),
    ("FINAL_STMG", r"\bterminale\s+(?:en\s+)?stmg\b"),
)
_CAPACITY = r"identifier|distinguer|decrire|expliquer|presenter|justifier|caracteriser|calculer|interpreter|analyser|comparer|determiner|evaluer"


def _fold(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(c))


def _choose(proposal: dict[str, object], ambiguities: list[dict[str, object]],
            field: str, candidates: Sequence[object]) -> None:
    unique = list(dict.fromkeys(candidates))
    if len(unique) == 1:
        proposal[field] = unique[0]
    elif unique:
        ambiguities.append({"field": field, "candidates": unique})


def _topics(text: str) -> list[str]:
    result = []
    for match in re.finditer(r"\b(?:sur|concernant)\s+|à\s+propos\s+de\s+", text, re.I):
        tail = text[match.end():]
        # Bound the subject to its explicit phrase; constraints and capacities
        # remain separate. There is deliberately no closed list of notion labels.
        phrase = re.split(
            r"[;,\n]|\s+(?:pour|avec|difficulté|difficulte|not[ée]e?|niveau|en\s+(?:première|premiere|terminale|bts))\b"
            r"|\s+(?:de\s+)?\d{1,3}\s*(?:minutes?|min|heures?|h|points?)\b",
            tail, maxsplit=1, flags=re.I)[0].strip(" .:")
        if phrase and len(phrase) <= 120 and not phrase.isdigit() and phrase not in result:
            result.append(phrase)
        if len(result) >= 8:
            break
    return result


def _objectives(text: str) -> list[str]:
    result = []
    for part in re.split(r"[;\n,]", text):
        normalized = _fold(part).lstrip()
        if re.match(r"^(?:" + _CAPACITY + r")\b", normalized):
            objective = part.strip(" .")
            if objective and len(objective) <= 500 and objective not in result:
                result.append(objective)
        if len(result) >= 8:
            break
    return result


class ProposeP0Intention:
    def execute(self, body: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(body, Mapping) or set(body) != {"command_id", "intention"}:
            raise ValueError("P0_INTENTION_FIELDS")
        command = body["command_id"]
        if not isinstance(command, str) or re.fullmatch(r"[0-9a-f]{32}", command) is None:
            raise ValueError("P0_INTENTION_COMMAND_ID")
        try:
            text = text_value(body["intention"], 4000, 12 * 1024)
        except ContextRejected:
            raise ValueError("P0_INTENTION_TEXT") from None
        normalized = _fold(text)
        proposal: dict[str, object] = {"family": None, "resource_type": None,
            "question_mode": None, "level": None, "topics": _topics(text),
            "objectives": _objectives(text), "difficulty": None,
            "duration_minutes": None, "total_points": None, "language": "fr",
            "audience": None, "teaching_hint": None}
        ambiguities: list[dict[str, object]] = []
        _choose(proposal, ambiguities, "family",
                [family for family, pattern in _FAMILIES if re.search(pattern, normalized)])
        family = proposal["family"]
        if family in {"OPEN_QUESTIONS", "QCM", "QUIZ"}:
            proposal.update(resource_type="QUESTION_SET", question_mode=family)
        elif family is not None:
            proposal["resource_type"] = family
        levels: list[object] = [level for level, pattern in _LEVELS if re.search(pattern, normalized)]
        if re.search(r"\bbts\s+cg\b", normalized):
            if re.search(r"\b(?:premiere|1ere|1re)\s+annee\b|\bannee\s*1\b", normalized):
                levels.append("BTS_CG_YEAR_1")
            if re.search(r"\b(?:deuxieme|seconde|2eme|2e)\s+annee\b|\bannee\s*2\b", normalized):
                levels.append("BTS_CG_YEAR_2")
        _choose(proposal, ambiguities, "level", levels)
        _choose(proposal, ambiguities, "difficulty", [difficulty for difficulty, pattern in (
            ("INTRODUCTORY", r"\b(?:introductif|introductive|introduction|debutant|decouverte)\b"),
            ("STANDARD", r"\bstandard\b"), ("ADVANCED", r"\b(?:avancee?|approfondi|approfondie)\b"),
        ) if re.search(pattern, normalized)])
        durations: list[object] = [int(h) * 60 + int(m) for h, m in
            re.findall(r"\b(\d{1,2})\s*h\s*([0-5]\d)\b", normalized)]
        durations += [int(n) * (60 if unit.startswith("h") else 1) for n, unit in
            re.findall(r"\b(\d{1,3})\s*(heures?|h|min(?:utes?)?)\b", normalized)]
        if any(not 1 <= int(str(value)) <= 480 for value in durations):
            raise ValueError("P0_INTENTION_DURATION")
        _choose(proposal, ambiguities, "duration_minutes", durations)
        points: list[object] = [int(n) for n in re.findall(
            r"(?:notee?\s+sur|bareme\s+(?:de|sur)|/)\s*(\d{1,3})\b", normalized)]
        points += [int(n) for n in re.findall(r"\b(\d{1,3})\s*points?\b", normalized)]
        if any(not 1 <= int(str(value)) <= 200 for value in points):
            raise ValueError("P0_INTENTION_POINTS")
        _choose(proposal, ambiguities, "total_points", points)
        student = re.search(r"\beleves?\b|\betudiants?\b", normalized) is not None
        teacher = re.search(r"\bprofesseurs?\b|\benseignants?\b", normalized) is not None
        if student and teacher and not re.search(r"\bou\b", normalized):
            proposal["audience"] = "student_and_teacher"
        else:
            _choose(proposal, ambiguities, "audience",
                    (["student"] if student else []) + (["teacher"] if teacher else []))
        compound = r"\bmsdgn\b|management,?\s+sciences\s+de\s+gestion\s+et\s+numerique"
        teaching: list[object] = ["Management, sciences de gestion et numérique"] if re.search(compound, normalized) else []
        other_teaching = re.sub(compound, " ", normalized)
        teaching += [label for label, pattern in (
            ("Management", r"\bmanagement\b"),
            ("Sciences de gestion et numérique", r"\bsgn\b|\bsciences\s+de\s+gestion\s+et\s+numerique\b"),
            ("Comptabilité et gestion", r"\bcomptabilite\s+et\s+gestion\b"),
        ) if re.search(pattern, other_teaching)]
        _choose(proposal, ambiguities, "teaching_hint", teaching)
        missing = [field for field in ("family", "level", "topics", "objectives", "difficulty")
                   if not proposal[field]]
        if family == "ASSESSMENT":
            missing += [field for field in ("duration_minutes", "total_points") if proposal[field] is None]
        else:
            if proposal["duration_minutes"] is not None:
                missing.append("duration_constraint_application")
            if proposal["total_points"] is not None:
                missing.append("points_constraint_application")
        unsupported = None
        action = re.match(r"^(?:(?:je (?:veux|voudrais|souhaite)|peux[- ]tu|merci de)\s+)?"
                          r"(modifier|modifie|corriger|corrige|exporter|exporte|relire|revoir|review)\b", normalized)
        if action:
            verb = action[1]
            unsupported = "EXPORT" if verb.startswith("export") else "REVIEW" if verb in {"relire", "revoir", "review"} else "MODIFY"
        return {"contract_id": INTENTION_CONTRACT,
            "state": "OUT_OF_SCOPE" if unsupported else "CLARIFICATION_REQUIRED" if missing or ambiguities else "CONTEXT_PROPOSED",
            "command_id": command, "intention_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "proposal": proposal, "extracted_fields": [field for field, value in proposal.items()
                if field not in {"language", "resource_type", "question_mode"} and value],
            "missing_fields": missing, "ambiguities": ambiguities,
            "institutional_selection": "EXACT_CATALOG_CONFIRMATION_REQUIRED",
            "unsupported_operation": unsupported, "implementation": "DETERMINISTIC_APPLICATION_PROPOSAL",
            "confirmation_required": True, "provider_attempts": 0, "authority": "NONE"}
