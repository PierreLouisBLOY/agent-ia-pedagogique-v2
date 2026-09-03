# Phase 12.17.4E-B09 — Résolution du scope

```text
PHASE = 12.17.4E-B09
B09_CANONICAL_TITLE = Legacy review et handoff API
B09_ROOT_CHANGE = RC-09
B09_ENTRY_GATE = READY
HEAD_PRE_B09 = 054ba2c7eb19f1be4eb048f94e554022db631dc1
COMMIT_POLICY = SEPARATE_COMMIT
```

Le lot matérialise la trace rétrospective OD-02 et publie pour 12.17.5 les
contraintes OD-03, OD-04 et OD-07. Il crée les deux fichiers prévus sous
`docs/legacy-review/`, un handoff documentaire et machine-readable, ainsi que
quatre guards documentaires.

Sont hors scope : tout endpoint HTTP, use case Application nouveau, migration,
accès ou modification SQLite, résolution des deux inconnues sémantiques,
provider, credential, 12.17.5 et 12.18.

Le titre, `RC-09`, les fichiers attendus, les tests documentaires et la policy
de commit correspondent au plan canonique sans divergence.
