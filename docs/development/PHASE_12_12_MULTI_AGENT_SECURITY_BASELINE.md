# Baseline Phase 12.12-E — Sécurité multi-agent

## Périmètre livré

Le lot E part directement du commit D
`acb3455d48ac4e1b6b050956c9ce8d9335fc3162` sur
`phase12/12-12-security-hardening`.

Il livre :

```text
audit invocation/délégation/résultat et handoffs spécialisés
+ exclusivité AG-01 sur la délégation
+ envelope à capability exacte, profondeur 1 et scope non-redélégable
+ producteur AgentResult dérivé de meta.actor
+ corrélation exacte invocation/result/envelope/run/step/correlation
+ réutilisation de l'évaluateur canonique parent/enfant
+ classification C/D des contextes, outputs, warnings, metrics et erreurs
+ provenance AGENT_OUTPUT/REVIEW_OUTPUT/CORRECTION_OUTPUT
+ sécurité Review -> AG-01 -> Correction
+ événements minimisés E
+ tests adversariaux et fitness d'architecture
```

Il ne livre ni scanner/limites globales F, ni intégration runtime/recovery G,
ni observabilité 12.13.

## Audit des contrats agentiques

`StepSpec` fixe le step, l'executor et la capability. `DelegationEnvelope`
relie ce step à AG-02/03/04, à un scope enfant et aux Evidence refs. Le registre
et l'access matrix conservent les owners de capability. Seul AG-01 possède la
route de délégation ; AG-02/03/04 ont uniquement leurs capabilities
spécialisées.

`AgentInvocation` représente une tentative. `AgentResult` porte la sortie,
les refs typées, warnings, metrics, error et stop reason. Son acteur meta est
désormais un agent canonique et son producteur est dérivé de ce champ immutable.
`DelegationResult` empêche donc AG-03 d'être présenté comme AG-04, ou l'inverse.

Les résultats directs avec `delegation=None` restent supportés. Un handoff
réellement délégué doit passer par `AgentHandoffSecurityPolicy` avec les deux
envelopes présents et égaux.

## Scope, identité et profondeur

L'envelope exige :

- source AG-01 ;
- target AG-02, AG-03 ou AG-04 et executor identique ;
- exactement la capability du step dans le scope enfant ;
- principal égal au target ;
- scope enfant non-redélégable ;
- profondeur spécialiste égale à 1.

La boundary appelle l'évaluation canonique de délégation. Elle contrôle donc
capabilities, resources, operations, contraintes, budget, fenêtres temporelles,
gates, deny rules et révocation sans second evaluator. La borne runtime
historique reste inchangée.

L'identité est exacte sur delegation ID, invocation ID, source/target,
capability, schema, run, step, parent step et correlation. Les divergences
échouent fermé sans réécriture.

## Contenu inter-agent

La classification structurelle D est appliquée récursivement à
`context_slice`, payload, warnings, metrics, détails d'erreur et stop reason.
Ces mappings ne peuvent fournir owner, identité agent, capability, permission,
gate, policy facts, promotion/validator, provider/handler, runtime override,
recovery facts ni substituer les refs/l'identité du handoff.

La policy C inspecte séparément les feuilles textuelles. Une revendication
« gate approved » ou « promotion allowed » reste une donnée isolée ; elle ne
devient pas un fait. Une mention pédagogique de `permission`, `gate`,
`capability_id` ou `validator` dans une citation, un exercice ou du code reste
acceptée comme texte.

Les labels effectifs sont `AGENT_OUTPUT`, `REVIEW_OUTPUT` ou
`CORRECTION_OUTPUT`, avec role `RESULT`. `STRUCTURALLY_VALIDATED` est une borne
descriptive, jamais une autorisation. Ni `SUCCEEDED`, ni un texte « approved »,
ni un résultat de review ne déclenchent validation métier, gate ou promotion.

## Review vers correction

AG-04 reste `REVIEWER_CRITIC`. Le signal de correction retourne à AG-01 avec
review ref, review ID, target version, finding IDs, blocking IDs et Evidence
refs. Les suggestions sont immuables et descriptives ; elles ne possèdent pas
le champ `allowed_changes` d'une requête de correction et ne sont jamais
auto-exécutées.

La préparation CAP-G03 existante contrôle ensuite la target version et la
lignée complète de la requête explicitement planifiée. Un target différent ou
une perte de lignée est refusé.

## Événements et erreurs

Les codes E sont mappés vers `AGENT_HANDOFF_VIOLATION`,
`AUTHORITY_SMUGGLING`, `TRUST_BOUNDARY_VIOLATION`,
`INDIRECT_CONTENT_INJECTION` et `HOSTILE_CONTENT_PROPAGATION`. Les événements
ne contiennent que codes, labels, refs et compteurs sûrs. Aucun contenu agent
brut, finding, prompt ou raisonnement privé n'est copié.

## Couverture

Les tests E couvrent notamment :

- tentative de délégation par AG-02/03/04 ;
- mutation target/capability/principal, profondeur et redélégation ;
- scope enfant élargi ;
- delegation, invocation, run, step et correlation divergents ;
- envelope manquant ou réutilisé ;
- spoof AG-03/AG-04 ;
- Evidence hors scope et substitution de refs dans le payload ;
- clés d'autorité imbriquées dans contexte, payload et warnings ;
- faux positifs pédagogiques textuels ;
- statut `SUCCEEDED` sans sémantique métier ;
- review reviewer-only, suggestion non exécutable et lignée correction ;
- provenance des trois types d'output ;
- cinq mappings `SecurityEvent` sans raw content ;
- owners uniques et absence de leakage F/G/12.13.

Résultats de clôture :

```text
Python                         3.12.13
tests ciblés E                 33 passed
régression contrats historiques 138 passed
fitness E + allowlist historique 11 passed
suite globale               3248 passed
compileall backend             PASS
Ruff                           PASS
mypy backend                   PASS
git diff --check               PASS
```

## Frontières et dépendances

```text
AG-01 = unique delegation owner
CapabilityAuthorizationPolicy = shared capability/delegation authority
DelegationScopePolicy = unique child-scope evaluator
InstructionDataBoundaryPolicy = unique text isolation policy
structural_keys.py = unique structural key classifier
AG-04 = Reviewer/Critic only
Tool/Application/Gate owners = unchanged
```

`[project].dependencies` reste vide. Aucun provider, réseau, DB, filesystem
métier, scanner de secrets, sink, intégration runtime/recovery ou nouvelle
dépendance n'est ajouté.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
