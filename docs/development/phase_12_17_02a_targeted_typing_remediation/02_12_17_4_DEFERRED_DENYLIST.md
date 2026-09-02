# Phase 12.17.2A — Denylist différée vers 12.17.4

## Freeze autoritatif initial

Les quatorze diagnostics ci-dessous proviennent directement de la disposition 12.17.2 et n'ont pas été corrigés intentionnellement.

| Error ID | Fichier | Raison du defer | Findings liés |
| --- | --- | --- | --- |
| `MYPY-002` | `tests/providers/anthropic/scorer.py` | Contrat de contrôle de flux et placement du provider tooling. | `TYP-002`, `ARC-003` |
| `MYPY-003` | `tests/providers/anthropic/scorer.py` | Même racine d'affinement optionnel provider. | `TYP-002`, `ARC-003` |
| `MYPY-004` | `tests/providers/anthropic/scorer.py` | Même racine d'affinement optionnel provider. | `TYP-002`, `ARC-003` |
| `MYPY-005` | `tests/providers/anthropic/scorer.py` | Même racine d'affinement optionnel provider. | `TYP-002`, `ARC-003` |
| `MYPY-007` | `tests/calibration/pedagogical/catalog.py` | Builder de cardinalité trois tiers à rationaliser. | `TYP-003`, `ARC-002` |
| `MYPY-008` | `tests/calibration/pedagogical/anchor_corpus_v2.py` | Même contrat répliqué dans un corpus versionné. | `TYP-003`, `ARC-002` |
| `MYPY-009` | `tests/calibration/pedagogical/anchor_corpus_v3.py` | Même contrat répliqué dans un corpus versionné. | `TYP-003`, `ARC-002` |
| `MYPY-017` | `tests/calibration/pedagogical/anchor_corpus_v4.py` | Même contrat répliqué dans un corpus versionné. | `TYP-003`, `ARC-002` |
| `MYPY-018` | `tests/calibration/pedagogical/call_plan.py` | Garde budgétaire dupliquée à consolider. | `TYP-005`, `ARC-002` |
| `MYPY-019` | `tests/calibration/pedagogical/call_plan.py` | Même racine d'affinement du plafond optionnel. | `TYP-005`, `ARC-002` |
| `MYPY-021` | `tests/calibration/pedagogical/call_plan_v4_1.py` | Variante historique de la garde budgétaire. | `TYP-005`, `ARC-002` |
| `MYPY-022` | `tests/calibration/pedagogical/call_plan_v4_1.py` | Même racine d'affinement du plafond optionnel. | `TYP-005`, `ARC-002` |
| `MYPY-023` | `tests/calibration/pedagogical/review_contract_v4_2.py` | Re-export implicite d'un type canonique. | `ARC-002`, `BUS-002` |
| `MYPY-033` | `tests/calibration/pedagogical/semantic_gate_v5_2.py` | Deux specs versionnées partagent une locale sans contrat commun. | `TYP-008`, `ARC-002` |

`INITIAL_12_17_4_DENYLIST_COUNT = 14`

## Exception découverte pendant la remédiation

| Error ID | Fichier | Raison du defer | Findings liés |
| --- | --- | --- | --- |
| `MYPY-001` | `tests/providers/anthropic/transport.py` | Les octets du fichier participent au bundle `_ANTHROPIC_CONTRACT_PATHS`; retirer le cast modifie les call-specs et déclenche `MATRIX_MISMATCH`. Une correction sûre exige une décision d'identité/placement. | `TYP-007`, `ARC-003` |

`FINAL_12_17_4_DENYLIST_COUNT = 15`

Le fix essayé pour `MYPY-001` a été annulé intégralement. Aucun des quinze diagnostics de cette denylist n'est intentionnellement corrigé dans le diff final.
