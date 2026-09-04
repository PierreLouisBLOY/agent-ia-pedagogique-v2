# Phase 12.17.7B — Binding de la décision observabilité

```text
OBSERVABILITY_DECISION = OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S
DESTINATION_KIND = LOCAL_NDJSON
MAX_FILE_SIZE_BYTES = 5242880
ROTATED_FILE_COUNT = 5
RETENTION_DAYS_MAX = 14
SHUTDOWN_FLUSH_TIMEOUT_SECONDS_MAX = 2
DECISION_BOUND = TRUE
DECISION_APPLIED = FALSE
TARGET_BATCH = 12.17.8-B03
```

## Destination

Le chemin logique est `<V2_DATA_ROOT>/logs/observability.ndjson`. Le data root doit être résolu par la configuration V2 portable; aucun chemin Desktop/Drive/AppData codé en dur. Le répertoire et les fichiers reçoivent les permissions privées définies par B02.

## Contraintes privacy/security liées

Sont exclus sans exception : secrets, credentials, tokens, prompts, réponses brutes, contenu pédagogique, corps/query/headers/cookies HTTP, rows SQLite, chemins absolus, username, valeurs d'environnement, stack traces, locals et message d'exception non classifié.

Seuls les champs fermés de la matrice 12.17.7 sont admissibles : timestamps UTC, level/code, corrélation/run/step, durée/outcome, identités opaques, versions/checksums, tokens/coût bornés et codes d'erreur fermés.

Le sink reste injecté, local-only, failure-isolated, borné en taille et sans export réseau. Les tests fournisseurs utilisent exclusivement des doubles. Le fichier `*.ndjson` doit rejoindre la famille de logs structurés ignorés par B06, à côté de `*.jsonl`.

## Effets et gates

La décision résout le choix propriétaire de CF-OBS-001. Elle n'en ferme pas le finding : la fermeture exige l'implémentation et les 12/12 signaux PASS en B03. Une panne du sink ne doit jamais bloquer le runtime; elle doit exposer un état de santé et un compteur borné.

Rollback futur : revert du commit B03. La suppression de logs existants n'est pas incluse et requiert une action de rétention/destruction séparée.
