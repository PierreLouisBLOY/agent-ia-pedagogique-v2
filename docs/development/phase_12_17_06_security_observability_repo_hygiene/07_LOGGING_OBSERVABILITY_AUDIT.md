# Phase 12.17.6 — Logging, privacy et observabilité

## Capacités présentes

Le socle définit logs, spans et métriques structurés avec timestamp UTC, niveau, code fermé, correlation ID, run/step IDs et trace context. La sérialisation NDJSON est déterministe, limitée à 65 536 octets et passe par le classifieur de valeurs sensibles. Les labels métriques à haute cardinalité sont interdits par contrat. Les buffers sont bornés et non bloquants ; les échecs de sink sont isolés et exposent un état de santé.

Les wrappers couvrent les étapes runtime, application, outils, agents, gates et recovery. La calibration dispose d'événements `BLOCKED`, `STARTED`, `FAILED`, `COMPLETED`, contenant uniquement identités opaques, durée, tokens/coût et code fermé.

## Écarts de câblage

Les sinks persistants ne sont instanciés que dans les tests. L'infrastructure fournit seulement un writer sur stream injecté et ne possède ni chemin, ni rotation, ni rétention. La calibration choisit un `NullCalibrationTelemetrySink` par défaut. Aucun composition root applicatif ne câble startup, shutdown, bootstrap/migration SQLite, backup, appels fournisseurs ou exceptions non gérées vers une destination locale.

Les contrats protègent les contenus observés contre les credentials et chemins privés, mais l'absence de sink effectif rend le diagnostic de production incomplet. Aucun prompt, réponse brute ou contenu pédagogique n'est implicitement journalisé par les adaptateurs inspectés.

## Verdicts

`OBSERVABILITY_READINESS = PARTIAL`

`LOGGING_PRIVACY_STATUS = PASS_CONTRACTS_NOT_WIRED`

Une décision propriétaire est requise sur la destination locale, la rotation/rétention, les événements minimaux et le comportement de flush au shutdown. Le contenu pédagogique et les prompts/réponses doivent rester exclus par défaut.
