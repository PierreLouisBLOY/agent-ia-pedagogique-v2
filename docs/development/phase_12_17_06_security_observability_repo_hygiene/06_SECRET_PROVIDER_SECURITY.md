# Phase 12.17.6 — Secrets et frontières fournisseurs

## Scan

Le scan de formes de clés AWS/GitHub/Slack/OpenAI, bearer tokens longs et clés privées sur le code, la configuration, les documents, les tests et les artefacts textuels pertinents n'a trouvé aucun credential. Aucun fichier `.env*` n'est présent à la racine. Les recherches n'ont jamais imprimé de valeur potentiellement secrète.

Les mentions `api_key`, `credential`, `secret`, `prompt` ou `raw_response` dans les racines ignorées sont des noms de champs, du code de lancement local ou des rapports de sécurité. Les 12 JSON locaux contenant `raw_response` attestent tous `raw_response_persisted=false` ou `raw_response_persistence=NONE`.

`SECRET_FINDINGS_COUNT = 0`

## Résolution et transport

- La configuration conserve uniquement un `ProviderCredentialRef`; le secret est une valeur opaque dont `repr`/`str` sont redacted et qui n'est révélée qu'au transport.
- Les loaders reçoivent un mapping injecté ; aucun `os.environ`/`getenv` n'est lu directement dans `backend/` ou `calibration_tooling/`.
- OpenAI Responses utilise `store=False`, sortie JSON schema stricte, aucun outil, aucun streaming, timeout borné et `max_retries=0`.
- OpenAI embeddings utilise timeout et `max_retries=0`.
- Anthropic calibration est désactivé par défaut. L'activation exige configuration, secret, projection source, allowlist exacte, autorisation one-shot, budget et ledger. Transport et runner effectuent un seul appel par spec et ne retentent pas.
- Les erreurs fournisseurs sont traduites en codes fermés, sans corps de réponse ni credential.
- Les sorties réseau sont limitées aux adaptateurs OpenAI et à l'adaptateur/client Anthropic injecté ; aucun autre import réseau n'a été trouvé.

## Verdict

`PROVIDER_BOUNDARY_STATUS = PASS`

`LIVE_PROVIDER_DEFAULT = DISABLED`

`RAW_RESPONSE_PERSISTENCE = NONE_CONFIRMED_FOR_LOCAL_LIVE_REPORTS`
