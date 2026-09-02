# Phase 12.17.1 — Baseline repository

## Point de contrôle

| Élément | Valeur observée |
| --- | --- |
| HEAD | `3156092091bf755f1d542ef2d36ada2a34f3c210` |
| Branche | `phase12/12-16-provider-model-calibration` |
| Sujet du commit | `docs: close phase 12.16 calibration` |
| Worktree avant audit | `CLEAN` |
| Fichiers suivis | `1622` |
| Fichiers non suivis avant audit | `0` |
| Phase 12.16 | `CLOSED / PASS` |
| Manifest de clôture 12.16 | `5cca614f33a7105ba91f4a1c6098336e2bbabfc09f054c7ad774730288d788c4` |
| Appels fournisseur autorisés | `FALSE` |

Le manifest interne du bundle de kickoff est valide. Le SHA-256 de l'archive reçue est `9f3aabbd1b23f3179408e3dd5f6e772077bf35124be1d66ed98e11ca29964ec5`.

## Topologie et volumes

- `backend/` : `659` fichiers Python.
- `tests/` : `412` fichiers Python, dont `323` fichiers nommés `test_*.py`.
- `evaluation_harness/` : `30` fichiers Python.
- `backend/modules/` : `13` modules métier, `344` fichiers Python, dont `339` `__init__.py` et `5` fichiers d'implémentation.
- Les cinq fichiers d'implémentation métier appartiennent tous à `resource_library`; les douze autres modules sont des squelettes structurels.
- Couches déclarées sous `backend/modules/` : `104` fichiers Domain, `120` Application, `65` Contracts et `41` Ports. Cette volumétrie inclut massivement des packages `__init__.py` d'une ligne.
- `backend/adapters/inbound/` : un seul fichier non-`__init__`, le bridge Application de `resource_library`.
- `backend/adapters/inbound/api/` : uniquement `__init__.py`; aucun endpoint HTTP `/api/v2` matérialisé.

Modules déclarés : `analysis_simulation`, `audit_traceability`, `documents_provenance`, `knowledge_reference`, `lifecycle_promotion`, `materialization_export`, `pedagogical_context`, `pedagogical_design`, `quality_evaluation`, `resource_library`, `transformation_assembly`, `validation_control`, `work_orchestration`.

## Tests et contrôles disponibles

| Famille | Fichiers `test_*.py` |
| --- | ---: |
| Unit | 155 |
| Integration | 70 |
| Architecture | 85 |
| Non-functional | 4 |
| Calibration | 8 |
| Providers | 1 |

Les répertoires E2E, contracts et adapters contiennent des supports mais aucun fichier directement nommé `test_*.py`. La configuration `pyproject.toml` impose Python 3.12, pytest, Ruff et mypy strict sur `backend`. L'environnement observé utilise Python `3.12.13`, mypy `2.3.1`, Ruff `0.16.4` et pytest `9.1.1`.

Les commandes documentées dans `docs/development/ENVIRONMENT.md` sont `compileall backend`, `pytest -q`, `ruff check .` et `mypy backend`. Aucun script de lancement ou entry point de production n'est déclaré; les fonctions `main` détectées appartiennent aux helpers historiques de calibration sous `tests/`.

## État des sorties locales

- Fichiers runtime/artifacts suivis : `0`.
- SQLite/DB suivies : `0`.
- Bytecode Python suivi : `0`.
- Fichiers ignorés sous `artifacts/` : `747`.
- Fichiers ignorés sous `.tmp/`, `tmp/` et `temp/` : `3064`.
- L'inventaire de `.tmp` remonte trois avertissements d'accès refusé sur d'anciens répertoires pytest; aucune suppression n'a été tentée.

À la fin du lot, les seuls nouveaux fichiers doivent se trouver sous `docs/development/phase_12_17_01_baseline_inventory/`. Aucun fichier déjà suivi ne doit être modifié.
