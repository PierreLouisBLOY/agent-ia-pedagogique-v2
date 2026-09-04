# Phase 12.17.7 — Minimum viable observability V2

## Cible minimale

Réutiliser les contrats structurés, bornés et privacy-safe existants. Ajouter seulement une destination locale, le câblage aux frontières atteignables et des guards pour les futures frontières. Aucun export réseau, backend SaaS, tracing distribué externe ou contenu pédagogique.

```text
OBSERVABILITY_REMEDIATION_ITEMS_COUNT = 12
OWNER_DECISION_REQUIRED = TRUE
TARGET_BATCH = 12.17.8-B03
```

Champs communs : `timestamp_utc`, `level`, `event_code`, `correlation_id`, `run_id`/`step_id` lorsque disponibles, `duration_ms`, `outcome` et `closed_error_code`. Les identifiants absents sont omis, jamais inventés.

Destination recommandée, sous réserve de décision propriétaire : fichier NDJSON dans le répertoire de données V2 résolu par configuration, sous `logs/observability.ndjson`. Publication locale uniquement, rotation à 5 MiB, cinq fichiers maximum, purge au-delà de 14 jours, flush borné à 2 s au shutdown. Les permissions suivent le même profil least-privilege que les données runtime.

Exclusions globales : credential/secret/token, prompt/réponse brute, contenu pédagogique, corps/query HTTP, row SQLite, chemin absolu, username, variable d'environnement brute, stack trace et message d'exception non classifié.

## Matrice des signaux

| # | Signal | Level | Champs spécifiques minimaux | Exclusions supplémentaires | Destination / rétention | Test d'acceptation |
|---:|---|---|---|---|---|---|
| 1 | Startup | INFO ou ERROR | `app_version`, `config_profile_id`, `sink_health`, `runtime_mode` | valeurs de configuration et chemins | destination locale approuvée; 14 j/5×5 MiB | un événement unique; config invalide produit seulement un code fermé |
| 2 | Shutdown | INFO ou WARNING | `flush_outcome`, `dropped_event_count`, `duration_ms` | contenu du buffer | même destination; flush ≤2 s | flush borné; sink indisponible n'empêche pas l'arrêt |
| 3 | HTTP request/error | INFO pour succès, WARNING/ERROR pour rejet/5xx | `method`, `route_template`, `status_class`, `duration_ms`, `correlation_id` | URL brute, query, headers, cookies, body, IP | même destination si HTTP existe; politique identique | guard actuel constate absence de serveur; future fixture refuse champs sensibles et route brute |
| 4 | Validation rejection | WARNING | `boundary`, `rule_code`, `field_code`, `correlation_id` | valeur rejetée et payload | même destination | chaque rejet a un code fermé; aucune valeur d'entrée sérialisée |
| 5 | SQLite bootstrap | INFO ou ERROR | `schema_version`, `seed_identity_digest`, `runtime_identity_digest`, `outcome` | chemins et données | même destination | succès/échec simulés; digests opaques et seed pre/post identique |
| 6 | SQLite migration | INFO ou ERROR | `from_version`, `to_version`, `migration_id`, `migration_checksum`, `outcome` | SQL et rows | même destination | une séquence autorisée et un checksum invalide produisent les bons événements fermés |
| 7 | Backup/recovery | INFO, WARNING ou ERROR | `operation`, `artifact_digest`, `authentication_outcome`, `outcome` | destination/source, contenu DB | même destination | backup/restore temporaires émettent digest et résultat sans chemin |
| 8 | Provider attempt | INFO | `provider_id`, `model_profile_id`, `call_id`, `authorization_id`, `attempt_number=1` | prompt, projection, API key, endpoint | même destination; aucune télémétrie réseau | transport fake prouve exactement un événement avant appel et aucun retry |
| 9 | Provider success | INFO | `provider_id`, `call_id`, `input_tokens`, `output_tokens`, `cost_usd`, `duration_ms` | réponse et contenu transféré | même destination | fake succès; coûts/tokens bornés et aucune réponse brute |
| 10 | Provider failure | ERROR | `provider_id`, `call_id`, `provider_error_code`, `duration_ms`, `authorization_consumed` | message/corps fournisseur, credential | même destination | fake échec; code fermé, one-shot consommé et aucune fuite |
| 11 | Security-relevant rejection | WARNING | `boundary`, `policy_code`, `correlation_id` | chemin ou valeur rejetée, détails d'attaque | même destination | traversal/credential-like/authority-key produisent uniquement la classification fermée |
| 12 | Unhandled exception | ERROR | `boundary`, `exception_class_code`, `correlation_id`, `shutdown_required` | `str(exception)`, repr, stack et locals | même destination | top-level fake produit un code fermé puis termine sans fuite |

## Option set propriétaire

- **OBS-A — fichier NDJSON local rotatif (recommandé)** : cible ci-dessus, portable, testable hors réseau et cohérente avec le serializer existant.
- **OBS-B — facility système native** : Windows Event Log/journald via adaptateurs distincts; plus de permissions, de variabilité et de surface de test. Cette option augmente le scope et exige un nouveau design détaillé avant B03.

`stderr` seul ne satisfait pas l'exigence de diagnostic durable et n'est pas une option de clôture.

## Contraintes d'implémentation

- le sink est injecté depuis la composition, jamais découvert depuis le métier ;
- les modules Domain/Application n'importent aucun logger concret ;
- une panne du sink reste failure-isolated et incrémente un compteur borné ;
- les appels fournisseurs sont testés par doubles; `PROVIDER_CALLS = 0` pendant 12.17.8 ;
- tant que le serveur HTTP n'existe pas, seul le contrat/guard est ajouté et aucun framework n'est introduit.

`OBSERVABILITY_MINIMUM_TARGET = PASS_AFTER_OWNER_POLICY_AND_12_TEST_ITEMS`
