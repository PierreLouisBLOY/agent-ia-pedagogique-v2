# Phase 12.17.4E-B05 — Preuve d'implémentation

## Dépréciation active

`calibration_tooling/HISTORICAL_ONLY.md` qualifie explicitement les deux
anciennes racines comme preuves non importables :

- `tests/calibration/pedagogical/` ;
- `tests/providers/anthropic/`.

Il relie chaque responsabilité historique à son propriétaire actif sans
copier, déplacer ou modifier les anciennes implémentations. La documentation
indique explicitement que la parité ne vaut ni réexport ni fallback.

## Tests de parité

Les tests unitaires vérifient les invariants approuvés : blind scoring,
strong-only, autorisation one-shot, fail-closed, zéro retry, absence de seuil,
triplet strong/mixed/weak de cardinalité fixe, schémas absolu/pairwise et
ownership direct des types.

Le test d'intégration rejoue les deux branches du runner actif sur un transport
fake et compare le résultat au snapshot contractuel approuvé, sans importer un
module historique.

## Isolation typing

Le nouveau guard parcourt le source actif et ses tests unitaires/intégration.
Il interdit les imports historiques, `tests/providers`, les `.pyi`, les
`type: ignore`, `typing.Any` et les exclusions mypy. Son registre de preuve
relie les 15 diagnostics aux tests actifs.

```text
ACTIVE_RUNTIME_FILES_MODIFIED = 0
ACTIVE_IMPORT_EDITS_REQUIRED = 0
HISTORICAL_SOURCE_FILES_MODIFIED = 0
PROVIDER_CALLS = 0
CREDENTIAL_RESOLUTIONS = 0
SQLITE_ACCESSED = 0
SQLITE_MODIFIED = 0
```
