# Phase 12.17.7B — Binding de l'attestation propriétaire

## Attestation liée

L'attestation est constituée des valeurs fournies explicitement par le propriétaire, complétées par le timestamp transmis dans le message suivant. Aucun champ n'est inféré.

```text
OWNER_DECISION_RESOLUTION_12_17_07 = APPROVED

BASELINE_COMMIT = e2c43184a272491371b73131170db488cf3157d6
PHASE_12_17_07_MANIFEST_SHA256 = 937644fb779b6b860e7d677a3b17c1065feabbb7723e48017fc0b74a1893db8b
OWNER_DECISION_SOURCE_SHA256 = 3a0b957e69de662b89e3cb9bea47a2b56f6cd27f20e733858392d21210fdfbce
OWNER_DECISION_PACKET_MANIFEST_SHA256 = 00cdce8cf4a230bbe3e5c39a56c7f19a1039b00a7d7488cef1f2cdb657012945

REPO_EVIDENCE_DECISION = OPTION_A_MINIMIZE_FIVE_AND_CONSOLIDATE_165
REPO_OPTION_LABEL_LEGACY_COUNT = 165
REPO_EVIDENCE_EFFECTIVE_INVENTORY = 172
REPO_INVENTORY_REBOUND = APPROVED
REPO_EXECUTION_TARGET_COUNT = 172

OBSERVABILITY_DECISION = OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S

OWNER_NAME_OR_ROLE = PROJECT_OWNER
OWNER_ATTESTATION = APPROVED
OWNER_ATTESTATION_TIMESTAMP = 2026-09-04T18:50:04+02:00
```

## Validation du binding

| Contrôle | Attendu | Observé | Verdict |
|---|---|---|---|
| HEAD | `e2c43184a272491371b73131170db488cf3157d6` | identique | PASS |
| Manifest 12.17.7 | `937644fb…1893db8b` | identique | PASS |
| Source décision | `3a0b957e…10fdfbce` | identique | PASS |
| Manifest paquet 12.17.7A | `00cdce8c…57012945` | identique | PASS |
| Option REPO | Option A exacte | identique | PASS |
| Count legacy/effectif/target | `165/172/172` | identique | PASS |
| Option observabilité | OBS-A exacte | identique | PASS |
| Rôle et attestation | `PROJECT_OWNER / APPROVED` | identique | PASS |
| Timestamp | ISO-8601 avec fuseau | `2026-09-04T18:50:04+02:00` | PASS |

## Portée

Les deux décisions sont liées, mais non appliquées. Cette attestation autorise la préparation de l'entrée 12.17.8 selon les options choisies; elle n'autorise ni minimisation dans le présent lot, ni staging/commit/push, ni suppression, ni provider, ni écriture SQLite seed/utilisateur. B01 nécessite toujours son propre contrôle d'entrée et son allowlist exacte.

`OWNER_DECISIONS_RESOLVED = 2/2`
