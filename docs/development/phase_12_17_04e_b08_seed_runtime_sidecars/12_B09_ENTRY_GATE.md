# Phase 12.17.4E-B08 — Gate d'entrée B09

```text
NEXT_BATCH = 12.17.4E-B09
NEXT_TITLE = Legacy review et handoff API
NEXT_ROOT_CHANGE = RC-09
B09_ENTRY_GATE = READY
```

B09 doit uniquement matérialiser la trace rétrospective OD-02 et propager les
contraintes OD-03/04/07 vers 12.17.5. Il ne doit ni implémenter `/api/v2`, ni
modifier SQLite, ni réouvrir la calibration, ni appeler un provider.

La gate finale 12.17.4E reste conditionnée au PASS de B09 puis à la suite
globale documentée. B09 n'est pas démarré par ce lot.
