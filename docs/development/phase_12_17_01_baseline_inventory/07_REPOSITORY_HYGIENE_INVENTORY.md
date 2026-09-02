# Phase 12.17.1 — Inventaire d'hygiène repository

## Git et fichiers runtime

- Baseline initiale : worktree propre, `0` fichier non suivi.
- Aucun fichier sous `artifacts/`, aucune base SQLite/DB et aucun bytecode ne sont suivis.
- `.gitignore` couvre environnements, caches, secrets, bases et sidecars, logs, runtime, exports, artifacts et répertoires temporaires.
- `.gitattributes` impose LF et porte une exception `blank-at-eof` limitée au dossier immutable V5 integration.

## Manifests

- Manifests détectés : `36`.
- Entrées vérifiées : `421`.
- Erreur de format : `0`.
- Référence manquante : `0`.
- Hash divergent : `0`.

La vérification résout d'abord les chemins repo-relative, puis les chemins relatifs au dossier du manifest. Aucun manifest n'a été modifié.

## EOF et espaces

Sur `1606` fichiers texte suivis inspectés :

- espaces finaux : `0` fichier;
- absence de LF final : `1` fichier, `docs/development/PHASE_12_15_G_CANONICAL_SUITE_REPORT.json`;
- ligne vide finale : `7` fichiers, tous sous `phase_12_16_g2_v5_semantic_validation_integration_offline/` et couverts par l'exception explicite de `.gitattributes`.

Les sept fichiers protégés sont inventoriés comme dette acceptée historique potentielle; ils ne sont pas requalifiés ni normalisés ici.

## Duplications documentaires

Deux documents ont un contenu octet-identique :

- `phase_12_16_g2_v5_2_2_live_pairwise_execution/06_PHASE_12_16_CLOSURE_READINESS.md`;
- `phase_12_16_g2_v5_2_3_live_pairwise_execution/06_PHASE_12_16_CLOSURE_READINESS.md`.

Cette duplication peut être une preuve versionnée légitime. Elle reste `CANDIDATE` et aucune suppression n'est proposée avant l'audit documentaire ciblé.

## TODO et fichiers locaux

La recherche `TODO/FIXME/HACK/XXX` ne trouve aucun marqueur de dette exécutable. L'unique occurrence est la chaîne `"todo"` traitée comme placeholder invalide dans `human_review_reconciliation.py`.

Les volumes locaux ignorés sont importants : `747` fichiers artifacts et `3064` fichiers temporaires. Trois anciens dossiers pytest sous `.tmp` ne sont pas lisibles par l'utilisateur courant. Ils ne contaminent pas Git, mais constituent un candidat de nettoyage local séparé et potentiellement destructif; aucune action n'a été effectuée.

Les `378` documents Markdown, `98` baselines top-level et `36` dossiers de phase justifient un audit futur de hiérarchie canonique et d'orphelins, sans présumer qu'un historique versionné est supprimable.
