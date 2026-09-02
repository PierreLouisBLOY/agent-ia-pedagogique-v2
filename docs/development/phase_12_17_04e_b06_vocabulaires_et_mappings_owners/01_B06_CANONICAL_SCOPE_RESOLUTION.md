# Phase 12.17.4E-B06 — Résolution du scope canonique

```text
B06_CANONICAL_TITLE = Vocabulaires et mappings owners
B06_ROOT_CHANGES = RC-06
B06_COMMIT_POLICY = SEPARATE_COMMIT
```

Le plan assigne à B06 la création des types dans leurs bounded contexts puis la
traduction SQLite explicite des dix familles. Les fichiers confirmés sont les
modules Domain/Application propriétaires, le mapper outbound SQLite, les stores
qui le consomment et les tests de conformance.

Sont hors scope : chemins et variables B07, cycle seed/runtime et sidecars B08,
legacy/API B09, toute migration, toute modification du seed, tout appel provider
et toute réouverture de 12.16.

Les diagnostics attendus ne ferment aucune dette mypy historique : B06 prévient
uniquement de nouveaux littéraux non typés. Les gates sont 10/10 familles,
round-trips/transitions, refus des valeurs inconnues, absence de type métier dans
le shared kernel et confinement SQL aux adapters.
