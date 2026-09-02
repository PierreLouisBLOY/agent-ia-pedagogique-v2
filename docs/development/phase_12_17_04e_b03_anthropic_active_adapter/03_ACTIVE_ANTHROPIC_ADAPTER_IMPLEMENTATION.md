# Phase 12.17.4E-B03 — Adapter Anthropic actif

## Cible créée

`calibration_tooling/adapters/anthropic/` contient exactement :

- `contracts.py` : configuration résolue, client injecté, request/response,
  usage, stop reason, erreurs fermées et source de projection ;
- `mapping.py` : mapping déterministe du spec B02 et de la projection autorisée ;
- `parser.py` : normalisation response/usage/coût vers `RawProviderResponse` ;
- `transport.py` : unique appel au client injecté et unique révélation du secret ;
- `scorer.py` : implémentation de `ProviderTransportPort.invoke` ;
- `__init__.py` : surface publique bornée.

Le package parent `calibration_tooling/adapters/__init__.py` est également créé.

## Flux actif B03

```text
CalibrationService
  -> ProviderTransportPort.invoke
  -> AnthropicCalibrationScorer
  -> AnthropicProjectionSource [injecté]
  -> build_anthropic_scoring_request
  -> AnthropicMessagesTransport
  -> AnthropicMessagesClient [injecté]
  -> parse_anthropic_response
  -> CanonicalCalibrationOutputParser B02
```

L'adapter ne lit ni environnement, ni fichier, ni SQLite. Il ne sélectionne pas
de route provider et ne crée pas de composition ou CLI, réservés à B04. Le
payload est fourni par un port injecté lié au `CallRef`; une absence ou une
discordance bloque avant le transport.

```text
ACTIVE_ADAPTER_TARGET = calibration_tooling/adapters/anthropic
ACTIVE_PROVIDER_PORT_IMPLEMENTED = ProviderTransportPort
CLIENT_INJECTION = REQUIRED
SDK_IMPORT = NONE
RAW_RESPONSE_PERSISTENCE = NONE
```
