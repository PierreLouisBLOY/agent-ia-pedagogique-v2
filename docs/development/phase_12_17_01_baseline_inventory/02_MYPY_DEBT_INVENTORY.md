# Phase 12.17.1 — Inventaire de la dette mypy

## Deux traversées distinctes

La commande canonique du dépôt est propre, cache désactivé :

```text
.venv/Scripts/python.exe -m mypy backend --no-incremental --no-pretty --no-color-output --show-error-codes
Success: no issues found in 659 source files
```

La dette historique `33 erreurs / 15 fichiers` est néanmoins reproductible par la traversée import-driven documentée pendant V5.2.4 :

```text
.venv/Scripts/python.exe -m mypy --strict --explicit-package-bases --no-incremental --no-pretty --no-color-output --show-error-codes tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py tests/unit/test_pairwise_output_contract_v5_2_4.py
Found 33 errors in 15 files (checked 2 source files)
```

Il ne s'agit donc pas de 33 erreurs dans `backend`, mais de dette importée depuis les helpers de calibration et le support Anthropic situés sous `tests/`. Cette distinction de périmètre est elle-même un finding.

## Inventaire exhaustif

| # | Fichier:ligne | Code | Message condensé | Pattern | Cause probable |
| ---: | --- | --- | --- | --- | --- |
| 1 | `tests/providers/anthropic/transport.py:88` | `redundant-cast` | cast `str` redondant | cast obsolète | Annotation amont désormais précise. |
| 2 | `tests/providers/anthropic/scorer.py:198` | `union-attr` | `route` peut être `None` | narrowing absent | Le helper d'erreur est annoté `None`, pas `NoReturn`. |
| 3 | `tests/providers/anthropic/scorer.py:208` | `union-attr` | `model` peut être `None` | narrowing absent | Même cause que l'erreur 2. |
| 4 | `tests/providers/anthropic/scorer.py:215` | `arg-type` | `provider` optionnel transmis | narrowing absent | Même cause que l'erreur 2. |
| 5 | `tests/providers/anthropic/scorer.py:216` | `arg-type` | `model` optionnel transmis | narrowing absent | Même cause que l'erreur 2. |
| 6 | `tests/calibration/pedagogical/catalog.py:104` | `unused-ignore` | ignore inutilisé | suppression obsolète | Le narrowing du tuple de deux éléments est maintenant compris. |
| 7 | `tests/calibration/pedagogical/catalog.py:489` | `arg-type` | `tuple[str, ...]` vs tuple de 3 | cardinalité fixe | La compréhension perd l'information de longueur trois. |
| 8 | `tests/calibration/pedagogical/anchor_corpus_v2.py:681` | `arg-type` | `tuple[str, ...]` vs tuple de 3 | cardinalité fixe | Construction dynamique non raffinée. |
| 9 | `tests/calibration/pedagogical/anchor_corpus_v3.py:453` | `arg-type` | `tuple[str, ...]` vs tuple de 3 | cardinalité fixe | Construction dynamique non raffinée. |
| 10 | `tests/calibration/pedagogical/anchor_corpus_v3.py:946` | `assignment` | type de variable `item` incompatible | réemploi de variable | Deux boucles réemploient `item` avec des types distincts. |
| 11 | `tests/calibration/pedagogical/anchor_corpus_v3.py:948` | `attr-defined` | attribut `tier` absent | cascade de l'erreur 10 | Mypy conserve le type de la première boucle. |
| 12 | `tests/calibration/pedagogical/anchor_corpus_v3.py:949` | `attr-defined` | attribut `v2_content_fingerprint` absent | cascade de l'erreur 10 | Même cause. |
| 13 | `tests/calibration/pedagogical/anchor_corpus_v3.py:949` | `attr-defined` | attribut `v3_content_fingerprint` absent | cascade de l'erreur 10 | Même cause. |
| 14 | `tests/calibration/pedagogical/anchor_corpus_v3.py:950` | `attr-defined` | attribut `human_v2_label` absent | cascade de l'erreur 10 | Même cause. |
| 15 | `tests/calibration/pedagogical/anchor_corpus_v3.py:950` | `attr-defined` | attribut `reuse_allowed` absent | cascade de l'erreur 10 | Même cause. |
| 16 | `tests/calibration/pedagogical/anchor_corpus_v3.py:951` | `attr-defined` | attribut `reason` absent | cascade de l'erreur 10 | Même cause. |
| 17 | `tests/calibration/pedagogical/anchor_corpus_v4.py:459` | `arg-type` | `tuple[str, ...]` vs tuple de 3 | cardinalité fixe | Construction dynamique non raffinée. |
| 18 | `tests/calibration/pedagogical/call_plan.py:607` | `operator` | comparaison `Decimal | None` | narrowing absent | Helper d'erreur non annoté `NoReturn`. |
| 19 | `tests/calibration/pedagogical/call_plan.py:609` | `operator` | comparaison avec plafond optionnel | narrowing absent | Même cause que l'erreur 18. |
| 20 | `tests/calibration/pedagogical/protocol.py:190` | `arg-type` | `object` vs union Observation | union hétérogène | Le tuple `values` est inféré trop largement avant `zip`. |
| 21 | `tests/calibration/pedagogical/call_plan_v4_1.py:218` | `operator` | comparaison `Decimal | None` | narrowing absent | Duplication du pattern V4 initial. |
| 22 | `tests/calibration/pedagogical/call_plan_v4_1.py:220` | `operator` | comparaison avec plafond optionnel | narrowing absent | Même cause que l'erreur 21. |
| 23 | `tests/calibration/pedagogical/review_contract_v4_2.py:20` | `attr-defined` | `AnchorTier` non exporté explicitement | export implicite | Import transitoire depuis le module V4. |
| 24 | `tests/calibration/pedagogical/review_contract_v4_2.py:84` | `redundant-cast` | cast `str` redondant | cast obsolète | Annotation amont précise. |
| 25 | `tests/calibration/pedagogical/repair_tranche_v4_2.py:615` | `redundant-cast` | cast `Decimal` redondant | cast obsolète | Annotation amont précise. |
| 26 | `tests/calibration/pedagogical/semantic_integration_v5.py:536` | `redundant-cast` | cast `str` redondant | cast obsolète | Annotation amont précise. |
| 27 | `tests/calibration/pedagogical/semantic_integration_v5.py:985` | `redundant-cast` | cast `str` redondant | cast obsolète | Annotation amont précise. |
| 28 | `tests/calibration/pedagogical/semantic_integration_v5.py:1039` | `redundant-cast` | cast `str` redondant | cast obsolète | Annotation amont précise. |
| 29 | `tests/calibration/pedagogical/semantic_integration_v5.py:1084` | `redundant-cast` | cast `Decimal` redondant | cast obsolète | Annotation amont précise. |
| 30 | `tests/calibration/pedagogical/semantic_pilot_freeze_v5.py:192` | `redundant-cast` | cast mapping redondant | cast obsolète | Annotation amont précise. |
| 31 | `tests/calibration/pedagogical/semantic_mini_pilot_v5_1.py:674` | `redundant-cast` | cast mapping redondant | cast obsolète | Annotation amont précise. |
| 32 | `tests/calibration/pedagogical/semantic_gate_v5_2.py:489` | `redundant-cast` | cast mapping redondant | cast obsolète | Annotation amont précise. |
| 33 | `tests/calibration/pedagogical/semantic_gate_v5_2.py:738` | `assignment` | spec mini-pilot vs micro-canary | union de branches | Une variable locale reçoit deux dataclasses distinctes. |

## Regroupement

| Code mypy | Nombre |
| --- | ---: |
| `arg-type` | 7 |
| `assignment` | 2 |
| `attr-defined` | 7 |
| `operator` | 4 |
| `redundant-cast` | 10 |
| `union-attr` | 2 |
| `unused-ignore` | 1 |

Les clusters racines probables sont : narrowing fail-closed non exprimé à mypy, cardinalité de tuples, réemploi de variables locales entre versions, union d'identités V5.1/V5.2 et casts devenus obsolètes. Aucune correction n'est appliquée dans 12.17.1.
