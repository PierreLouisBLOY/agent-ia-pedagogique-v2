# ADR-P12-040 — Frontière de sécurité multi-agent

## Statut

Accepté pour la Phase 12.12-E.

## Contexte

Les contrats `DelegationEnvelope`, `AgentInvocation`, `AgentResult` et
`DelegationResult` transportaient déjà les identités, scopes et métadonnées
nécessaires à une exécution provider-neutral. La corrélation locale restait
cependant insuffisante pour prouver à une seule frontière que le producteur,
l'invocation, la délégation, le scope et le contenu provenaient tous du même
handoff autorisé.

L'architecture canonique reste :

```text
AG-01 = Orchestrator / Planner, unique owner de la délégation
AG-02 = Retrieval / Evidence
AG-03 = Generator / Transformer
AG-04 = Reviewer / Critic, jamais Validator métier
```

Les spécialistes n'acquièrent aucune autorité métier, Tool, Application,
Gate, Runtime ou Recovery.

## Audit des sources d'autorité et de lignée

| Fait | Source canonique | Contrôle E |
| --- | --- | --- |
| owner de délégation | registre AG-01 + access matrix | `source_agent == AG-01`, creator de l'invocation déléguée AG-01 |
| target/capability | `StepSpec`, registry et access matrix | executor, target, owner et capability exacts |
| child scope | `PermissionScope` | capability unique, principal target, non-redélégable, puis évaluation canonique parent/enfant |
| identité de tentative | `AgentInvocation` | invocation ID et step exacts |
| producteur | `AgentResult.meta.actor` | `producer_agent` dérivé, jamais fourni par le payload |
| résultat délégué | `DelegationResult` | envelope, delegation ID, source et step exacts |
| lignée | `ContractMeta` | schema, run, step, parent step et correlation exacts |
| références | champs typés du résultat/envelope | couverture Evidence AG-03/04 et interdiction de substitution par payload |

`delegation=None` reste légitime pour un résultat direct et est exposé par
`DelegationResult.is_delegated`. La boundary sécurisée, elle, n'accepte que la
voie déléguée avec envelope présent des deux côtés.

## Décision

### Contrats

`DelegationEnvelope` porte explicitement `source_agent=AG-01` et une profondeur
spécialiste égale à 1. Son scope contient exactement la capability du step et
reste non-redélégable. La borne runtime historique n'est pas augmentée.

`AgentInvocation` exige AG-01 comme acteur lorsqu'un envelope est présent.
`AgentResult` exige un acteur agent canonique et dérive le producteur depuis
les métadonnées immuables. `DelegationResult` vérifie ce producteur contre son
`source_agent` avant toute corrélation optionnelle à l'envelope.

### Boundary de handoff

`AgentHandoffSecurityPolicy` est une policy pure de validation. Elle ne crée
pas une nouvelle autorité : elle compose
`CapabilityAuthorizationPolicy.evaluate_delegation`, donc le même
`DelegationScopePolicy` et le même évaluateur de `PermissionScope` que la
baseline.

Elle refuse sans correction silencieuse :

- délégateur autre qu'AG-01 ;
- envelope absent, modifié ou réutilisé pour une autre invocation ;
- producteur, target, capability ou identité de tentative divergents ;
- run, step, parent step ou correlation divergents ;
- scope enfant élargi, principal incorrect, parent inactif/révoqué ou
  redélégation ;
- références Evidence hors envelope pour AG-03/AG-04 ;
- clés structurelles d'autorité ou de substitution dans le contexte, payload,
  warnings, metrics, détails d'erreur ou stop reason.

AG-02 peut produire de nouvelles références Evidence dans son rôle
propriétaire ; cette exception n'autorise ni substitution par payload ni
conversion automatique d'un résultat en preuve canonique.

### Contenu et provenance

Le classifieur structurel D et la policy instruction/data C sont réutilisés.
Les vocabulaires spécialisés E restent locaux à la boundary. Les sorties sont
étiquetées selon leur origine réelle :

```text
AG-02 ou génération AG-03 -> AGENT_OUTPUT
AG-04                     -> REVIEW_OUTPUT
CAP-G03                   -> CORRECTION_OUTPUT
role                      -> RESULT
trust maximum             -> STRUCTURALLY_VALIDATED
```

Ce trust décrit uniquement une forme et une provenance. Il ne signifie jamais
permission, gate, promotion, vérité métier ou validation de domaine.
`AgentResultStatus.SUCCEEDED` reste un statut technique.

Une clé structurelle telle que `permissionScope`, `gateDecision`,
`promotionAllowed`, `validator`, `artifactRefs` ou `evidenceRefs` est refusée.
Les mêmes mots dans une citation, un exercice, du code ou une analyse restent
du texte isolé comme donnée et ne sont pas interprétés comme des faits.

## Review et correction

Le handoff de review existant reste destiné exactement à AG-01. Les
`suggested_actions` n'ont pas de champ exécutable `allowed_changes` et ne sont
jamais transformées automatiquement en `CorrectionRequest`. AG-01 reste
responsable d'une éventuelle décision de planification. La préparation
CAP-G03 conserve le contrôle exact de `review_ref`, findings, target version,
Evidence et contraintes ; une perte de lignée échoue fermé.

AG-04 reste `REVIEWER_CRITIC`. Les textes « review passed », « validated
output » ou une suggestion ne peuvent fournir ni validation métier, ni gate,
ni promotion.

## Événements et erreurs sûres

La boundary réutilise `SecurityEvent` :

```text
mismatch de handoff       -> AGENT_HANDOFF_VIOLATION
clé d'autorité            -> AUTHORITY_SMUGGLING
scope/producteur/trust    -> TRUST_BOUNDARY_VIOLATION
contenu agent suspect     -> INDIRECT_CONTENT_INJECTION
propagation explicitement hostile -> HOSTILE_CONTENT_PROPAGATION
```

Les erreurs n'exposent qu'un code fermé. Les événements contiennent identifiants,
refs, label, compteurs et codes ; jamais payload, prompt, finding, warning ou
sortie brute. Aucun sink ou logger n'est ajouté.

## Invariants

```text
ONLY_AG_01_MAY_CREATE_OR_AUTHORIZE_DELEGATION
SPECIALIST_CHILD_SCOPE_IS_NON_REDELEGABLE
DELEGATED_RESULT_HAS_EXACT_INVOCATION_AND_LINEAGE
AGENT_RESULT_PRODUCER_COMES_FROM_IMMUTABLE_META
AGENT_SUCCEEDED_IS_NOT_DOMAIN_VALIDATED
AGENT_OUTPUT_NEVER_BECOMES_PERMISSION_OR_GATE_FACT
AG_04_REMAINS_REVIEWER_CRITIC
SUGGESTED_ACTION_IS_NON_AUTHORITATIVE
CONTENT_TRUST_NEVER_CONFERS_CONTROL_AUTHORITY
SECURITY_EVENT_NEVER_CARRIES_RAW_AGENT_CONTENT
```

## Frontières différées

E n'ajoute aucun scanner de valeurs secrètes, aucune limite globale, aucune
intégration security au runtime/recovery et aucune observabilité. Les owners
Tool, Application et Gate restent inchangés. Aucune dépendance runtime n'est
introduite.

## Rationalisation

L'évaluateur de scope, la policy de capability, le classifieur structurel, la
policy instruction/data, les labels et les événements sont réutilisés. Les
contrats et handoffs spécialisés ont des cycles de vie et propriétaires
distincts ; aucune autre fusion ne conserve tous leurs invariants.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
