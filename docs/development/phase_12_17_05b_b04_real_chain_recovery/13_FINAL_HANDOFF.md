# Phase 12.17.5B-B04 — Handoff final

```text
PHASE_12_17_05B_B04 = PASS
B04_USER_RUNTIME_WRITE_AUTHORIZED = FALSE
VALIDATION_TARGET = CONTROLLED_RUNTIME_COPY
B02_B03_CARRY_FORWARD_VERIFIED = TRUE
SEED_PATH = OWNER_OVERRIDE_REDACTED
RUNTIME_PATH = %LOCALAPPDATA%/ProjetV2/runtime/base_pedagogique_v2.runtime.sqlite
SEED_SHA256_PRE_POST = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134 -> SAME
USER_RUNTIME_SHA256_PRE_POST = de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1 -> SAME
BACKUP_CREATED_VERIFIED = TRUE
TEMP_RUNTIME_ARTIFACTS_CLEANED = TRUE
MIGRATIONS_BEFORE_MISSING_APPLIED_AFTER = 001 / 002 / 002 / 001,002
USER_RUNTIME_002_APPLIED = FALSE
REPLAY_IDEMPOTENCE = PASS_WITH_TEMP_SIDECAR_MATERIALIZATION
FIVE_INVARIANTS = 5/5 PASS
CHECK_SHA256_RETAINED = TRUE
ROW_PRESERVATION = PASS 15 -> 15
INTEGRITY_QUICK_FK = ok / ok / 0
RECOVERY_REHEARSAL = PASS
SEED_SIDECARS_PRE_POST = IDENTICAL
USER_RUNTIME_SIDECARS_PRE_POST = IDENTICAL
DM_01_STATUS = CONFORMANT
DM_02_STATUS = NOT_YET_EXECUTED
DM_03_STATUS = NOT_YET_EXECUTED
CONTEXT_ORIGIN = UNKNOWN
TARGETED_TESTS = 63/63 PASS
ARCHITECTURE_GUARDS = 17/17 PASS
ACTIVE_MYPY = 0/42
BACKEND_MYPY = 0/671
PROVIDER_CALLS = 0
SECRETS = 0
COMMIT = NONE
PUSH = NONE
B05_ENTRY_GATE = READY
B05_CANONICAL_TITLE = Contrat resource_ref
```

## Écarts explicités

1. Le chemin runtime logique est redirigé par l'isolation MSIX de l'hôte ; les
   deux représentations convergent après résolution et ne désignent pas deux
   runtimes.
2. Le replay crée un WAL vide et un SHM sur la copie temporaire. Le fichier
   principal, le ledger, le schéma et les données restent identiques.
3. Deux invocations préparatoires ont été corrigées avant exécution utile
   (racine d'import Python puis nom du fichier `001`). Elles ont échoué avant
   tout appel au runner et n'ont touché ni seed ni runtime utilisateur.

Le lot B04 est clos. B05 et la Phase 12.17.6 ne sont pas commencés.
