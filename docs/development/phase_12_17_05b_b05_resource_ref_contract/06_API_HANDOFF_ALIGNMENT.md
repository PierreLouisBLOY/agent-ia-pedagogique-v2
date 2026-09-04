# Phase 12.17.5B-B05 — Alignement du handoff API

Le handoff B09 reste immuable et conserve :

```text
HTTP_METHOD = GET
HTTP_ROUTE = /api/v2/resources/{resource_ref}
PATH_PARAMETERS = resource_ref
QUERY_PARAMETERS = NONE
API_ENDPOINT_IMPLEMENTED = FALSE
DIRECT_SQL_AUTHORIZED = FALSE
```

Le futur adapter HTTP doit construire `ResourceRef` via l'inbound Application.
Il consomme donc la regex et la borne canonique du Domain sans définir de
validator alternatif. L'erreur `InvalidResourceRefError` appartient au mapping
d'entrée invalide; `RES_NOT_FOUND` reste le résultat distinct d'une référence
valide mais absente.

Les champs `version_ref` et `include` restent
`DEPRECATED_FOR_ACTIVE_READ15`. Les tests prouvent qu'ils sont absents du DTO,
absents des query parameters du handoff et rejetés à l'exécution comme champs
non supportés.

```text
API_HANDOFF_STATUS = ALIGNED
API_ENDPOINT_IMPLEMENTED = FALSE
VERSION_REF_STATUS = DEPRECATED_REJECTED
INCLUDE_STATUS = DEPRECATED_REJECTED
PREVIOUS_B09_EVIDENCE_MODIFIED = FALSE
```
