"""Frozen Phase 12.16-F1 retrieval-quality corpus and deterministic metrics."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from backend.agent_runtime.agents.evidence import EvidenceAgent, RetrievalChannel
from backend.agent_runtime.contracts.common import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
)
from backend.agent_runtime.contracts.evidence import EvidenceRequest
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

CORPUS_VERSION = "12.16-f1-v1"
CORPUS_SHA256 = "f9ebd4330c1f4b5d06021b8a29d4d12db4cfaff05b535eec0ff86da4d842f238"
BENCHMARK_K_VALUES = (1, 3, 5)
BENCHMARK_CHANNELS = ("STRUCTURED", "LEXICAL", "COMBINED")


class PedagogicalLevel(StrEnum):
    PREMIERE_STMG = "PREMIERE_STMG"
    TERMINALE_STMG = "TERMINALE_STMG"
    BTS_CG_1 = "BTS_CG_1"
    BTS_CG_2 = "BTS_CG_2"


class RetrievalQueryClass(StrEnum):
    EXACT_LABEL = "A_EXACT_LABEL"
    LEXICAL_VARIANT = "B_LEXICAL_VARIANT"
    NORMALIZED_SURFACE = "C_NORMALIZED_SURFACE"
    SYNONYM_BUSINESS = "D_SYNONYM_BUSINESS"
    PEDAGOGICAL_PARAPHRASE = "E_PEDAGOGICAL_PARAPHRASE"
    CONCEPT_DESCRIPTION = "F_CONCEPT_DESCRIPTION"


class RetrievalMissCause(StrEnum):
    DATA_GAP = "DATA_GAP"
    ALIAS_GAP = "ALIAS_GAP"
    NORMALIZATION_GAP = "NORMALIZATION_GAP"
    LEXICAL_LIMITATION = "LEXICAL_LIMITATION"
    SEMANTIC_PARAPHRASE_GAP = "SEMANTIC_PARAPHRASE_GAP"
    RELATIONAL_GAP = "RELATIONAL_GAP"
    EXPECTATION_ERROR = "EXPECTATION_ERROR"


@dataclass(frozen=True, slots=True)
class RetrievalQualityCase:
    case_id: str
    level: PedagogicalLevel
    query_class: RetrievalQueryClass
    query_text: str
    expected_refs: tuple[str, ...]
    control_ref: str | None
    query_family: str
    notes: str
    miss_cause: RetrievalMissCause | None = None


def _family(
    *,
    slug: str,
    level: PedagogicalLevel,
    expected_ref: str,
    queries: tuple[str, str, str, str, str, str],
    semantic_wording_cause: RetrievalMissCause,
    description_cause: RetrievalMissCause,
    synonym_cause: RetrievalMissCause,
) -> tuple[RetrievalQualityCase, ...]:
    classes = tuple(RetrievalQueryClass)
    causes: tuple[RetrievalMissCause | None, ...] = (
        None,
        None,
        None,
        synonym_cause,
        semantic_wording_cause,
        description_cause,
    )
    control_case_id = f"RQ-{slug}-A"
    class_notes = (
        "Libellé canonique exact, contrôle positif fixé avant exécution.",
        "Variation lexicale légitime de surface.",
        "Surface normalisée sans enrichissement sémantique.",
        "Synonyme ou formulation métier courante.",
        "Question ou intention pédagogique mono-concept.",
        "Description mono-concept sans libellé canonique imposé.",
    )
    suffixes = ("A", "B", "C", "D", "E", "F")
    return tuple(
        RetrievalQualityCase(
            case_id=f"RQ-{slug}-{suffix}",
            level=level,
            query_class=query_class,
            query_text=query,
            expected_refs=(expected_ref,),
            control_ref=None if suffix == "A" else control_case_id,
            query_family=slug,
            notes=note,
            miss_cause=cause,
        )
        for suffix, query_class, query, note, cause in zip(
            suffixes, classes, queries, class_notes, causes, strict=True
        )
    )


RETRIEVAL_QUALITY_CASES = (
    *_family(
        slug="ACTION-COLLECTIVE",
        level=PedagogicalLevel.PREMIERE_STMG,
        expected_ref="notion:action-collective",
        queries=(
            "Action collective",
            "actions collectives",
            "action collective",
            "mobilisation coordonnée",
            "agir ensemble dans une organisation",
            "groupe de personnes poursuivant un objectif commun",
        ),
        synonym_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="SYSTEME-INFORMATION",
        level=PedagogicalLevel.PREMIERE_STMG,
        expected_ref="notion:systeme-dinformation",
        queries=(
            "Système d’information",
            "systèmes information",
            "systeme dinformation",
            "SI",
            "comment une organisation collecte et fait circuler ses informations",
            "ressources organisées pour collecter traiter stocker et diffuser information",
        ),
        synonym_cause=RetrievalMissCause.ALIAS_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="DONNEES-PERSONNELLES",
        level=PedagogicalLevel.PREMIERE_STMG,
        expected_ref="notion:donnees-personnelles",
        queries=(
            "Données personnelles",
            "donnée personnelle",
            "donnees personnelles",
            "informations nominatives",
            "informations concernant une personne identifiable",
            "information liée directement ou indirectement à une personne physique",
        ),
        synonym_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="DIAGNOSTIC-EXTERNE",
        level=PedagogicalLevel.TERMINALE_STMG,
        expected_ref="notion:diagnostic-externe",
        queries=(
            "Diagnostic externe",
            "diagnostics externes",
            "diagnostic externe",
            "opportunites menaces",
            "analyser les facteurs situés hors de organisation",
            "étude des opportunités et menaces de environnement",
        ),
        synonym_cause=RetrievalMissCause.ALIAS_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="DEMARCHE-MARKETING",
        level=PedagogicalLevel.TERMINALE_STMG,
        expected_ref="notion:demarche-marketing",
        queries=(
            "Démarche marketing",
            "démarches marketing",
            "demarche marketing",
            "approche marketing",
            "comprendre le marché avant de construire une offre",
            "processus qui analyse les besoins puis définit une offre",
        ),
        synonym_cause=RetrievalMissCause.ALIAS_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="MARCHE",
        level=PedagogicalLevel.TERMINALE_STMG,
        expected_ref="notion:marche",
        queries=(
            "Marché",
            "marchés",
            "marche",
            "rencontre entre offre et demande",
            "où se confrontent vendeurs et acheteurs",
            "mécanisme de confrontation entre offre et demande",
        ),
        synonym_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="BILAN",
        level=PedagogicalLevel.BTS_CG_1,
        expected_ref="notion:bilan",
        queries=(
            "Bilan",
            "bilan comptable",
            "bilan",
            "état patrimonial",
            "présenter le patrimoine de entreprise à une date",
            "état des actifs et passifs à la clôture",
        ),
        synonym_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="AMORTISSEMENTS",
        level=PedagogicalLevel.BTS_CG_1,
        expected_ref="notion:amortissements",
        queries=(
            "Amortissements",
            "amortissement",
            "amortissements",
            "dépréciation planifiée des immobilisations",
            "répartir le coût de actif sur sa durée utilisation",
            "constat comptable de consommation des avantages économiques de immobilisation",
        ),
        synonym_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="COUT-COMPLET",
        level=PedagogicalLevel.BTS_CG_2,
        expected_ref="notion:cout-complet",
        queries=(
            "Coût complet",
            "coûts complets",
            "cout complet",
            "méthode des centres analyse",
            "calculer toutes les charges supportées par un produit",
            "coût intégrant les charges directes et indirectes",
        ),
        synonym_cause=RetrievalMissCause.ALIAS_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
    *_family(
        slug="METHODE-ABC",
        level=PedagogicalLevel.BTS_CG_2,
        expected_ref="notion:methode-abc",
        queries=(
            "Méthode ABC",
            "ABC",
            "methode abc",
            "activity based costing",
            "imputer les coûts selon les activités consommées",
            "calcul des coûts fondé sur activités inducteurs et processus",
        ),
        synonym_cause=RetrievalMissCause.ALIAS_GAP,
        semantic_wording_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
        description_cause=RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP,
    ),
)


def corpus_sha256(cases: Iterable[RetrievalQualityCase] = RETRIEVAL_QUALITY_CASES) -> str:
    payload = [
        {
            "case_id": case.case_id,
            "control_ref": case.control_ref,
            "expected_refs": case.expected_refs,
            "level": case.level.value,
            "miss_cause": case.miss_cause.value if case.miss_cause else None,
            "notes": case.notes,
            "query_class": case.query_class.value,
            "query_family": case.query_family,
            "query_text": case.query_text,
        }
        for case in cases
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_retrieval_benchmark(
    agent: EvidenceAgent,
    *,
    seed_sha256: str,
    seed_size_bytes: int,
) -> dict[str, object]:
    outcomes: list[dict[str, object]] = []
    for index, case in enumerate(RETRIEVAL_QUALITY_CASES, start=1):
        retrieval = agent.search_evidence(request=_request(case, index))
        channel_refs = {
            result.channel.value: tuple(
                str(candidate.canonical_object_ref or candidate.source_ref)
                for candidate in result.candidates
            )
            for result in retrieval.channel_results
            if result.channel in (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL)
        }
        channel_refs["COMBINED"] = tuple(
            str(
                candidate.representative.canonical_object_ref
                or candidate.representative.source_ref
            )
            for candidate in retrieval.ranked_candidates
        )
        outcomes.append(
            {
                "case": case,
                "channels": {
                    channel: {
                        "candidate_count": len(channel_refs.get(channel, ())),
                        "rank": _first_expected_rank(
                            channel_refs.get(channel, ()), case.expected_refs
                        ),
                    }
                    for channel in BENCHMARK_CHANNELS
                },
            }
        )

    metrics = {
        "global": _metrics_by_channel(outcomes),
        "by_query_class": {
            query_class.value: _metrics_by_channel(
                item
                for item in outcomes
                if item["case"].query_class is query_class  # type: ignore[union-attr]
            )
            for query_class in RetrievalQueryClass
        },
        "by_level": {
            level.value: _metrics_by_channel(
                item
                for item in outcomes
                if item["case"].level is level  # type: ignore[union-attr]
            )
            for level in PedagogicalLevel
        },
    }
    exact_misses = [
        case.case_id
        for item in outcomes
        if (case := item["case"]).query_class is RetrievalQueryClass.EXACT_LABEL  # type: ignore[union-attr]
        and item["channels"]["COMBINED"]["rank"] is None  # type: ignore[index]
    ]
    semantic_cases = tuple(
        item
        for item in outcomes
        if item["case"].query_class  # type: ignore[union-attr]
        in {
            RetrievalQueryClass.SYNONYM_BUSINESS,
            RetrievalQueryClass.PEDAGOGICAL_PARAPHRASE,
            RetrievalQueryClass.CONCEPT_DESCRIPTION,
        }
    )
    misses = []
    for item in semantic_cases:
        case = item["case"]
        if item["channels"]["COMBINED"]["rank"] is not None:  # type: ignore[index]
            continue
        cause = case.miss_cause  # type: ignore[union-attr]
        if cause is None:
            raise AssertionError(f"missing cause for {case.case_id}")  # type: ignore[union-attr]
        misses.append(
            {
                "case_id": case.case_id,  # type: ignore[union-attr]
                "cause": cause.value,
                "control_ref": case.control_ref,  # type: ignore[union-attr]
                "level": case.level.value,  # type: ignore[union-attr]
                "lexical_rank": item["channels"]["LEXICAL"]["rank"],  # type: ignore[index]
            }
        )
    semantic_gap_misses = [
        miss
        for miss in misses
        if miss["cause"] == RetrievalMissCause.SEMANTIC_PARAPHRASE_GAP.value
    ]
    affected_levels = sorted({str(miss["level"]) for miss in semantic_gap_misses})
    controls_pass = not exact_misses
    material_semantic_gap = (
        len(semantic_gap_misses) >= 3
        and len(affected_levels) >= 2
        and controls_pass
    )
    semantic_gap_rate_percent = round(
        _rate(len(semantic_gap_misses), len(semantic_cases)) * 100,
        6,
    )
    return {
        "benchmark": "PHASE_12_16_F1_RETRIEVAL_BASELINE",
        "corpus": {
            "case_count": len(RETRIEVAL_QUALITY_CASES),
            "sha256": corpus_sha256(),
            "version": CORPUS_VERSION,
        },
        "decision": {
            "exact_label_gate": "PASS" if controls_pass else "BLOCKED",
            "f1_status": "PASS",
            "material_semantic_gap": material_semantic_gap,
            "next_step": "F2_READY" if material_semantic_gap else "G_READY",
            "provider_or_vector_runtime_added": False,
            "semantic_gap_affected_levels": affected_levels,
            "semantic_gap_miss_count": len(semantic_gap_misses),
            "semantic_gap_rate_percent": semantic_gap_rate_percent,
        },
        "exact_label_misses": exact_misses,
        "k_values": BENCHMARK_K_VALUES,
        "metrics": metrics,
        "miss_analysis": misses,
        "seed": {
            "sha256": seed_sha256,
            "size_bytes": seed_size_bytes,
        },
    }


def render_benchmark_report(report: Mapping[str, object]) -> bytes:
    return (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _request(case: RetrievalQualityCase, index: int) -> EvidenceRequest:
    timestamp = Instant(datetime(2026, 8, 28, 10, 0, tzinfo=UTC))
    return EvidenceRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id=f"retrieval-quality-{index:03d}",
            step_id=f"retrieval-quality-step-{index:03d}",
            parent_step_id=None,
            correlation_id=CorrelationId(f"retrieval-quality-corr-{index:03d}"),
            created_at=timestamp,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
            status=InvocationStatus.PLANNED,
        ),
        search_goal=case.query_text,
        scope={"level": case.level.value},
        source_policy={"kinds": ("canonical",)},
        filters={"active": True},
        required_authority=None,
        max_items=max(BENCHMARK_K_VALUES),
    )


def _first_expected_rank(refs: tuple[str, ...], expected_refs: tuple[str, ...]) -> int | None:
    expected = frozenset(expected_refs)
    return next((rank for rank, ref in enumerate(refs, start=1) if ref in expected), None)


def _metrics_by_channel(outcomes: Iterable[dict[str, object]]) -> dict[str, object]:
    materialized = tuple(outcomes)
    return {
        channel: _metrics(
            tuple(item["channels"][channel] for item in materialized)  # type: ignore[index]
        )
        for channel in BENCHMARK_CHANNELS
    }


def _metrics(values: tuple[dict[str, int | None], ...]) -> dict[str, object]:
    ranks = tuple(value["rank"] for value in values)
    return {
        "case_count": len(values),
        "mrr_at_5": _rate(
            sum(1 / rank for rank in ranks if rank is not None and rank <= 5),
            len(values),
        ),
        "recall_at_1": _rate(sum(rank == 1 for rank in ranks), len(values)),
        "recall_at_3": _rate(
            sum(rank is not None and rank <= 3 for rank in ranks), len(values)
        ),
        "recall_at_5": _rate(
            sum(rank is not None and rank <= 5 for rank in ranks), len(values)
        ),
        "zero_hit_rate": _rate(
            sum(value["candidate_count"] == 0 for value in values), len(values)
        ),
    }


def _rate(numerator: int | float, denominator: int) -> float:
    return round(float(numerator) / denominator, 6) if denominator else 0.0
