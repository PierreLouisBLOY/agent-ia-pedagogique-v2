"""Declared outbound-only double. Never imported by normal composition."""
from collections.abc import Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain


class P0GenerationDouble:
    def __init__(self, *, allowed=True, failure=None):
        self.allowed, self.failure = allowed, failure
        self.requests = []

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        return self.allowed

    def generate(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        self.requests.append(as_plain(request))
        if self.failure:
            raise RuntimeError("PRIVATE_TRANSPORT_DETAIL_MUST_NOT_LEAK")
        data = as_plain(request)
        context = data["context"]
        course = context["resource_type"] == "COURSE"
        options = ["Option A", "Option B"] if context["question_mode"] in {"QCM", "QUIZ"} else []
        return {"contract_id": "R6-P0-PRODUCTION-1.0", **{key: data[key] for key in
            ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage")},
            "title": "Harnais P0 — résultat synthétique déclaré",
            "sections": [{"section_id": "S01", "heading": "Application guidée",
                          "text": "Projection de test des références admises ; aucune autorité pédagogique."}],
            "questions": [] if course else [{"question_id": "Q01", "prompt": "Justifiez votre méthode.", "options": options}],
            "corrections": [] if course else [{"question_id": "Q01", "expected_answer": "Option A" if options else "TEACHER_ONLY_SENTINEL",
                                                "rationale": "TEACHER_ONLY_SENTINEL — correction synthétique du harnais."}],
            "marking": [{"question_id": "Q01", "points": f'{context["total_points"]:.2f}',
                          "criteria": ["Méthode explicitée"]}] if context["resource_type"] == "ASSESSMENT" else [],
            "limitations": ["CANDIDATE", "HARNESS_SYNTHETIC_OUTPUT — aucun fournisseur réel ni acceptation pédagogique"]}
