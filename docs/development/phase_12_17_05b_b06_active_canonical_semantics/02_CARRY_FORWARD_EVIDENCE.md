# Phase 12.17.5B-B06 — Preuves carry-forward

Les manifests des lots antérieurs ont été recalculés puis vérifiés entrée par
entrée.

| Lot | Entrées | Écarts | SHA-256 du manifest |
|---|---:|---:|---|
| B02 | 11 | 0 | `085035b8a3fc637252bb918301f1bf6fe93efcfce1b95a97b641da0a06be1635` |
| B03 | 13 | 0 | `83b01fb534a591a3e4509cc35adfdf43cd9beff2a6ccff88566571ac8d33147c` |
| B04 | 14 | 0 | `ec27bac6cc1f3879b1db2fca7b1f1dc00535aff64ae3094970239bbdca0d3fb8` |
| B05 | 13 | 0 | `d8b26c52889da83ef4137f7b8b55956d5b12eaebccf0553e7bcc0cae80174c3a` |

Les identités techniques structurantes restent :

- migration `001` : `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102` ;
- migration corrective `002` : `e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893` ;
- contrat exécutable `ResourceRef` : `f33c591de1774cb937e0bdc7d622efbd32f28be6e048669dae67d3e336da634d`.

B06 ne modifie ni le runner multiversion, ni `001`, ni `002`, ni le contrat
`ResourceRef`, ni les preuves de récupération réelle.

```text
CARRY_FORWARD_MANIFESTS = 4/4 PASS
CARRY_FORWARD_ENTRIES = 51/51 PASS
MIGRATION_001_MODIFIED_BY_B06 = FALSE
MIGRATION_002_MODIFIED_BY_B06 = FALSE
RESOURCE_REF_CONTRACT_MODIFIED_BY_B06 = FALSE
```
