# Phase 12.17.2A — Corrections par cluster

## C01 — Scaffolding de typing obsolète

Résultat : `10/11` diagnostics supprimés par `10` corrections locales.

- retrait de l'ignore devenu inutile dans `catalog.py`;
- retrait d'un cast redondant dans `review_contract_v4_2.py`;
- retrait d'un cast redondant dans `repair_tranche_v4_2.py`;
- retrait de quatre casts redondants dans `semantic_integration_v5.py`;
- retrait d'un cast redondant dans chacun de `semantic_pilot_freeze_v5.py`, `semantic_mini_pilot_v5_1.py` et `semantic_gate_v5_2.py`;
- maintien de `MYPY-001` dans `transport.py` après rollback de son fix pour préserver les identités historiques.

Les imports `cast` devenus inutiles ont été retirés uniquement dans les deux fichiers où aucun autre cast légitime ne subsistait.

## C04 — Collision de variable de boucle

Résultat : `7/7` diagnostics supprimés par `1` correction racine.

La deuxième boucle de `render_alignment_matrix()` utilise désormais `carry_forward` au lieu de réutiliser `item`. Le nom local est le seul changement logique; la concaténation et le rendu produits restent identiques.

## C06 — Union dynamique d'observation

Résultat : `1/1` diagnostic supprimé par `1` correction racine.

Le tuple local `values` est annoté `tuple[ObservationScalar | ObservationSequence, ...]`. Les objets construits, leur ordre et le `zip(..., strict=True)` restent inchangés.

## Total

- `ROOT_CORRECTIONS_APPLIED = 12`
- `DIAGNOSTICS_REMOVED = 18`
- `CODE_FILES_MODIFIED = 9`
- `TYPE_SYSTEM_ONLY = TRUE`
- `BUSINESS_RULE_CHANGE = FALSE`
- `API_OR_SQLITE_CONTRACT_CHANGE = FALSE`
- `FILE_MOVE_COUNT = 0`
- `NEW_TYPE_IGNORE_COUNT = 0`
- `ANY_ESCAPE_HATCH_COUNT = 0`
