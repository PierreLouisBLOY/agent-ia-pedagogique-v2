# Phase 12.17.5B-B06 — Alignement Domain / Application

Le Domain possède `ResourceSemanticState` et les deux vocabulaires séparés.
`ResourcePersistenceValues` ne transporte plus un `identity_status` ambigu,
mais le Value Object sémantique. Le port OP-03 expose également ce Value Object
et ne dépend d'aucun type SQLite, HTTP, ORM ou SDK fournisseur.

La query READ-15 projette uniquement la disponibilité prouvée. `ResourceView`
expose `availability_status`; ni `identity_status`, ni canonicalité inconnue ne
franchissent la frontière inbound. Le read model OP-12 suit la même règle.

Aucun use case de transition n'existe dans le périmètre courant. B06 n'en crée
pas en l'absence d'une autorité métier et d'un contrat de transition approuvés.

```text
DOMAIN_SEMANTIC_STATE = IMPLEMENTED
OUTBOUND_PORT_ALIGNMENT = PASS
APPLICATION_QUERY_ALIGNMENT = PASS
APPLICATION_TRANSITION_USE_CASES = NONE_AUTHORIZED
HTTP_OR_ORM_TYPES_IN_CONTRACTS = 0
```
