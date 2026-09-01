# Phase 12.16-G2-V4.1 — Preuves de validation

## Tests ciblés

Commande hors ligne couvrant matrice, runner, scorer, Review, canaries, budget et clôture V4 :

`166 passed, 1 skipped in 27.16s`

Le skip est exclusivement la gate live opt-in historique, fermée en l'absence d'autorisation live.

## Suite globale et qualité

- Suite globale post-liaison : `4460 passed, 3 skipped in 839.43s`.
- Ruff : `PASS`.
- mypy : `PASS — Success: no issues found in 659 source files`.
- compileall : `PASS` sur `backend`, `tests/calibration/pedagogical` et `tests/providers/anthropic`.
- git diff --check : `PASS`.

Les trois skips correspondent exclusivement aux gates opt-in : calibration fournisseur, benchmark sémantique live et benchmark sémantique offline R1.

Un premier passage sandboxé avait exposé l'accès refusé au seed canonique `G:` et le contrôle byte-exact du scorer historique. Le scorer a été remis byte-exact (`3be22f3a...a76119`). Lors de la validation post-liaison, le test d'hygiène a ensuite détecté des bases de test résiduelles sous `.tmp`; les seuls répertoires pytest concernés ont été supprimés après vérification de leur chemin. La suite finale a été relancée avec le seed en lecture, les gates et credentials fournisseurs absents du processus, et `basetemp` hors du dépôt ; elle passe intégralement.

## Sécurité hors ligne

- Provider calls : `0`.
- Credentials resolved : `0`.
- Transports constructed : `0`.
- Bases runtime créées dans l'arbre source : `0`.
- Secrets détectés dans le diff/les artefacts : `0`.
- Commit : `NONE`.
- Push : `NONE`.
