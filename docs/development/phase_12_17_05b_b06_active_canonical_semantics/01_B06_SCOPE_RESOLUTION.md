# Phase 12.17.5B-B06 — Résolution de périmètre

Le lot est exécuté sous le titre canonique `Sémantique ACTIVE/CANONICAL`, sur
la baseline `576d6bd6dcf5082740c4192842b7c87ccbc1f246`, avec `DM-03 = OPTION_B`.
Les gates d'entrée B05 sont conformes et le seed est authentifié par le SHA-256
`38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`.

Le périmètre autorisé comprend le modèle Domain des deux dimensions, les ports
et DTO Application, les mappings SQLite, les projections READ-15 et OP-12, les
tests ciblés et le présent dossier de preuve. Sont hors périmètre : migration
ou backfill B06, endpoint HTTP, résolution de `ContextOrigin`, provider, fusion
`ACTIVE == CANONICAL`, suppression de `CANONICAL`, démarrage de B07 ou de
12.17.6.

Le seed n'est ouvert qu'en lecture seule. Les runtimes utilisés par les tests
sont des copies temporaires et supprimables. Aucun fichier SQLite, sidecar ou
résultat runtime n'entre dans Git.

```text
B06_ENTRY_GATE = READY
B06_CANONICAL_TITLE = Sémantique ACTIVE/CANONICAL
DM_03 = OPTION_B
ACTIVE_CANONICAL_MIGRATION_AUTHORIZED = FALSE
DATA_BACKFILL_AUTHORIZED = FALSE
COMMIT_STRATEGY = NONE_PENDING_EXPLICIT_CONSOLIDATION_REVIEW
```
