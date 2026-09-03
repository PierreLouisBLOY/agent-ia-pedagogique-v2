# Phase 12.17.4E-B09 — Handoff API v2 Resource READ-15

```text
PHASE_12_17_5_API_SCOPE = RESOURCE_READ_15_ONLY
HTTP_METHOD = GET
HTTP_ROUTE = /api/v2/resources/{resource_ref}
API_ENDPOINT_IMPLEMENTED_IN_B09 = FALSE
API_AUTHORITY = APPLICATION
DIRECT_SQL_AUTHORIZED = FALSE
```

Le futur adapter HTTP valide un unique path parameter `resource_ref`, construit
la requête C-12 `application.read_canonical_resource`, puis appelle l'inbound
injecté `ResourceLibraryUseCaseInbound`. Celui-ci délègue au contrat existant
`GetResourceQuery.get_resource`; la chaîne Application/OP-03 reste seule
autorité de lecture.

La réponse nominale HTTP 200 est limitée aux quatre champs de `ResourceView` :
`resource_ref`, `resource_type`, `canonical_title`, `identity_status`.
`RES_NOT_FOUND` est projeté en 404. Une entrée invalide, inconnue ou dépréciée
est projetée en 400 fermé. Une failure Application devient une erreur 500
générique sans SQL, chemin, stack, secret ni payload brut.

L'API n'ouvre jamais SQLite, n'importe aucun repository, ne construit pas la
composition et n'expose aucune route Production, validation ou promotion. La
réalisation et les tests HTTP/OpenAPI appartiennent exclusivement à 12.17.5.
