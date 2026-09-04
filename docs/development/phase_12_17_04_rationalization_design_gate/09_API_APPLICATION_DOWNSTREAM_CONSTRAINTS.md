# Phase 12.17.4 — Contraintes Application/API aval

## Portée

Ce document propage OD-03, OD-04 et OD-07 vers 12.17.5. Il ne crée aucun use
case, route HTTP ou migration pendant 12.17.4.

## OD-03 — Trois owners Application

| Capacité | Opération | Owner | Nature | Prérequis |
|---|---|---|---|---|
| `CAP-R02` | `application.read_production` | `work_orchestration` Application, lecture Production | query read-only | port outbound typé et modèle de lecture Production |
| `CAP-A01` | `application.run_deterministic_validation` | `validation_control` Application | commande déterministe, sans provider | règles/invariants Domain et résultat fermé |
| `CAP-A02` | `application.request_promotion` | `lifecycle_promotion` Application | commande à effet derrière Gate | décision Gate préexistante, idempotency/effect ledger |

L'ordre de livraison est `CAP-R02 -> CAP-A01 -> CAP-A02`. Le registre de
capabilities et le routeur restent des métadonnées/dispatch ; ils ne sont pas
les owners des règles. Les agents accèdent à ces opérations uniquement par une
frontière inbound Application.

## OD-04 — Premier `/api/v2`

Le premier slice HTTP prévu est uniquement le lookup Resource READ-15 :

```text
GET /api/v2/resources/{resource_ref}
  -> API input mapper
  -> ResourceLibraryUseCaseInbound
  -> GetResourceQuery
  -> ResourceStorePort
  -> SQLiteResourceStoreAdapter (read-only runtime DB)
  -> ResourceView
  -> API output mapper
```

La route n'ouvre jamais SQLite, n'importe aucun repository et ne construit pas
le use case. La composition lui injecte l'inbound existant. Aucun endpoint de
production, validation ou promotion n'est autorisé par OD-04 Option A.

## OD-07 — Contrat READ-15

L'entrée active contient exactement `resource_ref`. `version_ref` et `include`
sont dépréciés et ne doivent apparaître ni dans le DTO, ni dans la query string,
ni dans le schéma OpenAPI, ni comme option silencieusement ignorée.

Un client qui les envoie reçoit une erreur de validation fermée conformément au
futur contrat HTTP. Leur réintroduction exige un nouveau use case et une nouvelle
version de contrat ; elle ne peut pas être ajoutée comme paramètre optionnel du
READ-15 actuel.

## Contraintes sécurité et données

- le Resource lookup est read-only sur la runtime DB, jamais sur le seed ;
- les refs sont validées et bornées avant l'inbound ;
- les erreurs ne divulguent ni chemin SQLite, SQL, stack, secret ou payload ;
- `RES_NOT_FOUND` reste un résultat Application explicite ;
- l'API n'accorde aucune permission, validation ou promotion ;
- aucune `sqlite3.Row` ou type provider ne traverse Application/API.

## Acceptation 12.17.5

1. un seul endpoint `/api/v2` matérialisé : Resource READ-15 read-only ;
2. test nominal et `RES_NOT_FOUND` via l'inbound Application ;
3. tests négatifs pour `version_ref`, `include` et champ inconnu ;
4. test d'architecture interdisant SQL/repository dans l'API ;
5. OpenAPI aligné sur `resource_ref` seul ;
6. CAP-R02/A01/A02 restent séparés et ne sont pas exposés par opportunisme ;
7. aucune migration attendue pour ce premier slice.

`PHASE_12_17_5_API_SCOPE = RESOURCE_READ_15_ONLY`.
