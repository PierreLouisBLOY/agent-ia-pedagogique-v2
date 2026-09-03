# Phase 12.17.4E-B08 — Tests ciblés

```text
B08_DIRECT_WITH_REAL_SEED = 16/16 PASS
CUMULATIVE_B01_B08_OFFLINE = 161 PASS, 19 CONDITIONAL SKIP
REAL_SKIP_REACTIVATION = 19/19 PASS
ADJACENT_SQLITE_REAL_GATES = 2/2 PASS
ARCHITECTURE_FINAL = 46/46 PASS
FAILED = 0
```

Les onze tests unitaires B08 couvrent : seed valide/invalide/absent, bootstrap
absent, runtime existante idempotente, identité seed/runtime, migration non
allowlistée, sidecars seed préexistants, course de publication sans
écrasement, backup/restore authentifié et interdiction de restauration sur le
seed. Quatre guards d'architecture et une gate réelle complètent ces cas.

Le run offline conserve 19 skips lorsque le seed n'est volontairement pas
configuré ; leur run réel distinct produit 19 PASS. La suite globale de
`ENVIRONMENT.md` reste réservée à la clôture après B09, conformément au plan.
