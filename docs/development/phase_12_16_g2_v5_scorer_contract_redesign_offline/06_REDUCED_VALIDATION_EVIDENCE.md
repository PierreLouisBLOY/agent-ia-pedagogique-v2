# Phase 12.16-G2-V5 — Preuves de validation réduite

## Tests ciblés

Commande :

```text
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .tmp/pytest-v5-scorer-redesign-reduced tests/unit/test_pedagogical_calibration_v5.py tests/unit/test_anthropic_evaluation_scorer.py tests/integration/test_anthropic_score_evaluator_integration.py tests/unit/test_pedagogical_calibration_call_plan.py tests/unit/test_pedagogical_calibration_v4_2.py tests/architecture/test_openai_review_anthropic_scorer_fitness.py tests/calibration/pedagogical/test_anchor_corpus_v4.py
```

Résultat : `84 passed in 17.98s`.

Couverture ciblée :

- scorer schema ;
- sémantique 0–4 et normalisation exacte ;
- monotonie synthétique ;
- saturation et niveaux intermédiaires ;
- parser evidence-first ;
- contradiction et defect coverage ;
- pairwise A/B/TIE ;
- rejet des ties matériels et conflits ;
- blinding anchors ;
- intégrité du corpus V4 ;
- agrégation des métriques ;
- live fail-closed ;
- non-régression des contrats Scorer/plan V4 ciblés.

## Ruff

```text
.\.venv\Scripts\python.exe -m ruff check tests/calibration/pedagogical/scorer_contract_v5.py tests/calibration/pedagogical/offline_calibration_v5.py tests/unit/test_pedagogical_calibration_v5.py
```

Résultat : `All checks passed!`.

## Mypy ciblé

```text
.\.venv\Scripts\python.exe -m mypy --strict --explicit-package-bases --follow-imports=skip tests/calibration/pedagogical/scorer_contract_v5.py tests/calibration/pedagogical/offline_calibration_v5.py tests/unit/test_pedagogical_calibration_v5.py
```

Résultat : `Success: no issues found in 3 source files`.

`--follow-imports=skip` limite le contrôle aux modules modifiés, conformément à la validation réduite. Une exécution exploratoire avec suivi complet des imports a retrouvé `13` erreurs mypy historiques dans cinq fichiers V2–V4 non modifiés (`catalog.py`, `anchor_corpus_v2.py`, `anchor_corpus_v3.py`, `anchor_corpus_v4.py`, `protocol.py`). Elles ne sont pas introduites par V5 et ne sont pas corrigées silencieusement dans ce lot.

## Compileall

```text
.\.venv\Scripts\python.exe -m compileall -q tests/calibration/pedagogical/scorer_contract_v5.py tests/calibration/pedagogical/offline_calibration_v5.py tests/unit/test_pedagogical_calibration_v5.py
```

Résultat : `PASS`.

## Contrôles finaux

- `git diff --check` : `PASS`.
- HEAD préservé : `a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b`.
- Contrôle whitespace des neuf livrables : inclus dans la vérification finale du manifest.
- Vérification SHA-256 du manifest : incluse dans la vérification finale du manifest.
- Suite globale : `NOT_RUN`, conformément au prompt.

## Réseau et secrets

- `PROVIDER_CALLS = 0`
- `OPENAI_CALLS = 0`
- `ANTHROPIC_CALLS = 0`
- `CREDENTIAL_RESOLUTION = 0`
- `TRANSPORT_INVOCATIONS = 0`
- `RETRY = 0`
- `RERUN = 0`
