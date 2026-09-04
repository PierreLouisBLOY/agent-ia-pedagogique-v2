# Phase 12.17.8-B02 — Backup, restauration, WAL et SHM

Les chemins runtime, backup, manifest et restauration sont tous bornés par une data root locale. Le backup refuse seed/runtime/backup identiques, une cible existante et une sortie de racine. Il checkpoint le WAL, utilise l'API SQLite backup, contrôle intégrité et foreign keys, écrit le manifest dans un temp privé du même volume et publie les deux fichiers sans écrasement.

La restauration exige un backup et un manifest sans redirection, authentifie le SHA-256, copie vers un temp privé, revérifie le hash et l'intégrité, puis publie uniquement vers une cible runtime fraîche distincte du seed et du backup.

Le runtime mutable peut produire WAL/SHM; ces sidecars sont attribués par snapshots et leurs données cohérentes sont rabattues par checkpoint/API backup. Le seed ne crée aucun sidecar nouveau. Les sidecars seed historiques et les sidecars utilisateur ne sont ni attribués à B02 ni nettoyés.

```text
BACKUP_FRESH_DESTINATION = PASS
BACKUP_AUTHENTICATION = PASS
RESTORE_FRESH_RUNTIME_ONLY = PASS
RESTORE_TO_SEED = DENY
RUNTIME_WAL_SHM = ALLOWED_AND_ATTRIBUTED
SEED_SIDECAR_NEW_COUNT = 0
HISTORICAL_SIDECAR_DELETION = 0
```
