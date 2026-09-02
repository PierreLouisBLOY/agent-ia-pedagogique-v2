# Phase 12.17.4E-B03 — Graphe d'import

## Résultats

```text
ACTIVE_IMPORTS_TO_TESTS = 0
ACTIVE_IMPORTS_TO_TESTS_PROVIDERS = 0
ACTIVE_IMPORTS_TO_HISTORICAL = 0
BACKEND_IMPORTS_TO_CALIBRATION_TOOLING = 0
EVALUATION_HARNESS_IMPORTS_TO_CALIBRATION_TOOLING = 0
PROVIDER_SDK_IMPORTS_IN_ADAPTER = 0
PROVIDER_SDK_IMPORTS_IN_CONTRACTS_APPLICATION = 0
SQLITE_IMPORTS_IN_ADAPTER = 0
ENVIRONMENT_READS_IN_ADAPTER = 0
```

Le seul import de configuration du nouvel adapter est le type sûr
`ProviderSecretValue` dans la frontière transport. Les contracts/application
B02 restent provider-neutral.

Le guard B02 a été étendu pour reconnaître la surface Anthropic créée par B03
tout en maintenant l'absence de `runtime/composition.py` et `runtime/cli.py`.
Un guard B03 dédié contrôle les six fichiers, les imports interdits, l'absence
de boucle de retry et de persistence, la révélation du secret confinée au
transport, l'implémentation structurale de `ProviderTransportPort` et les deux
hashes Anthropic historiques.

```text
ARCHITECTURE_GUARDS = 17/17 PASS
B04_COMPOSITION_PRESENT = FALSE
B04_CLI_PRESENT = FALSE
```
