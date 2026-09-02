# Phase 12.17.4E-B02 — Fermeture mypy partielle RC-05

## Mesures

| Graphe | Avant B02 | Après B02 | Verdict |
|---|---:|---:|---|
| `mypy backend` | 0 / 659 fichiers | 0 / 659 fichiers | PASS |
| tooling actif strict import-driven | package absent | 0 / 19 fichiers | PASS |
| ancien root V5.2.4 informatif | 15 erreurs / 10 fichiers | 15 erreurs / 10 fichiers | STABLE |
| nouveaux diagnostics | 0 | 0 | PASS |

## Diagnostics ciblés par B02

| Error ID | Before / cause | Fix B02 dans le graphe actif | After | Test | Historique modifié |
|---|---|---|---|---|---|
| MYPY-007 | tuple variable vers triplet fixe | `AnchorTriplet` à trois champs typés | 0 actif | `test_anchor_triplet_*` | NO |
| MYPY-008 | V2 importé dans l'ancien graphe | aucune dépendance V2 ; frontière `AnchorTriplet` | 0 actif | contracts + architecture | NO |
| MYPY-009 | V3 importé dans l'ancien graphe | aucune dépendance V3 ; même contrat fixe | 0 actif | contracts + architecture | NO |
| MYPY-017 | V4 importé dans l'ancien graphe | projection référencée par `ProjectionRef`, sans import V4 | 0 actif | contracts + architecture | NO |
| MYPY-018 | plafond optionnel à gauche de `>` | `ApprovedBudget.ceiling_usd: Decimal` requis | 0 actif | budget | NO |
| MYPY-019 | même plafond optionnel | calcul exact borné après validation | 0 actif | budget | NO |
| MYPY-021 | duplication V4.1 optionnelle | budget actif commun unique | 0 actif | budget | NO |
| MYPY-022 | même duplication | même garde non optionnelle | 0 actif | budget | NO |
| MYPY-033 | union réassignée entre specs | dataclasses discriminées et branches distinctes | 0 actif | parser + runner | NO |

```text
B02_MYPY_DIAGNOSTICS_TARGETED = 9
B02_MYPY_DIAGNOSTICS_CLOSED_IN_ACTIVE_GRAPH = 9
HISTORICAL_DIAGNOSTICS_CLAIMED_FIXED = 0
```

MYPY-001 à 005 restent attendus pour B03. MYPY-023 disparaîtra de la traversée
active lors des lots de composition/parité sans modifier sa source historique.
Aucun ignore, exclude, stub ou `Any` d'échappement n'a été ajouté.
