"""Explicit documentary reassembly of authenticated P0 text, without generation.

The caller supplies exact offsets, not a similarity rule. Each dossier is
partitioned into its introduction and consecutive question spans. No source
character is discarded except whitespace between spans. Teacher data and
references are inherited byte for byte; authority is not inherited.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


@dataclass(frozen=True, slots=True)
class DossierPartition:
    section_id: str
    questions: tuple[tuple[str, int], ...]


class ReassembleP0Candidate:
    def execute(self, parent: P0Production, *, expected_sha256: str,
                version_ref: str, partitions: tuple[DossierPartition, ...]) -> P0Production:
        if parent.sha256 != expected_sha256:
            raise ValueError("P0_ASSEMBLY_SOURCE_IDENTITY")
        if not partitions or len({p.section_id for p in partitions}) != len(partitions):
            raise ValueError("P0_ASSEMBLY_PARTITIONS")
        data = parent.mutable_copy()
        sections = items(parent.data["sections"], 16)
        questions = items(parent.data["questions"], 60)
        by_section = {p.section_id: p for p in partitions}
        if not set(by_section) <= {str(s["section_id"]) for s in sections}:
            raise ValueError("P0_ASSEMBLY_PARTITIONS")
        selected: list[str] = []
        new_sections: list[Mapping[str, object]] = []
        new_questions: list[dict[str, object]] = []
        originals = {str(q["question_id"]): q for q in questions}
        for section in sections:
            partition = by_section.get(str(section["section_id"]))
            if partition is None:
                new_sections.append(section)
                continue
            text = str(section["text"])
            spans = partition.questions
            offsets = [start for _, start in spans]
            if (not spans or any(type(start) is not int or not 0 < start < len(text)
                                 for start in offsets)
                    or offsets != sorted(set(offsets))):
                raise ValueError("P0_ASSEMBLY_OFFSETS")
            intro = text[:offsets[0]].strip()
            if not intro:
                raise ValueError("P0_ASSEMBLY_INTRODUCTION")
            new_sections.append({"section_id": "S_BEFORE_" + spans[0][0],
                                 "heading": section["heading"], "text": intro})
            for index, (question_id, start) in enumerate(spans):
                if question_id not in originals:
                    raise ValueError("P0_ASSEMBLY_QUESTION_LINK")
                stop = offsets[index + 1] if index + 1 < len(offsets) else len(text)
                prompt = text[start:stop].strip()
                if not prompt:
                    raise ValueError("P0_ASSEMBLY_OFFSETS")
                selected.append(question_id)
                new_questions.append({**originals[question_id], "prompt": prompt})
        if selected != [str(q["question_id"]) for q in questions]:
            raise ValueError("P0_ASSEMBLY_QUESTION_ORDER")
        data["sections"] = new_sections
        data["questions"] = new_questions
        data["version_ref"] = version_ref
        data["lineage"] = {**object_data(data["lineage"]), "parent_version_ref": parent.version_ref}
        data["limitations"] = [*cast(tuple[str, ...], parent.data["limitations"]),
            "Réassemblage documentaire explicite ; aucune génération, validation humaine ou promotion."]
        successor = P0Production(data)
        # The DTO rejects a reused identity and changed context. This command
        # additionally leaves all original metadata and teacher fields untouched.
        return successor
