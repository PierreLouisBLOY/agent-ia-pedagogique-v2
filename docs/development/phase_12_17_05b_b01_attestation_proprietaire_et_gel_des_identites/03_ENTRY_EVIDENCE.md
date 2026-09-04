# Phase 12.17.5B-B01 — Preuves d'entrée

## Gates et bindings

```text
ENTRY_HEAD = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
EXPECTED_HEAD = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
HEAD_BINDING = PASS
PHASE_12_17_05A_BLOCKING_REMEDIATION_DESIGN = PASS
OWNER_DECISION_RESOLUTION_12_17_05A = APPROVED
OWNER_DECISION_RESOLUTION_APPLIED = TRUE
OWNER_DECISIONS_RESOLVED = 3/3
DECISION_REGISTER_SHA256 = f987ce8a601275630bf2ec0298eb2c868d38411b3fad88d6e44082e3102551d1
OWNER_ATTESTATION_SHA256 = 224c2de87e75ce7c1aa50df246a9d7aa0b76edb053e91bfca6ff86a90d939b1e
SEED_SHA256_EXPECTED = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134
SEED_SHA256_OBSERVED = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134
SEED_BINDING = PASS
12_17_05B_ENTRY_GATE = READY
```

Le chemin seed a été résolu à partir de l'override propriétaire B07/B08. Son chemin absolu reste volontairement absent de Git. Seuls les métadonnées filesystem et le SHA-256 ont été lus; aucune connexion SQLite n'a été ouverte.

## Snapshot seed PRE

| Fichier | Présent | Taille | SHA-256 |
|---|---:|---:|---|
| principal | oui | 105 553 920 | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` |
| WAL | oui | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| SHM | oui | 32 768 | `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` |
| journal | non | — | — |

## Snapshot Git initial

```text
TRACKED_MODIFICATIONS_PRE = 0
PREEXISTING_UNTRACKED_ITEMS = PRESENT_AND_PRESERVED
BRANCH = phase12/12-16-provider-model-calibration
```

Les éléments non suivis préexistants comprennent l'ADR et le guard de calibration ainsi que les répertoires documentaires 12.17.3 à 12.17.5A. Ils sont hors scope, non modifiés et exclus de tout staging.

## Gates baseline exécutées avant artefacts B01

```text
TARGETED_SQLITE_LIFECYCLE_TESTS_PRE = 15/15 PASS
ARCHITECTURE_GUARDS_PRE = 4/4 PASS
ACTIVE_MYPY_PRE = 0/42
BACKEND_MYPY_PRE = 0/671
RUFF_PRE = PASS
COMPILEALL_PRE = PASS
HISTORICAL_FREEZE_PRE = 40/40 PASS
KNOWN_PREEXISTING_DRIFTS = 7/7
NEW_HISTORICAL_DRIFT_PRE = 0
```
