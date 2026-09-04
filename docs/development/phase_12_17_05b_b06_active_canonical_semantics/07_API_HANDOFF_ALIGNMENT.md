# Phase 12.17.5B-B06 — Alignement handoff API

Le payload transport-neutral READ-15 devient :

```text
resource_ref
resource_type
canonical_title
availability_status
```

`identity_status` est retiré de ce handoff actif. `canonicality_status` reste
absent, car aucune canonicalité n'est prouvée pour les données existantes et
aucun contrat public versionné de cette dimension n'est autorisé. Les champs
`version_ref` et `include` restent dépréciés et rejetés conformément à B05.

Les preuves B09 historiques ne sont pas réécrites rétroactivement. Le présent
document constitue l'alignement B06 pour le futur audit de gate. Aucun endpoint
HTTP, schéma OpenAPI ou route supplémentaire n'est implémenté.

```text
READ15_IDENTITY_STATUS_EXPOSED = FALSE
READ15_AVAILABILITY_STATUS_EXPOSED = TRUE
READ15_CANONICALITY_STATUS_EXPOSED = FALSE
READ15_UNKNOWN_CANONICALITY_INVENTED = FALSE
READ15_CONTRACT_HONEST = TRUE
API_ENDPOINT_IMPLEMENTED = FALSE
```
