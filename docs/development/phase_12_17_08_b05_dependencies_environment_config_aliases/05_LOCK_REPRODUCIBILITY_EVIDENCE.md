# Preuve de locks et reproductibilité

| Lock | Lignes | SHA-256 du lock | Deux clean installs | Freeze SHA-256 commun |
|---|---:|---|---|---|
| `runtime-py312-win.txt` | 14 | `47540b39687a39f627c76e138596abfa752792fa54cef439660c5daba9665a63` | PASS | `f76d3ea4b5ab8824725596e3129ec0efa3711b457149721420a088bc55e616f1` |
| `calibration-py312-win.txt` | 16 | `e044cdb328a65f0d24ad4e82868171c6f96f7ef1e6cbcd6be78d402e3e8d7960` | PASS | `c3763372f147f4794e1cabbe2dff1436e489b814e8c87e218f4476c536bac9c4` |
| `dev-py312-win.txt` | 26 | `30a3ceec14d10432cd45f4ddddcd54868dd6da55001c8a74c6d125eac97a6c65` | PASS | `245042fbde3dd0a1219678c9708a4d8a7d4b85ae42ce6dc9efb473e750d91aa2` |

Chaque installation a utilisé `--no-index --find-links`, `--require-hashes`,
`--no-deps` et exclusivement le wheelhouse correspondant. `pip check` et les imports
smoke ont passé dans les six environnements. Une exigence sans hash soumise avec
`--require-hashes` a échoué avant réinstallation : `MISSING_HASH_FAIL_CLOSED = PASS`.

Le guard versionné compare les empreintes des deux inputs, les bornes, les pins, la
partition des ensembles, les métadonnées de cible et le format de chaque exigence.

```text
LOCK_STATUS = PASS
HASH_VERIFICATION_STATUS = PASS
TWO_CLEAN_INSTALLS_PER_SET = 3/3 PASS
REPRODUCIBILITY_VALIDATION = PASS
RUNTIME_NETWORK_DEPENDENCY = FALSE
```
