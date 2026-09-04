# Phase 12.17.3B — Owner decision worksheet

## Résumé compact

| ID | Recommendation | Confidence | External evidence | Blocks |
|---|---|---|---|---|
| `OD-01` | `OPTION_A` | MEDIUM | Phase 1/2 corpus missing | `OD-03`, `OD-07`, 12.17.4 |
| `OD-02` | `OPTION_A` | HIGH | Legacy trace incomplete | Governance closure, 12.17.4 |
| `OD-05` | `OPTION_A` | HIGH | `SQLITE = MISSING` | `OD-06`, `OD-07 OPTION_C`, data-model closure, 12.17.4 |
| `OD-08` | `OPTION_A` | HIGH | None | Durable calibration disposition, 12.17.4 |
| `OD-03` | `OPTION_A` | HIGH | Depends on `OD-01` | Non-resource API, lifecycle ownership, 12.17.4 |
| `OD-06` | `OPTION_A` | HIGH | `SQLITE = MISSING` | Vocabulary/data alignment, 12.17.4 |
| `OD-07` | `OPTION_A` | MEDIUM | Required only for option C; currently `MISSING` | READ-15 scope, 12.17.4 |
| `OD-04` | `OPTION_A` | HIGH | None for Resource-only A | `/api/v2` scope, 12.17.4 |

## Lignes d’attestation à remplir

Valeurs admises : `APPROVE_RECOMMENDATION`, `OPTION_A`, `OPTION_B`, `OPTION_C`, `DEFER`.

```text
OD-01 = ...
OD-02 = ...
OD-05 = ...
OD-08 = ...
OD-03 = ...
OD-06 = ...
OD-07 = ...
OD-04 = ...
```

Pour reprendre l’ordre numérique dans une attestation machine :

```text
OD_01_CHOICE = ...
OD_02_CHOICE = ...
OD_03_CHOICE = ...
OD_04_CHOICE = ...
OD_05_CHOICE = ...
OD_06_CHOICE = ...
OD_07_CHOICE = ...
OD_08_CHOICE = ...

OWNER_ATTESTATION = APPROVED
OWNER_NAME_OR_ROLE = ...
OWNER_ATTESTED_AT_UTC = ...
```

## Règles de résolution

- `APPROVE_RECOMMENDATION` se résout vers `OPTION_A` pour le registre SHA-256 `43985ca2cffc4979d59b32466654d541f9084465b7f06b5e00bf81be33cad8f4` uniquement.
- Une valeur absente ou inconnue laisse la décision `UNRESOLVED`.
- `DEFER` reste bloquant sauf déclaration explicite retirant la décision du scope 12.17.4.
- `OD-06 OPTION_A/B` nécessite `OD-05 OPTION_A/C` et la preuve externe avant alignement.
- `OD-07 OPTION_C` nécessite `OD-05 OPTION_A/C` et la preuve externe.
- `OD-04 OPTION_B` nécessite `OD-03 OPTION_A/B` et l’implémentation Application préalable.
- Le choix d’une option n’autorise ni code, ni migration, ni provider, ni commit/push.

## État courant

```text
OWNER_CHOICES_RECORDED = 0/8
EXTERNAL_SCHEMA_EVIDENCE = MISSING
PHASE_12_17_4_RATIONALIZATION_DESIGN_GATE = BLOCKED_OWNER_DECISIONS
```
