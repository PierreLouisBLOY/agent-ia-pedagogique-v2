# ADR-P12-039 — Frontière de sécurité Tool et Application

## Statut

Accepté pour la Phase 12.12-D.

## Contexte

Les frontières Tool et Application reçoivent et produisent des mappings libres
dont le texte doit rester exploitable comme donnée, sans pouvoir redéfinir les
faits de permission, de gate, de routage, de sandbox ou de recovery. Les lots B
et C fournissent déjà les labels de provenance, les événements minimisés et la
policy pure d'isolation instruction/data. D doit les composer avec les owners
existants, sans créer une nouvelle autorité.

L'audit localise les sources canoniques Tool comme suit :

| Fait | Source autoritaire | Transport/exécution |
| --- | --- | --- |
| `tool_id`, `capability_id`, arguments, scope, timeout, idempotency | `ToolCallRequest` | reconstruits et évalués par `ToolCallPolicy` |
| métadonnées statiques, contrats, effet, sandbox | `ToolDescriptor` dans `ToolRegistry` | vérifiés par `ToolRouter` |
| target/binding filesystem | `ToolRoutingContext` + `SandboxOutputTarget` | décisions du `SandboxPolicy` existant |
| binding exécuteur | `ToolExecutorBindings` | résolution exacte par `tool_id` |
| résultat, chemins produits | `ToolExecutionOutcome` + `ToolCallResult` | identité, forme, sandbox post-exécution et sécurité du contenu |

Les sources Application sont :

| Fait | Source autoritaire | Transport/exécution |
| --- | --- | --- |
| `use_case_id`, payload, intention d'effet, idempotency | `UseCaseRequest` | validés avant routage |
| capability, executor, output contract | `UseCaseRoutingContext.step` | contexte trusted fourni au router |
| permission et policy facts | `UseCaseRoutingContext` | `CapabilityAuthorizationPolicy` produit `REQUEST` |
| contrats et capability statiques | `UseCaseDescriptor` dans `UseCaseRegistry` | liés au contexte par `UseCaseRouter` |
| binding Application | `UseCaseInboundBindings` | résolution exacte de l'`ApplicationInboundPort` |
| résultat métier et technique | `UseCaseResult`, `ApplicationOutcome`, `ApplicationFailure`, `ErrorEnvelope`, domain events | reconstruction typée et contrôle post-invocation |

Les timeouts Tool restent bornés par le descriptor et décidés par
`ToolCallPolicy`. L'idempotency reste un prérequis de routage. D ne lit, ne
produit et ne modifie aucun ledger ou fait de recovery.

## Rationalisation des clés structurelles

| Source auditée | Vocabulaire spécialisé | Partie commune sûre | Owner conservé |
| --- | --- | --- | --- |
| arguments Tool | identité Tool/capability, permission, gate, provider/handler, sandbox, target/binding, owner/route, policy et faits 12.11 | normalisation et recherche récursive de clés | `ToolCallPolicy` pour `ALLOW/DENY` ; `ToolRouter` pour la frontière d'exécution |
| payload Application | capability, permission, gate, promotion, provider/handler/executor, override, owner/route/target et faits 12.11 | même classification structurelle | `UseCaseRouter` et `CapabilityAuthorizationPolicy` |
| `requested_effect` | vocabulaire payload plus succès, commit et preuve d'effet | même classification structurelle | `UseCaseRouter` ; le champ reste une intention |
| Gate | authority, gate, actor, expiration et policy facts | même classification structurelle | `GateEngine` et `GateAuthorityPolicy` |
| isolation C | capability, permission, gate, provider/handler, owner/route/target | même classification structurelle | `InstructionDataBoundaryPolicy` |
| safe mapping | secrets, credentials/tokens, SQL, stack traces, provider payload, chemins locaux/filesystem et raisonnement privé | aucune décision commune supplémentaire | `freeze_safe_mapping` / `freeze_agent_safe_mapping` |

La normalisation commune reconnaît snake case, camel case, kebab case,
séparateurs et formes compactes, puis retourne uniquement des positions
logiques. Elle ne contient aucune disposition et ne sait pas autoriser,
router, promouvoir ou exécuter. Les listes spécialisées restent locales à
leurs propriétaires.

## Décision Tool

`ToolCallPolicy` demeure l'unique propriétaire de `ALLOW/DENY`. Son vocabulaire
d'arguments interdit est exposé comme constante canonique et réutilise le
classifieur structurel commun. `ToolRouter` compose cette décision sans la
remplacer : il vérifie les identités, le contexte, les contrats, le sandbox et
les bindings exacts.

Les deux tools routables possèdent déjà des IDs de contrats statiques dans
leurs descriptors. D les compare à la baseline canonique avant toute
exécution. La forme runtime est ensuite reconstruite au moyen des contrats
typés existants ; aucun registre JSON Schema ou framework générique n'est
introduit. Un mismatch d'ID ou de structure échoue fermé.

