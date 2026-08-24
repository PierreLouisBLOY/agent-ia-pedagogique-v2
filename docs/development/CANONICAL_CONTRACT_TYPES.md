# Types de contrats canoniques

## Placement

| Zone | Types | Responsabilite |
| --- | --- | --- |
| `backend/shared_kernel/identifiers/` | `TypedEntityId` | Identite generique typee |
| `backend/shared_kernel/references/` | `TypedEntityRef`, `VersionRef`, `ObjectVersionRef` | References d'identite et de version |
| `backend/shared_kernel/correlation/` | `CorrelationId` | Correlation opaque |
| `backend/shared_kernel/errors/` | `BusinessErrorCode`, enums et `BusinessError` | Erreurs metier generiques |
| `backend/shared_kernel/time/` | `Instant`, `BusinessDate` | Valeurs temporelles fournies par l'appelant |
| `backend/core_contracts/invocation/` | `UseCaseContext` | Contexte transverse d'invocation |
| `backend/core_contracts/outcome/` | `OutcomeStatus`, `ApplicationFailure`, `ApplicationOutcome` | Resultat transverse d'un use case |
| `backend/core_contracts/capability/` | `CapabilityId` | Reference generique de capability |

Le Shared Kernel contient les primitives generiques partagees. `core_contracts` compose ces primitives
pour definir les frontieres applicatives transverses et ne depend d'aucun module metier. M09
(`backend/modules/validation_control/`) reste proprietaire de `ValidationIssue` et `ValidationResult`.
Le parametre generique de `ApplicationOutcome.validation_result` preserve cette frontiere.

## Statuts d'outcome

| `OutcomeStatus` | `success` |
| --- | --- |
| `SUCCESS` | `True` |
| `SUCCESS_WITH_WARNING` | `True` |
| `REJECTED` | `False` |
| `FAILED` | `False` |
| `INDETERMINATE` | `False` |

Une combinaison incoherente est refusee a la construction. Ce mapping n'implique aucun statut HTTP.
Chaque `ApplicationOutcome` exige un `CorrelationId`. Ses `side_effects` sont des mappings data-only,
profondement figes et soumis a la meme politique fail-closed que les details diagnostiques.
Dans `BusinessError`, `retryable` indique seulement qu'une nouvelle tentative metier peut devenir
possible apres correction du contexte ou de l'entree; il ne declenche aucun retry technique.

## Adaptation aux frontieres

La serialisation, les schemas API, JSON Schema, les modeles Pydantic et les payloads fournisseurs sont
des representations peripheriques. Ils adaptent les types canoniques sans introduire HTTP, ORM, SDK,
SQL, exceptions brutes ou secrets dans le coeur.
Les cles manifestement sensibles ou techniques sont refusees, sans redaction silencieuse. Les
references canoniques du Shared Kernel restent autorisees comme valeurs de diagnostic immuables.
Les tokens d'authentification restent interdits, tandis que les compteurs de tokens et les requetes
de recherche provider-neutral sont des metadonnees de remediation autorisees.

Les contrats runtime agentiques C-01 a C-19, les etats d'execution, le scheduler et les adaptateurs
LLM/RAG sont reportes a 12.3-C. Les registries, evaluateurs de capability et `PermissionScope`, tool
mappings et policy engine sont reportes a 12.4.
