# Matrice runtime, calibration et développement

| Propriété | Runtime | Calibration | Dev/test |
|---|---|---|---|
| Lock | `runtime-py312-win.txt` | `calibration-py312-win.txt` | `dev-py312-win.txt` |
| OpenAI | direct | hérité du runtime | hérité du runtime |
| Anthropic | absent | extra direct | absent |
| pytest/ruff/mypy | absents | absents | directs et épinglés |
| Transitifs entièrement épinglés | oui | oui | oui |
| Hashes wheels | oui | oui | oui |
| Réseau requis à l'installation offline | non | non | non |

Le lock calibration est un sur-ensemble strict du runtime avec seulement `anthropic`
et son transitif `docstring-parser`. Le lock dev est un autre sur-ensemble strict du
runtime et ne transforme pas Anthropic en dépendance produit ou dev.

```text
RUNTIME_DEV_TEST_SPLIT_STATUS = PASS
ANTHROPIC_RUNTIME_LEAK_COUNT = 0
ANTHROPIC_DEV_LEAK_COUNT = 0
DIRECT_DEPENDENCY_SOURCE_DRIFT = 0
```
