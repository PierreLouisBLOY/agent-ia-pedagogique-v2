# Phase 12.17.5B-B02 — Preuves de tests ciblés

## Exécutions ciblées

```text
SYNTHETIC_UNIT_AND_ARCHITECTURE = 39/39 PASS
B08_REAL_SEED_GATE = 1/1 PASS
TARGETED_TOTAL = 40/40 PASS
```

Les 39 tests couvrent le cycle seed/runtime existant, le nouveau registre multi-version et les gardes d'architecture. La gate B08 supplémentaire utilise le seed canonique en lecture seule et une base runtime temporaire.

Une première exécution combinée a détecté les bases de test laissées sous `.tmp` par son propre `basetemp`. Ces seuls artefacts temporaires ont été supprimés, puis la matrice a été rejouée avec un `basetemp` système hors du dépôt : `39/39 PASS`. Il ne s'agissait pas d'un écart fonctionnel du runner.

## Matrice multi-version

- registre `001` canonique ;
- tri déterministe de plusieurs migrations ;
- rejet des doublons, identifiants invalides et trous d'ordre/version ;
- rejet des écarts de checksum de ressource ou de ledger ;
- idempotence du rejeu ;
- rollback et arrêt de séquence ;
- rejet d'un historique troué ou inconnu ;
- refus d'une migration non applicable ;
- compatibilité du provisionnement avec un registre explicite.

## Accès SQLite

```text
SEED_SQLITE_ACCESS = TRUE_READ_ONLY
SEED_SQLITE_MODIFIED = FALSE
USER_RUNTIME_ACCESSED = FALSE
USER_RUNTIME_MODIFIED = FALSE
TEMP_TEST_DATABASES_ACCESSED = TRUE
TEMP_TEST_DATABASES_MODIFIED = TRUE
```
