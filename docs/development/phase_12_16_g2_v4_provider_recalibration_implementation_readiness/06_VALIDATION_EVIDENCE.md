# 12.16-G2-V4 — Preuves finales de validation hors ligne

Date : 2026-08-31

## Validation globale finale

La suite complète a été exécutée avec les flags live et les credentials OpenAI/Anthropic supprimés de l'environnement du processus. Les tests SQLite réels ont reçu uniquement le chemin local de la base canonique en lecture. Le `basetemp` final était hors du dépôt.

```text
4445 passed, 3 skipped in 815.92s
```

Les trois skips sont les gates explicitement opt-in : recalibration pédagogique live, benchmark sémantique live et variante offline R1 non demandée.

Contrôles complémentaires :

```text
REAL_SQLITE_E2E_GATES = 22 passed in 534.94s
HISTORICAL_R2_R3_R4_DEBT = 106 passed in 57.82s
RUFF_FULL_REPOSITORY = PASS
MYPY_BACKEND = PASS (659 source files)
COMPILEALL_BACKEND_AND_TESTS = PASS
GIT_DIFF_CHECK = PASS
SOURCE_TREE_RUNTIME_DATABASE_FILE_COUNT = 0
GLOBAL_SUITE_RUN = PASS
PROVIDER_CALLS = 0
CREDENTIALS_RESOLVED = FALSE
TRANSPORT_CONSTRUCTED = FALSE
```

## Dette historique résolue

La réconciliation directe distingue désormais explicitement le formulaire corrigé `5748b0f2...42a6` des preuves pré-correction. Les sorties corrigées sont déterministes : rapport `872dd091...61d78`, résultat `23fce7f8...da92b`. Les artefacts historiques restent byte-stables : rapport `7f54427d...3947e`, résultat `deefcf80...85db`.

Les audits R2/R3/R4 utilisent maintenant une vue legacy gelée de 96 appels, checksum `997e814f...50ed`, au lieu d'importer la matrice courante mutable. La matrice V4 approuvée reste distincte : 102 appels, checksum `f159f200...6245e`.

Aucune preuve historique, donnée runtime, route fournisseur ou attestation propriétaire n'a été réécrite.
