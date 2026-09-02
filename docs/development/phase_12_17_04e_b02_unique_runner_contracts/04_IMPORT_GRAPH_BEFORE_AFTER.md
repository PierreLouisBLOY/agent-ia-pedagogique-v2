# Phase 12.17.4E-B02 — Graphe d'import avant/après

## Avant

```text
tests/calibration/pedagogical/live_runner*
  -> backend OpenAI + runtime agents
  -> evaluation_harness
  -> tests/calibration/pedagogical/*
  -> tests/providers/anthropic/*

pairwise_output_contract_v5_2_4
  -> V5.2.3 -> V5.1 parser
  -> semantic integration/scorer/pricing
  -> tests/providers/anthropic/contracts
```

Cette traversée reste historique et reproduit `15 erreurs / 10 fichiers`.

## Après

```text
CanonicalCalibrationRunner
  -> application.CalibrationServicePort
  -> runtime authorization + budget + ledger
  -> contracts models + policy + errors

CalibrationService
  -> ProviderTransportPort [injecté, aucune implémentation B02]
  -> CalibrationOutputParserPort

CanonicalCalibrationOutputParser
  -> contrats actifs uniquement
```

## Résultats mesurés

```text
ACTIVE_IMPORTS_TO_HISTORICAL = 0
ACTIVE_IMPORTS_TO_TESTS_PROVIDERS = 0
ACTIVE_IMPORTS_TO_TESTS = 0
BACKEND_IMPORTS_TO_CALIBRATION_TOOLING = 0
EVALUATION_HARNESS_IMPORTS_TO_CALIBRATION_TOOLING = 0
PROVIDER_SDK_IMPORTS_IN_CONTRACTS_APPLICATION = 0
LEGACY_COMPAT_DEFAULT_IMPORTS = 0
```

Le port transport est prêt pour B03. Aucun adapter réel, SDK ou client n'est
composé par B02.
