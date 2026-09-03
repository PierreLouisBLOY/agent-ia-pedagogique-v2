# Phase 12.17.4E-B09 — Dépréciation READ-15

```text
resource_ref = REQUIRED_PATH_PARAMETER
version_ref = DEPRECATED_FOR_ACTIVE_READ15
include = DEPRECATED_FOR_ACTIVE_READ15
UNKNOWN_OR_DEPRECATED_FIELD_POLICY = CLOSED_VALIDATION_ERROR
```

Le contrat actif ne comporte aucune query string. `version_ref` et `include`
ne doivent figurer ni dans le DTO, ni dans OpenAPI, ni comme options ignorées.

Une réintroduction exige un nouveau contrat versionné, une justification
consommateur, des tests et, si la forme de données le requiert, une preuve du
data model. Elle ne peut pas être ajoutée silencieusement au READ-15 courant.