Les arguments reçoivent un `StructuredContentSecurityAssessment`. Une clé
structurelle interdite est refusée ; un texte pédagogique ou impératif reste
une donnée isolée par la policy C et ne modifie pas l'autorisation.

Tout `ToolCallResult` porte exactement une provenance
`TOOL_OUTPUT / RESULT / UNTRUSTED`. Output, metrics, message et détails d'erreur
sont évalués par composition de C. Une clé structurelle d'autorité dans le
résultat est invalide. Un texte hostile reste isolé et ne devient ni
instruction système, permission, gate, capability, target, ni Evidence.

```text
TOOL_OUTPUT_IS_NEVER_EVIDENCE_BY_DEFAULT
```

Le `SandboxPolicy` existant demeure unique. Ses décisions pré/post-exécution,
ses profils et ses contrôles de chemins ne sont ni dupliqués ni affaiblis.

## Décision Application

`CapabilityAuthorizationPolicy` demeure l'autorité partagée et
`UseCaseRouter` l'unique owner du routage Application. Le payload et
`requested_effect` reçoivent chacun une évaluation structurée avant toute
invocation inbound. Le premier ne peut redéfinir aucun fait d'autorité ou de
recovery ; le second ne peut en plus affirmer succès, commit ou preuve d'effet.

Les descriptors canoniques `C-12`/`C-13` sont contrôlés avant l'invocation et
le binding `use_case_id` lie exactement le descriptor au port inbound. Le
contrat de sortie générique du plan reste distinct du contrat de frontière
Application. Les contrats
`UseCaseRequest`, `UseCaseResult`, `ApplicationOutcome`, `ApplicationFailure`,
`BusinessError` et `ErrorEnvelope` sont reconstruits après invocation. Il
s'agit d'une validation de frontière, jamais d'une validation métier.

Le contenu libre de data, validation result, side effects, domain events,
failures et errors porte une provenance
`APPLICATION_OUTPUT / RESULT / UNTRUSTED` et une évaluation C. Une affirmation
textuelle de permission ou de succès reste une donnée ; une clé structurelle
qui cherche à fournir une autorité runtime est refusée.

## Propagation hostile et événements

Les résultats Tool/Application transportent leur label et leur assessment vers
les prepared inputs Generation/Review. Les deux éléments doivent couvrir les
mêmes refs ; un label seul, une origine altérée ou une promotion de confiance
est refusé. Aucun chemin D ne construit un `EvidenceItem`. Toute candidature
Evidence doit passer ultérieurement par ses owners de provenance.

Le mapping pur réutilise `SecurityEvent` et ne copie aucun argument, payload ou
résultat brut :

```text
clé structurelle interdite -> AUTHORITY_SMUGGLING
contenu hostile Tool       -> TOOL_INJECTION
contenu hostile Application-> APPLICATION_INJECTION
propagation hostile        -> HOSTILE_CONTENT_PROPAGATION
confusion de frontière     -> TRUST_BOUNDARY_VIOLATION
```

`PASS_AS_DATA` et `ISOLATE_AS_DATA` ne créent pas automatiquement un événement
sans contexte d'escalade. Le mapping n'est ni un logger ni une nouvelle
autorité.

## Invariants

```text
TOOLCALLPOLICY_REMAINS_UNIQUE_TOOL_AUTHORIZATION_OWNER
USECASEROUTER_REMAINS_UNIQUE_APPLICATION_ROUTING_OWNER
CONTENT_NEVER_CONFERS_CONTROL_AUTHORITY
REQUESTED_EFFECT_IS_INTENT_NOT_EFFECT_FACT
TOOL_APPLICATION_OUTPUT_REMAINS_UNTRUSTED
TOOL_OUTPUT_IS_NEVER_EVIDENCE_BY_DEFAULT
HOSTILE_RESULT_PROPAGATION_PRESERVES_LABEL_AND_ASSESSMENT
SECURITY_EVENT_NEVER_CARRIES_RAW_CONTENT
SANDBOXPOLICY_REMAINS_UNIQUE
RECOVERY_FACTS_REMAIN_OWNED_BY_12_11
```

## Portée différée

D ne modifie aucun handoff ou `DelegationResult` de 12.12-E, n'ajoute aucun
scanner de valeurs secrètes ou limite globale de 12.12-F, n'intègre aucune
policy au runtime/recovery de 12.12-G et n'ajoute aucun sink d'observabilité de
12.13. Aucune dépendance runtime n'est introduite.

## Conséquences

La provenance et les évaluations de contenu deviennent explicites aux deux
frontières, au prix de champs de contrat additionnels frozen/slotted et de
contrôles fail-closed. Les décisions restent chez leurs owners. Au-delà du
classifieur structurel commun, aucune fusion ne satisfait simultanément les
critères de sémantique, invariants, autorité et cycle de vie.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
