# Handoff final 12.17.8-B06

```text
PHASE_12_17_08_B06 = PASS
B06_CANONICAL_TITLE = .gitignore, tests déterministes et rétention locale
HEAD_PRE = 313d574cc0aca15529978db622939ed648d0c1c7
HEAD_POST = CREATED_AFTER_MANIFEST_FREEZE
FINDINGS_CLOSED = CF-TEMP-LOCAL-001, CF-GITIGNORE-001
FINDINGS_CLOSED_COUNT = 2
ASSIGNED_ITEMS_DISPOSITIONED = 207/207
LOCAL_ITEMS_RETAINED = 203
LOCAL_ITEMS_REMOVED = 0
TMP_IMMEDIATE_ITEMS_PRE_POST = 41/41
TMP_IMMEDIATE_DIRECTORIES_PRE_POST = 31/31
TMP_IMMEDIATE_FILES_PRE_POST = 10/10
TMP_RECURSIVE_DIRECTORIES_PRE_POST = 1673/1673
TMP_FILES_PRE_POST = 4587/4587
LOCAL_TOTAL_FILES_PRE_POST = 20664/20664
LOCAL_TOTAL_DIRECTORIES_PRE_POST = 2994/2994
FINAL_METADATA_ACCESS_GAPS = 0
GITIGNORE_FAMILIES_ASSIGNED_FIXED = 4/4
OVERBROAD_GITIGNORE_PATTERNS = 0
B01_EVIDENCE_TRACKED = 209/209
CANONICAL_PRE_EVIDENCE_UNMASKED = 1001/1001
HISTORICAL_FREEZE = 40/40 PASS
KNOWN_HISTORICAL_DRIFTS = 7/7 PRESERVED
NEW_HISTORICAL_CONTENT_DRIFT = 0
HISTORICAL_MYPY = 15 errors / 10 files STABLE
TRACKED_DB_BINARY_SIDECAR_BACKUP_FINDINGS = 0
SECRET_FINDINGS_COUNT = 0
TARGETED_TESTS = 46 passed
ISOLATED_HISTORICAL_WRITER_TEST = 1 passed
ARCHITECTURE_GUARDS = 872 passed
GLOBAL_OFFLINE_SUITE = 4915 passed, 28 skipped, 0 failed
ACTIVE_MYPY = 0/42
BACKEND_MYPY = 0/683
BACKEND_PLUS_CALIBRATION_MYPY = 0/710
B06_SUPPORT_MYPY = 0/2
RUFF = PASS
COMPILEALL = PASS
GIT_DIFF_CHECK = PASS
REPO_TEMP_POLLUTION = 0
POST_ISOLATION_LOCAL_METADATA_DRIFT = 0
CANONICAL_SEED_ACCESS = 0
CANONICAL_SEED_WRITES = 0
USER_RUNTIME_WRITES = 0
PROVIDER_CALLS = 0
NETWORK_B06 = 0
STAGING_ALLOWLIST_COUNT = 20
COMMIT_COUNT = 1
PUSH = NONE
MERGE = NONE
B07_ENTRY_GATE = READY
B07_CANONICAL_TITLE = Ré-audit transverse et clôture
B07_STARTED = FALSE
PHASE_12_18_STARTED = FALSE
```

## Écarts et limites explicites

Deux anomalies diagnostiques ont été corrigées : variables Windows vidées au lieu d'être retirées, puis test historique écrivant ses rendus dans le dépôt. Les premiers essais ne sont pas annoncés PASS. Le test d'écriture utilise maintenant une copie temporaire et contrôle contenu/mtime des originaux. Le premier passage a changé le mtime du manifeste local reusable_results_manifest.json et de son parent, sans nouvelle donnée résiduelle ; cette trace n'est pas effacée. Aucune dérive supplémentaire de métadonnées après isolation.

Les anciens volumes de temporaires cités par le plan ne sont pas les volumes mesurés actuels. Tous les 203 ensembles locaux sont conservés faute d'autorité de suppression. Leur inutilité ou leur reproductibilité n'est pas inventée. Les métadonnées détaillées restent privées hors Git ; l'inventaire versionné donne leurs digests et dispositions.

Les 28 skips et le fichier réel explicitement ignoré sont détaillés dans 08_TEST_AND_GATE_EVIDENCE.md. La suite hors seed n'est pas une validation du seed réel. B07, et elle seule lorsqu'elle sera demandée, doit faire le ré-audit transverse de clôture.

Le SHA du commit et le statut clean POST sont fournis après le gel du manifeste ; voir 09_STAGING_COMMIT_EVIDENCE.md pour la résolution non circulaire. Ce lot ne démarre pas B07.
