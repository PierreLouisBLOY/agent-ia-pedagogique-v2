# Phase 12.17.4E-B02 — Inventaire des générations runner/parser

## Classification exécutable

| Génération | Chemin | Nature | Classification B02 | Entrants | Sortants principaux | Protection | Diagnostics liés |
|---:|---|---|---|---:|---|---|---|
| 1 | `tests/calibration/pedagogical/live_runner.py` | runner | `HISTORICAL_IMMUTABLE` | 8 historiques/tests | backend OpenAI, harness, corpus/call-plan/protocol historiques, `tests.providers.anthropic` | HIST-006, `8c7f8872...` | 018/019 transitifs |
| 2 | `tests/calibration/pedagogical/live_runner_v4_1.py` | runner | `HISTORICAL_IMMUTABLE` | 1 test historique | mêmes frontières, call-plan V4.1, `tests.providers.anthropic` | HIST-007, `bf354170...` | 021/022 transitifs |
| 3 | `tests/calibration/pedagogical/semantic_parser_adapter_v5_1.py` | parser | `HISTORICAL_IMMUTABLE` | 10 historiques/tests | pricing, scorer V5, intégration V5, contrats Anthropic sous `tests` | HIST-028, `4788eac7...` | 001–005 transitifs |
| 4 | `tests/calibration/pedagogical/semantic_gate_v5_2.py` | runner/gate | `HISTORICAL_IMMUTABLE` | 5 historiques/tests | calibration V5, pricing, scorer, micro/mini/parser/freeze | HIST-024, `f4eaddf6...`, drift 12.17.2A | 033 direct |
| 5 | `tests/calibration/pedagogical/pairwise_runner_v5_2_2.py` | runner/parser dispatch | `HISTORICAL_IMMUTABLE` | 3 tests | gate V5.2, pricing, intégration, parser V5.1, freeze | HIST-012, `ec72fd6d...` | 033 transitive |
| 6 | `tests/calibration/pedagogical/pairwise_output_contract_v5_2_3.py` | parser/output contract | `HISTORICAL_IMMUTABLE` | 3 historiques/tests | pricing, scorer, intégration, parser V5.1, contrats Anthropic | HIST-010, `bde7afa8...` | traversée historique |
| 7 | `tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py` | parser/output contract | `HISTORICAL_IMMUTABLE` | 1 test historique | V5.2.3, pricing, scorer, intégration, contrats Anthropic | HIST-011, `3f47351e...` | root des 15/10 |

Les sept générations sont aussi `TEST_ONLY` au sens de leur accessibilité
actuelle, mais `HISTORICAL_IMMUTABLE` est leur classification propriétaire.
Aucune n'est `LEGACY_COMPAT`, `ACTIVE_TARGET` ou `DEAD/UNREACHABLE` : elles
restent atteignables uniquement par leurs preuves et tests historiques.

## Cible après B02

```text
RUNNER_PARSER_GENERATIONS_BEFORE = 7
ACTIVE_TARGET_COUNT = 1
ACTIVE_RUNNER = calibration_tooling.runtime.runner.CanonicalCalibrationRunner
ACTIVE_PARSER = calibration_tooling.contracts.parser.CanonicalCalibrationOutputParser
HISTORICAL_GENERATIONS_RETAINED = 7
LEGACY_COMPAT_WRAPPERS_RETAINED = 0
```

Le runner et le parser forment une seule génération active versionnée. Le
parser n'est pas un second orchestrateur. Aucun ancien point d'entrée n'est
aliasé vers la cible active.
