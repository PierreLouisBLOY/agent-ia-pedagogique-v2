# Phase 12.17.4E-B04 — Preuve d'implémentation

## Configuration et composition

`CalibrationRuntimeConfiguration` est un contrat injecté, versionné et limité
au provider Anthropic déjà approuvé. `live_provider_enabled` vaut `False` par
défaut. L'activation exige une configuration Anthropic résolue, puis des
dépendances injectées : client, secret opaque, projection source, ledger et
horloge.

`compose_calibration_runtime` est l'unique site actif qui assemble :

1. le transport B03 ;
2. le scorer B03 ;
3. le service/parser B02 ;
4. les gardes one-shot et budget B02 ;
5. le runner canonique B02.

La composition ne lit ni environnement, ni argument process, ni fichier, ni
SQLite. Elle ne résout aucun credential et ne charge aucun SDK provider.

## CLI unique

`calibration_tooling.runtime.cli.main` accepte uniquement la commande exacte
`run` et uniquement des objets déjà injectés. Il ne lit pas `sys.argv`, ne
parcourt pas le filesystem et n'active rien implicitement. Les sorties sont
des rapports typés ne contenant que référence de run, coût borné ou code
d'erreur fermé.

## Télémétrie sûre

Le schéma autorise uniquement les références opaques, codes provider/modèle,
état, durée, compteurs de tokens, coût et code d'erreur fermé. Prompt, payload,
projection, réponse, secret et thinking ne font pas partie du contrat. Le sink
par défaut est sans I/O ; une panne du sink est best-effort et ne peut ni
changer l'issue provider ni provoquer un retry.

```text
LIVE_PROVIDER_DEFAULT_ENABLED = FALSE
ACTIVE_RUNNER_COUNT = 1
ACTIVE_PARSER_COUNT = 1
ACTIVE_CLI_COUNT = 1
PROVIDER_CALLS = 0
CREDENTIAL_RESOLUTIONS = 0
SQLITE_ACCESSED = 0
SQLITE_MODIFIED = 0
```
