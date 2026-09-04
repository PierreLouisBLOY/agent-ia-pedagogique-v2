# Phase 12.17.5B-B07 — Résolution du scope

Le plan gelé B01 fixe sans ambiguïté le titre canonique
`Ré-audit et décision de gate`.

Le scope B07 est exclusivement documentaire et de validation : ré-audit des
56 liens, des cinq blockers 12.17.5, du schéma/migrations, de READ-15, de la
complétude du handoff API, des tests et de la gate 12.17.6. Il n'autorise aucun
nouveau comportement, endpoint, contrat métier, migration, backfill, provider
ou modification de runtime utilisateur.

Les fichiers attendus sont les treize artefacts B07 et leur manifest. Les
gates de test sont celles d'`ENVIRONMENT.md`, complétées par les ciblages
B02→B06, le contrôle des 56 liens, le lint, les deux graphes mypy, compileall,
le diff et les secrets.

La policy SQLite est lecture seule sur le seed et réutilisation des preuves
validées; les tests peuvent employer des copies temporaires. La policy Git
prévoit des artefacts de clôture, mais n'autorise pas explicitement la
consolidation du carry-forward B02→B06.

```text
PHASE_12_17_05B_B07 = PASS
B07_CANONICAL_TITLE = Ré-audit et décision de gate
B07_SCOPE_AMBIGUITY = NONE
B07_SQLITE_POLICY = READ_ONLY_SEED_TEMPORARY_TEST_COPIES_ONLY
B07_COMMIT_POLICY = NO_CONSOLIDATION_AUTHORIZED
12_17_6_ENTRY_CONDITION = ALL_BLOCKERS_CLOSED_AND_VALIDATIONS_GREEN
```
