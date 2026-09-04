# Phase 12.17.5B-B02 — Preuves de compatibilité de la migration 001

## Identité préservée

La ressource `database/migrations/001_document_sha256_check.sql` n'a pas été modifiée.

```text
EXPECTED_SHA256 = 5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
OBSERVED_SHA256 = 5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
RESULT = PASS
```

## Compatibilité fonctionnelle

| Preuve | Résultat |
|---|---|
| découverte de `001` dans le registre approuvé | PASS |
| provisionnement par l'ancien argument `Path` | PASS |
| provisionnement par registre explicite | PASS |
| application fraîche de `001` | PASS |
| rejeu de `001` sans nouvelle écriture de ledger | PASS |
| postcondition SHA du document | PASS |
| rejet d'une ressource `001` altérée | PASS |
| gate réelle B08 avec seed en lecture seule et runtime temporaire | PASS |

Le seed canonique a seulement servi de source authentifiée et read-only pour la gate B08. La copie migrée était temporaire ; aucun fichier SQLite utilisateur n'a été pris pour cible.
