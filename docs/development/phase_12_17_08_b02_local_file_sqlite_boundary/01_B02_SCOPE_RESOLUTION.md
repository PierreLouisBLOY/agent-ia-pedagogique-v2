# Phase 12.17.8-B02 — Résolution du périmètre

```text
PHASE = 12.17.8-B02
CANONICAL_TITLE = Frontière locale fichiers et SQLite
ENTRY_HEAD = d20428d2c3060546a2c40fc59f0e8b7026be707f
B01 = PASS
B02_ENTRY_GATE = READY
SOURCE_BUNDLE_SHA256 = 24957d4171b266c8a666b56f950cd35eb50226421ba590ff4fd6db769043c460
SOURCE_BUNDLE_MANIFEST = 6/6 PASS
FINDINGS = CF-FILE-001; CF-SQLITE-HARDEN-001
FINDINGS_COUNT = 2
PROVIDER_CALLS = 0
```

Le lot matérialise l'adaptateur local derrière `SandboxFilesystemPort` et une primitive unique de sécurité physique réutilisée par le runtime SQLite, l'index sémantique, les backups et les restaurations. Il ne modifie ni Domain, ni Application, ni migration `001`/`002`, ni sémantique métier.

Le seed externe n'est admis qu'en lecture stricte. Les seules écritures SQLite de validation ciblent des copies et fixtures sous le répertoire temporaire système. Aucun runtime utilisateur, seed, sidecar historique, appel fournisseur, credential, push, merge, travail B03 ou travail 12.18 n'appartient au périmètre.

```text
B02_IN_SCOPE = LOCAL_FILESYSTEM_ADAPTER; PHYSICAL_PATH_GUARD; SQLITE_7_GUARDS; TESTS; EVIDENCE
B02_OUT_OF_SCOPE = USER_DB_MUTATION; SEED_MUTATION; PROVIDERS; B03; 12.18; PUSH; MERGE
```
