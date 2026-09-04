# Phase 12.17.5B-B05 — Propagation Domain/Application/persistence

## Domain

`ResourceRef` et `InvalidResourceRefError` sont définis sous
`backend/modules/resource_library/domain/`. Ils n'importent ni infrastructure,
ni adapter, ni SQLite.

## Application et READ-15

- `GetResourceRequest.resource_ref` est un `ResourceRef` ;
- `ResourceView.resource_ref` est un `ResourceRef` ;
- `ResourceRecord.resource_ref` et `ResourceStorePort.load_resource` utilisent
  le même type ;
- `GetResourceQuery` transmet le Value Object au port et ne transforme que sa
  valeur pour la référence générique d'outcome ;
- une référence invalide échoue avant le premier lookup ;
- une référence valide absente continue de produire `RES_NOT_FOUND`.

## Adapters et persistence

L'inbound vérifie d'abord la forme exacte du payload, construit le Value Object
Domain, puis appelle l'Application. L'adaptateur SQLite exige ce Value Object,
transmet sa valeur sans modification au store C0 et revalide les identités lues
en reconstruisant `ResourceRef`.

Le store SQL C0 reste un primitive de persistence interne : aucune regex n'y
est ajoutée et aucune contrainte DB n'est inventée.

```text
DOMAIN_STATUS = PASS
APPLICATION_STATUS = PASS
PERSISTENCE_STATUS = PASS
INVALID_REF_LOOKUP_COUNT = 0
NOT_FOUND_REMAINS_DISTINCT = TRUE
SQLITE_CONSTRAINT_ADDED = FALSE
DATA_VALUE_MUTATION = FALSE
```
