# Phase 12.17.4E-B07 — Gate d'entrée B08

```text
NEXT_BATCH = 12.17.4E-B08
NEXT_TITLE = Cycle seed/runtime et sidecars
NEXT_ROOT_CHANGE = RC-08
B08_ENTRY_GATE = READY
```

B08 doit conserver les identités B07 et capturer les snapshots PRE/POST du
seed et de ses sidecars. Il doit provisionner la runtime par copie atomique,
réserver WAL, migrations et backups à cette runtime, puis exécuter les gates
réelles conditionnelles contre le seed canonique exact.

Le seed ne peut être ouvert qu'en lecture seule pour les preuves prévues. Toute
création ou modification inattendue de sidecar seed, divergence de hash,
fallback de chemin ou migration du seed ferme la gate. Les deux inconnues B06
restent inchangées.
