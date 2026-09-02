# Phase 12.17.4E-B03 — Erreurs et sécurité

## Matrice fail-closed

| Situation | Erreur active | Appels supplémentaires |
|---|---|---:|
| credential absent | `CREDENTIAL_UNAVAILABLE` | 0 |
| timeout client | `PROVIDER_UNAVAILABLE` | 0 |
| HTTP non-2xx | `PROVIDER_UNAVAILABLE` | 0 |
| client indisponible/inconnu | `PROVIDER_UNAVAILABLE` | 0 |
| response client mal typée | `RESPONSE_INVALID` | 0 |
| projection absente ou mal liée | `TRANSFER_SCOPE_MISMATCH` | 0 |
| JSON de projection invalide | `INVALID_PAYLOAD` | 0 |
| sortie structurée invalide | parser B02, erreur fermée | 0 |
| sortie tronquée par max tokens | `RESPONSE_TRUNCATED` | 0 |

Les helpers d'erreur utilisent `NoReturn` pour préserver le narrowing strict.
Les erreurs publiques ne contiennent ni message SDK, ni body/header HTTP, ni
prompt, ni payload, ni request id, ni secret, ni chemin local.

## Secrets

Le secret actif est un `ProviderSecretValue`. Sa valeur n'est révélée que dans
`calibration_tooling/adapters/anthropic/transport.py`, au dernier moment, comme
argument transitoire du client injecté. Aucun accès environnement n'existe à
l'import et aucune vraie clé n'est utilisée par les tests. Les `repr` transport,
payload, request, message et response sont vérifiés pour exclure les contenus.

## Exécution

```text
RETRY_COUNT = 0
RERUN = NONE
PROVIDER_CALLS = 0
OPENAI_CALLS = 0
ANTHROPIC_CALLS = 0
CREDENTIAL_RESOLUTIONS_REAL = 0
SECRETS_FOUND = 0
RAW_PROVIDER_RESPONSE_PERSISTED = 0
```

Les appels observés par les tests sont uniquement ceux de clients locaux fake
injectés ; ils ne quittent jamais le processus.
