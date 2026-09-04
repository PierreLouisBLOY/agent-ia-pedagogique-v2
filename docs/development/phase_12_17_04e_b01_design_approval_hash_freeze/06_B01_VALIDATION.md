# Phase 12.17.4E-B01 — Validation du lot

## Matrice de contrôle

| Contrôle | Attendu | Résultat |
|---|---:|---:|
| Liaison propriétaire à la baseline exacte | PASS | PASS |
| ADR-P12-068 présent et accepté | PASS | PASS |
| Décision `ACTIVE_RUNTIME != HISTORICAL_CALIBRATION_EVIDENCE` | PASS | PASS |
| Entrées du registre machine-readable | 40 | 40 |
| Identifiants historiques uniques | 40 | 40 |
| Chemins historiques uniques | 40 | 40 |
| Hashes SHA-256 courants valides et vérifiés | 40/40 | 40/40 PASS |
| `immutable` | 40 × `true` | PASS |
| `allowed_operation` | 40 × `READ_ONLY` | PASS |
| Baseline par entrée | 40 × baseline approuvée | PASS |
| Dérives préexistantes | 7 | 7 |
| Origine des dérives | 12.17.2A | 7/7 PASS |
| Réparation rétroactive | FORBIDDEN | 7/7 PASS |
| PRE/POST identiques | 40/40 | 40/40 PASS |
| Guard d'architecture B01 | 5 tests | 5/5 PASS |
| Ruff ciblé | 0 diagnostic | PASS |
| Mypy ciblé | 0 diagnostic | PASS |
| Fichiers historiques modifiés par B01 | 0 | 0 |
| Code runtime modifié par B01 | 0 | 0 |
| Support de test explicitement autorisé | 1 fichier | 1 fichier |
| Base SQLite ouverte ou modifiée | 0 | 0 |
| Appel fournisseur | 0 | 0 |
| B02 démarré | non | non |

## Nature des validations

Le lot ne modifie que l'ADR, ses preuves documentaires et le guard
`tests/architecture/test_calibration_tooling_boundary.py`, explicitement prévu
par le plan B01. Le SHA-256 du guard est
`43f91d0ea1d631588b76c9646edb8ddba16a771393694d4aa8cda95b2c2e2309`.

Les validations exécutées couvrent le parsing JSON, les cardinalités,
l'unicité, le format et la concordance des 40 hashes, le contrôle PRE/POST,
les références historiques, les imports interdits du graphe actif, le
manifeste, la recherche de secrets et les espaces de fin de ligne. Le test
ciblé, Ruff et Mypy sont tous PASS. Aucun test runtime n'est requis par ce lot.

`B01_VALIDATION_STATUS = PASS`
