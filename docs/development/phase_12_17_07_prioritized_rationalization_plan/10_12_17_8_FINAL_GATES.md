# Phase 12.17.8 — Gates finales planifiées

Chaque gate est fail-closed : absence de preuve, test non exécuté, résultat tronqué ou dérive d'identité vaut `FAIL`. Les 16 gates doivent passer dans le même état Git final.

| # | Gate | Critère PASS | Preuve obligatoire |
|---:|---|---|---|
| 1 | OPEN_P0 | `OPEN_P0 = 0` | registre canonique recalculé |
| 2 | P1 bloquants | `OPEN_BLOCKING_P1 = 0` | CF-REPO-001 fermé et commit de provenance vérifié |
| 3 | Active mypy | 0 diagnostic sur le graphe actif documenté | commande, version mypy et liste de 42 fichiers ou successeur explicite |
| 4 | Backend mypy | 0 diagnostic sur tout `backend/` | sortie complète et nombre de fichiers; baseline précédente 674 |
| 5 | Suite globale | 0 failure | `pytest` global hors racines ignorées, pass/skip/fail et durée |
| 6 | Seed inchangé | SHA256 `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`, PRE=POST | accès read-only exact et snapshots sidecars |
| 7 | Runtime valide | provisionnement/migrations/recherche sur runtimes temporaires PASS | fresh/existing/recovery et invariant `001`/`002` |
| 8 | Secrets | `SECRET_FINDINGS_COUNT = 0` | scan borné sans affichage de valeur, Git + artefacts candidats |
| 9 | Fournisseurs | `PROVIDER_CALLS = 0`, aucune autorisation live active, aucun credential résolu | test doubles, config fail-closed, registre d'appels vide |
| 10 | HTTP local-browser | contrat loopback-only PASS; aucun serveur ajouté | refus non-loopback/wildcard/debug/docs et absence de framework/routes |
| 11 | Observabilité minimale | 12/12 signaux PASS, confidentialité PASS, sink failure-isolated | matrice, rotation/rétention/flush et payload-exclusion tests |
| 12 | Dépendances | reproductibilité PASS ou exception exacte approuvée | deux clean installs hash-required, lock drift; sinon attestation d'exception bornée |
| 13 | Hygiène dépôt | quatre gaps fermés, aucun DB/secret/output runtime suivi, repository walks déterministes | `git check-ignore`, inventaire tracked/untracked/ignored et guards |
| 14 | Politique worktree finale | aucun staged, aucune modification tracked, aucun untracked canonique; ignored local autorisé et inventorié | `git status --porcelain=v1 -z` classifié exhaustivement |
| 15 | Disposition 126 | `126/126` conformes à l'option propriétaire, suivis comme preuve après minimisation éventuelle | matrice chemin→commit, manifestes et équivalence des cinq minimisations |
| 16 | Disposition 05C | `11/11` preuves 12.17.5C versionnées et manifestes valides | matrice de provenance 05C et commit final |

Contrôles transverses complémentaires, sans augmenter le nombre de gates : ruff PASS, compileall PASS, architecture guards PASS, historical freeze `40/40`, dette mypy historique exactement `15/10`, drifts connus `7/7 UNCHANGED`, nouveau drift historique `0`, manifestes B01-B07 valides, diff revu et aucune modification des frontières sans ADR.

```text
FINAL_GLOBAL_GATES_COUNT = 16
PASS_REQUIRED = 16/16
PARTIAL_ACCEPTED = FALSE
AUTO_MERGE = FALSE
```

Une exception de dépendance n'est admissible qu'au titre du critère 12, avec l'artefact, la plateforme, le risque, la mesure compensatoire et l'approbation owner exacts. Elle ne peut masquer aucun autre échec.
