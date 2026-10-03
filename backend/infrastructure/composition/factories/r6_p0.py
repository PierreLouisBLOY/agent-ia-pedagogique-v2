"""R6 P0 composition through the authenticated local Application search boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.exact_source_sqlite import (
    SQLiteExactResourceEvidenceAdapter,
)
from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    _application_searcher,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0_PROVENANCE_LABEL
from backend.modules.resource_library.application.dto.input.exact_resource_evidence import (
    ExactResourceEvidenceRequest,
)
from backend.modules.resource_library.application.dto.output.exact_resource_evidence import (
    ExactResourceEvidenceView,
)
from backend.modules.resource_library.application.queries.get_exact_resource_evidence import (
    GetExactResourceEvidenceQuery,
)
from backend.modules.resource_library.domain.value_objects import ResourceRef


@dataclass(frozen=True, slots=True)
class ExactQuestionBinding:
    question_id: str
    position: int
    points: float
    prompt_sha256: str
    correction_id: str
    correction_sha256: str


@dataclass(frozen=True, slots=True)
class ExactSourceBinding:
    scenarios: tuple[str, ...]
    resource_ref: str
    resource_version_ref: str
    resource_type: str
    canonical_title: str
    identity_status: str
    lifecycle_status: str
    validation_status: str
    body_sha256: str
    body_bytes: int
    questions: tuple[ExactQuestionBinding, ...]


R6_EXACT_SOURCE_BINDINGS = (
    ExactSourceBinding(
        ("R6-S01",),
        "revmax260921g:exercise:d6ac1f74b244ef7c7911fc60",
        "revmax260921g:exercise_version:d6ac1f74b244ef7c7911fc60",
        "EXERCISE", "Cas — Organisation — 2", "ACTIVE", "REVIEW", "NEEDS_REVIEW",
        "906469873b17ebf9edff6a9b5c11f91054a5b8e7c43deb5ed4053f0ca3eabdca", 640,
        (ExactQuestionBinding(
            "revmax260921g:question:d6ac1f74b244ef7c7911fc60", 1, 4.0,
            "59fcba9b42375dd740b8cf6fc822d03d0078e1cb30c586d1eb17b5fad3c6d9a7",
            "revmax260921g:correction:d6ac1f74b244ef7c7911fc60",
            "921fef39dee316a70463cd9675e1654188cfd8c1502b87c89b8fba8ba3321845",
        ),),
    ),
    ExactSourceBinding(
        ("R6-S02",),
        "revmax260921g:exercise:5d0e0227f109ff9fcf506c15",
        "revmax260921g:exercise_version:5d0e0227f109ff9fcf506c15",
        "EXERCISE", "Cas — Performance — 2", "ACTIVE", "REVIEW", "NEEDS_REVIEW",
        "efb8f2216dd045e6ac56b15702bb810a244cf3d4ed4bed9d7413c57eb13bc15b", 532,
        (ExactQuestionBinding(
            "revmax260921g:question:5d0e0227f109ff9fcf506c15", 1, 4.0,
            "181b9a674a986f39614a55ed507ee809a1b442c6f96f0722bf11dfd879fb5be1",
            "revmax260921g:correction:5d0e0227f109ff9fcf506c15",
            "5eed0b6c0fe598d1aba4a9d4ce6f6ce15c12fc1cba6d6db06e5f4da4b035e6f7",
        ),),
    ),
    ExactSourceBinding(
        ("R6-S03",),
        "revmax260921:exercise:fdd9c49a23bb1cf836bc764b",
        "revmax260921:exercise_version:fdd9c49a23bb1cf836bc764b",
        "EXERCISE", "Cas — Management stratégique — 2", "ACTIVE", "REVIEW", "NEEDS_REVIEW",
        "96343538d68a0d1857f85a6e60141a83973be14adbc450bcaa8e76fa25df20e9", 547,
        (ExactQuestionBinding(
            "revmax260921:question:fdd9c49a23bb1cf836bc764b", 1, 4.0,
            "2f5a580a9201afda9c9c556e032ca1305a86cb146b3499d5baa9b620e519bf41",
            "revmax260921:correction:fdd9c49a23bb1cf836bc764b",
            "dadc89cc86e43a646f46e5fbf2a055828e472ace460142c45141d70ee1091217",
        ),),
    ),
    ExactSourceBinding(
        ("R6-S04",),
        "revmax260921g:exercise:daf745c59bd24f75512cbc7f",
        "revmax260921g:exercise_version:daf745c59bd24f75512cbc7f",
        "EXERCISE", "Cas — Performance globale — 2", "ACTIVE", "REVIEW", "NEEDS_REVIEW",
        "da5e44353608d87558483224c1320b58f1fd812a77baa83140febe2a0f391884", 519,
        (ExactQuestionBinding(
            "revmax260921g:question:daf745c59bd24f75512cbc7f", 1, 4.0,
            "685bae7c48cd475bb840c3b436eea1444d5696c0c818d190224d53279fa96da9",
            "revmax260921g:correction:daf745c59bd24f75512cbc7f",
            "3f5de0714a409fe221838063df313f036c58beaeab240404c28445964c31e340",
        ),),
    ),
    ExactSourceBinding(
        ("R6-S05", "R6-S07"),
        "revmax260921:exercise:6785b115e78c9f4bece895b8",
        "revmax260921:exercise_version:6785b115e78c9f4bece895b8",
        "EXERCISE", "Cas — Lettrage — 2", "ACTIVE", "REVIEW", "NEEDS_REVIEW",
        "be63f14dab1d4cbfeef196f2f24ca2f61f5ce127e0f11f86ab87ed00cfed69c6", 547,
        (ExactQuestionBinding(
            "revmax260921:question:6785b115e78c9f4bece895b8", 1, 4.0,
            "65b4b8fa242762ce0340364eb0b3d50511d164d25caa681128249c7ab3bbe530",
            "revmax260921:correction:6785b115e78c9f4bece895b8",
            "3e854c9158936c80ce40711efb863a7df9fe685a7dda12ea0c876dc0b52abb81",
        ),),
    ),
    ExactSourceBinding(
        ("R6-S06",),
        "revint260920:resource:ee0f10a68b6572bdeea986ff",
        "revint260920:version:8d94f3a815145012122c1e4e",
        "EXERCISE", "Deux preuves d’un même solde", "ACTIVE", "REVIEW", "PENDING",
        "827310bb792ace27439636281a523edd002ecbbd96f4a629a5362adc116efc5d", 386,
        (
            ExactQuestionBinding(
                "revint260920:question:8d94f3a815145012122c1e4e", 1, 3.0,
                "d13e1bc1a6555cf7f2deb860d6b2e50bfa02754ff4e61d0adb496d25c912a887",
                "revint260920:correction:f31184ab44e8f4f9ff7a1e05",
                "f2081eb87910036fd825c11d108e2a34e7f55cf48890b4233a23e7addee44a45",
            ),
            ExactQuestionBinding(
                "revint260920:question:c55ae1a97abe99820043b499", 2, 2.0,
                "004ca5bc83c65327c57abd3b559959853ccf2f62227b510fb800a1ca387624da",
                "revint260920:correction:7765ea358d325307e44639cf",
                "9733786aad5afcdad66a05cdd169362ed688cca8990c51fae0060e987722cbfd",
            ),
        ),
    ),
)

_BINDINGS = {
    (binding.resource_ref, binding.resource_version_ref): binding
    for binding in R6_EXACT_SOURCE_BINDINGS
}


def load_p0_reference(
    target: Read15RuntimeTarget,
    *,
    query: str,
    passage_ref: str,
    correlation_id: str,
) -> dict[str, object]:
    """Return one exact, bounded reference projection; never a database handle or path."""

    target.validate()
    response = _application_searcher(target).get(query, 20, correlation_id)
    if response.status != 200:
        raise ValueError("R6_REFERENCE_SEARCH_FAILED")
    payload = object_data(response.payload, {"data", "meta"})
    data = object_data(payload["data"], {"items", "window_full", "more_admitted_in_window"})
    raw_items = data["items"]
    if not isinstance(raw_items, (tuple, list)):
        raise ValueError("R6_REFERENCE_SEARCH_FAILED")
    matches = [object_data(item) for item in raw_items if object_data(item).get("passage_ref") == passage_ref]
    if len(matches) != 1:
        raise ValueError("R6_REFERENCE_NOT_FOUND")
    item = matches[0]
    excerpt = item["excerpt"]
    if not isinstance(excerpt, str) or not excerpt:
        raise ValueError("R6_REFERENCE_EMPTY")
    version = item["version_or_checksum"]
    if not isinstance(version, str) or not version:
        raise ValueError("R6_REFERENCE_UNVERSIONED")
    evidence_hex = hashlib.sha256(passage_ref.encode("utf-8")).hexdigest()[:32]
    target.validate()
    return {
        "reference": {
            "evidence_id": "evidence:" + evidence_hex,
            "source_ref": item["object_ref"],
            "locator": passage_ref,
            "checksum_or_version": version,
            "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "provenance_label": P0_PROVENANCE_LABEL,
        },
        "excerpt": excerpt,
        "object_kind": item["object_kind"],
        "provider_calls": 0,
        "count_calls": 0,
        "credential_resolved": 0,
    }


def load_p0_exact_reference(
    target: Read15RuntimeTarget,
    *,
    resource_ref: str,
    resource_version_ref: str,
) -> dict[str, object]:
    """Materialize one allowlisted exact source through the internal M03 query."""

    binding = _BINDINGS.get((resource_ref, resource_version_ref))
    if binding is None:
        raise ValueError("R6_SOURCE_NOT_ALLOWLISTED")
    target.validate()
    connection = connect_sqlite(
        target.runtime_path, readonly=True, allowed_root=target.data_root
    )
    source = SQLiteExactResourceEvidenceAdapter(connection)
    try:
        view = GetExactResourceEvidenceQuery(source).execute(
            ExactResourceEvidenceRequest(ResourceRef(resource_ref), resource_version_ref)
        )
    finally:
        source.close()
    target.validate()
    _authenticate_exact_source(binding, view)
    evidence = view.evidence_text()
    evidence_hex = hashlib.sha256(
        f"{resource_ref}\n{resource_version_ref}".encode()
    ).hexdigest()[:32]
    return {
        "reference": {
            "evidence_id": "evidence:" + evidence_hex,
            "source_ref": resource_ref,
            "locator": resource_version_ref,
            "checksum_or_version": view.body_sha256,
            "excerpt_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
            "provenance_label": P0_PROVENANCE_LABEL,
        },
        "evidence": evidence,
        "exact_source": view.as_dict(),
        "scenarios": binding.scenarios,
        "provider_calls": 0,
        "count_calls": 0,
        "credential_resolved": 0,
    }


def _authenticate_exact_source(
    binding: ExactSourceBinding, view: ExactResourceEvidenceView
) -> None:
    if view.resource_ref.value != binding.resource_ref:
        raise ValueError("R6_RESOURCE_NOT_FOUND")
    if view.resource_version_ref != binding.resource_version_ref:
        raise ValueError("R6_RESOURCE_VERSION_MISMATCH")
    if view.body_sha256 != binding.body_sha256 or len(view.body.encode("utf-8")) != binding.body_bytes:
        raise ValueError("R6_RESOURCE_BODY_HASH_MISMATCH")
    actual_identity = (
        view.resource_type,
        view.canonical_title,
        view.identity_status,
        view.resource_lifecycle_status,
        view.resource_validation_status,
    )
    expected_identity = (
        binding.resource_type,
        binding.canonical_title,
        binding.identity_status,
        binding.lifecycle_status,
        binding.validation_status,
    )
    if actual_identity != expected_identity or len(view.questions) != len(binding.questions):
        raise ValueError("R6_RESOURCE_SHAPE_INVALID")
    for expected, actual in zip(binding.questions, view.questions, strict=True):
        if (
            actual.question_id,
            actual.position,
            actual.points,
            actual.correction_id,
        ) != (
            expected.question_id,
            expected.position,
            expected.points,
            expected.correction_id,
        ):
            raise ValueError("R6_RESOURCE_SHAPE_INVALID")
        if actual.prompt_sha256 != expected.prompt_sha256:
            raise ValueError("R6_QUESTION_HASH_MISMATCH")
        if actual.correction_sha256 != expected.correction_sha256:
            raise ValueError("R6_CORRECTION_HASH_MISMATCH")
