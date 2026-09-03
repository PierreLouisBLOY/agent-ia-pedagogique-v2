# Phase 12.17.4E-B07 — Résolution du scope canonique

```text
PHASE = 12.17.4E-B07
CANONICAL_TITLE = Configuration de chemins
ROOT_CHANGE = RC-07
ENTRY_HEAD = 757254675d51ace6c1173cc21217580ae2509ba9
SOURCE_BUNDLE_SHA256 = 13107ef68de7823e0c5f37b644ee0ea8b1a99283ff2c7d9e0ea828ba57dc9f8a
SOURCE_PROMPT_SHA256 = 6953a1098cbff12492478073b3f3b6d55dda59826db91b61e3b2affaeda21f59
```

Le lot introduit `PROJET_V2_DATA_DIR`, `PROJET_V2_CANONICAL_DB` et
`PROJET_V2_RUNTIME_DB`, leurs valeurs par défaut dépendantes de l'OS et une
compatibilité stricte avec les deux anciens noms. Les conflits, chemins
relatifs, valeurs vides et collisions seed/runtime ferment la configuration.

Le cycle seed/runtime, les sidecars, copies, migrations et backups relèvent de
B08. La documentation d'exploitation et l'API relèvent de B09. Aucun provider,
secret, accès SQLite ou changement métier n'appartient à B07.

```text
GLOBAL_DISK_DISCOVERY = FORBIDDEN
PRIVATE_DEFAULT_PATH_IN_GIT = FORBIDDEN
SEPARATE_COMMIT = TRUE
```
