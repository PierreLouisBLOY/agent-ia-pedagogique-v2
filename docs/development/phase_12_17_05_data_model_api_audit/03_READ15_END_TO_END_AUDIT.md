# Phase 12.17.5 — Audit end-to-end Resource READ-15

```text
READ15_DATA_MODEL_ALIGNMENT = PARTIAL
READ15_API_HANDOFF_READINESS = BLOCKED
```

## Chaîne active

`resource_ref` traverse `GetResourceRequest`,
`ResourceLibraryUseCaseInbound`, `GetResourceQuery`, `ResourceStorePort`, puis
`SQLiteResourceStoreAdapter`. La composition ouvre le runtime en lecture seule.
L'adapter traduit la ligne SQLite en `ResourceRecord`; aucune `sqlite3.Row` ne
franchit le port. `ResourceView` puis l'inbound limitent la réponse à quatre
chaînes : `resource_ref`, `resource_type`, `canonical_title` et
`identity_status`.

| Exigence | Preuve | Verdict |
|---|---|---|
| entrée active = `resource_ref` seul | DTO + contrôle exact de `set(request.payload)` | PASS |
| `version_ref` absent/déprécié | DTO absent, B09 `DEPRECATED_FOR_ACTIVE_READ15` | PASS |
| `include` absent/déprécié | DTO absent, B09 `DEPRECATED_FOR_ACTIVE_READ15` | PASS |
| query Application canonique | `GetResourceQuery.get_resource` | PASS |
| port read-only logique | `ResourceStorePort.load_resource` | PASS |
| adapter SQLite | `SQLiteResourceStoreAdapter`, composition `readonly=True` | PASS |
| not-found | `RES_NOT_FOUND`, bloquant, non retryable | PASS |
| erreurs déterministes | messages fermés, mais borne de `resource_ref` non définie | PARTIAL |
| données minimisées | `ResourceView` quatre champs | PASS |
| couverture tests | unit, intégration, architecture et réel SQLite | PARTIAL |
| handoff B09 | méthode, route, délégation, erreurs et local-browser définis | PARTIAL |

## Écarts

1. `resource_ref` est seulement non vide. Ni le DTO Application ni le handoff
   HTTP ne définissent de longueur maximale ou de format, alors que le design
   exige une référence validée et bornée avant l'inbound.
2. `identity_status` expose deux valeurs volontairement distinctes, `ACTIVE` et
   `CANONICAL`, sans sémantique métier univoque. READ-15 est techniquement
   décodable, mais son contrat public ne peut pas encore expliquer ce champ sans
   inventer une règle.
3. Il n'existe pas de test négatif direct de l'inbound pour un champ inconnu ou
   déprécié. Les guards B09 testent le handoff documentaire, pas une validation
   de transport matérialisée.

Le modèle et la chaîne Application sont utilisables. La readiness HTTP reste
`BLOCKED` jusqu'à décision explicite sur la borne de référence et sur la
sémantique publiée de `identity_status`.
