# Preuve de résolution des dépendances

| Ensemble | Directes | Total résolu | Transitifs | Sdist | Wheelhouse manifest SHA-256 |
|---|---:|---:|---:|---:|---|
| runtime | 1 | 14 | 13 | 0 | `02daf1b9cf570a995a8778b88705fbf3405ef74bb3ec391f666e91622b85c0e3` |
| calibration | 2 | 16 | 14 | 0 | `67bc7815f84472cd65e432c578fd890e506cb65e29839e64bd8d97d6d184da12` |
| dev | 4 | 26 | 22 | 0 | `da32e3304b3142f46350721775f9a36e1054c883f5e16971c58d48ba6699b029` |

Versions directes résolues : `openai==3.8.0`, `anthropic==1.4.0`,
`pytest==9.1.1`, `ruff==0.16.4`, `mypy==2.3.1`. Elles satisfont les bornes et pins
sources sans modifier ceux-ci.

```text
RESOLUTION_STATUS = PASS
FULLY_PINNED = TRUE
TRANSITIVE_DEPENDENCIES_COVERED = TRUE
HASH_PER_REQUIREMENT = TRUE
PRERELEASE_COUNT = 0
UNEXPECTED_DIRECT_DEPENDENCY_COUNT = 0
UNEXPECTED_SDIST_COUNT = 0
```
