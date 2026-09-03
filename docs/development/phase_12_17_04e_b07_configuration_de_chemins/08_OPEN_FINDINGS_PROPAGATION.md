# Phase 12.17.4E-B07 — Findings ouverts et propagation

Deux inconnues B06 restent explicitement `UNKNOWN`, sans défaut inventé ni
migration :

1. le mapping exact des états Resource `ACTIVE` et `CANONICAL` ;
2. le vocabulaire et l'ownership définitifs de `ContextOrigin`.

L'écart de hash global connu dans `catalog.py` reste antérieur, enregistré et
hors scope. Aucun de ces éléments n'empêche RC-07.

Le risque propre à B07 était un fallback silencieux vers le mauvais seed. Il
est contrôlé par des chemins absolus, un choix déterministe des defaults, le
rejet des conflits new/legacy et le rejet des collisions d'identité. La preuve
réelle du seed et du cycle runtime reste obligatoire en B08.

```text
RESIDUAL_B07_FINDINGS = 0
B06_UNKNOWN_FINDINGS_CARRIED = 2
CATALOG_HASH_MISMATCH_REPAIRED = FALSE
```
