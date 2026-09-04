# Phase 12.17.5A — Final handoff

## Résultat

```text
PHASE_12_17_05A_BLOCKING_REMEDIATION_DESIGN = PASS
BASELINE_COMMIT = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
SEED_SHA256 = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134
MIGRATION_001_SCHEMA_REGRESSION = CONFIRMED
EXACT_LOST_INVARIANTS_COUNT = 5
MIGRATION_001_RETROACTIVE_EDIT = FORBIDDEN
CORRECTIVE_MIGRATION_RECOMMENDED_IDENTIFIER = 002
DM_01_OPTIONS = 3
DM_01_RECOMMENDATION = OPTION_A
DM_01_CONFIDENCE = HIGH
DM_02_OPTIONS = 4
DM_02_RECOMMENDATION = OPTION_A
DM_02_CONFIDENCE = MEDIUM
DM_03_OPTIONS = 4
DM_03_RECOMMENDATION = OPTION_B
DM_03_CONFIDENCE = MEDIUM
CONTEXT_ORIGIN = UNKNOWN
CONTEXT_ORIGIN_MIGRATION_AUTHORIZED = FALSE
BLOCKERS_MAPPED_COUNT = 5
BLOCKERS_REQUIRING_OWNER_DECISION_COUNT = 4
OWNER_DECISIONS_REQUIRED = 3
PROPOSED_12_17_05B_BATCHES = 7
CODE_OR_RULES_MODIFIED = 0
SQLITE_WRITE_OPERATIONS = 0
PROVIDER_CALLS = 0
COMMIT = NONE
PUSH = NONE
12_17_05B_ENTRY_GATE = BLOCKED_OWNER_DECISIONS
PHASE_12_17_6_STARTED = FALSE
```

## Synthèse des preuves

- Le DDL de reconstruction de `001` omet exactement un CHECK et quatre defaults du seed. La contrainte SHA-256 ajoutée par `001` est, elle, présente.
- `001` est appliquée, journalisée et hashée. Sa modification rétroactive est incompatible avec le ledger et les preuves antérieures.
- Le runner actuel est limité à la version globale `001` et à un unique chemin. Il doit être généralisé avant qu'une vraie migration `002` puisse exister.
- Les références observées ont des longueurs 10, 16, 44 et 49. Les 1 399 valeurs seed/runtime sont des références de longueur 44 sans caractères URL dangereux. La recommandation 128 caractères est fondée sur compatibilité observée et précédent technique, mais reste soumise à l'owner.
- Seed et runtime contiennent 1 399 ressources `ACTIVE` et aucune `CANONICAL`. Cela ne suffit pas à établir une relation sémantique entre les deux valeurs.
- Aucune preuve nouvelle ne résout `ContextOrigin`.

## Décisions attendues

Le propriétaire doit compléter `05_OWNER_DECISION_REGISTER.json` pour :

1. `DM-01` — stratégie de correction des cinq invariants ;
2. `DM-02` — borne et syntaxe de `resource_ref` ;
3. `DM-03` — relation sémantique `ACTIVE/CANONICAL`.

Les recommandations ne valent pas approbation automatique. Tant que ces choix ne sont pas attestés, 12.17.5B reste bloquée. Le présent lot ne démarre ni 12.17.5B ni 12.17.6.

## Écarts et limites

- Aucun écart aux gates d'entrée n'a été détecté.
- La régression `001` est un écart confirmé du runtime par rapport au seed; elle reste ouverte après ce lot de design.
- L'absence de support multi-migrations dans le runner est une dette technique préalable non comptée comme sixième finding : elle fait partie du mécanisme de résolution de `DMAPI-001/002/009`.
- Les décisions `DM-02` et `DM-03` ne disposent pas d'une autorité externe suffisante pour être auto-sélectionnées.
