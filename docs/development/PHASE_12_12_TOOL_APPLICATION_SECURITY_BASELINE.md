# Baseline Phase 12.12-D — Sécurité Tool et Application

## Périmètre livré

Le lot D part directement de la baseline C
`c10d8eaa0c811b6b9ffcb045bc9d2553ffe7455a` sur la branche
`phase12/12-12-security-hardening`.

Il livre :

```text
classification structurelle commune sans décision
+ sécurité des arguments et résultats Tool
+ sécurité du payload, requested_effect et résultats Application
+ validation des contrats descriptors avant exécution
+ provenance TOOL_OUTPUT/APPLICATION_OUTPUT non fiable
+ prévention de propagation hostile vers Generation/Review
+ mapping SecurityEvent minimisé
+ tests adversariaux et fitness d'architecture
```

Il ne livre ni handoff multi-agent, ni scanner global de secrets, ni limites
globales, ni intégration runtime/recovery, ni observabilité.

## Audit Tool

`ToolCallRequest` fournit l'intention, l'identité Tool/capability, les
arguments, le scope, le timeout et l'idempotency key. `ToolDescriptor` et
`ToolRegistry` fournissent les contrats, l'effet, le profil sandbox et les
contraintes statiques. `ToolCallPolicy` reste l'unique owner de `ALLOW/DENY` et
borne le timeout.

`ToolRoutingContext` fournit root, inputs et output targets ;
`SandboxPolicy` prend les décisions filesystem pré/post-exécution.
`ToolExecutorBindings` résout l'exécuteur exact. `PreparedToolExecution`
scelle request, descriptor, décision, sandbox, contrats, binding logique et
assessment des arguments avant le port. `ToolExecutionOutcome` et
`ToolCallResult` sont reconstruits puis contrôlés après exécution.

Les IDs input/output des deux descriptors Tool canoniques sont comparés à la
baseline avant l'appel de l'exécuteur. La reconstruction typée du résultat et
le contrôle exact des produced paths complètent cette validation sans nouveau
framework de schéma.

## Audit Application

`UseCaseRequest` fournit use case, payload, contexte acteur, préconditions,
idempotency et intention d'effet. `UseCaseRoutingContext` fournit le step, la
capability, le scope et les policy facts trusted. `UseCaseDescriptor` et
`UseCaseRegistry` fournissent les IDs `C-12`/`C-13`, la capability et
l'idempotency statiques. `UseCaseInboundBindings` résout l'inbound exact.

`CapabilityAuthorizationPolicy` produit la disposition `REQUEST` ;
`UseCaseRouter` reste le seul owner du routage. Les IDs du descriptor et son
binding exact par `use_case_id` vers le port sont contrôlés avant l'invocation.
Le contrat output générique du step reste une responsabilité de planification
distincte. `UseCaseResult`,
`ApplicationOutcome`, `ApplicationFailure`, business errors,
`validation_result`, side effects, domain events et `ErrorEnvelope` sont
reconstruits et contrôlés après l'inbound.

La validation de frontière vérifie forme, identité, lineage et contrats. Elle
ne remplace aucune validation métier Application.

## Classification structurelle et faux positifs

`normalize_structural_key`, `structural_key_locations` et
`contains_structural_keys` sont les seuls éléments rationalisés. Ils détectent
les clés imbriquées et leurs variantes snake/camel/kebab/compactes et ne
retournent que des positions logiques.

Les listes Tool, Application payload, `requested_effect`, résultats, Gate et C
restent distinctes. Le safe mapping conserve son vocabulaire propre de secrets,
tokens, SQL, traces, provider payload et chemins locaux, ainsi que le rejet du
raisonnement privé côté contrats agent. Aucun owner de décision n'est fusionné.

Une vraie clé `permissionScope` ou `gateDecision` peut donc être refusée, alors
qu'une chaîne pédagogique mentionnant `permission`, `capability_id`, JSON, du
code ou de la cybersécurité reste une donnée. Les signaux lexicaux de C peuvent
l'isoler mais ne changent jamais l'autorisation.

## Sécurité des inputs

Les arguments Tool ne peuvent redéfinir Tool/capability, permission, gate,
provider/handler, sandbox, target/binding, owner/route, policy facts ou faits
12.11. L'assessment est conservé dans `PreparedToolExecution`, tandis que
`ToolCallPolicy` reste responsable de la décision.

Le payload Application ne peut redéfinir capability, permission, gate,
promotion, provider/handler/executor, override, owner/route/target, policy
facts ou faits 12.11. `requested_effect` est contrôlé séparément et ne peut
affirmer succès, commit ou preuve d'effet.

## Sécurité des outputs et propagation

`ToolCallResult` impose le label :

```text
TOOL_OUTPUT / RESULT / UNTRUSTED
```

`UseCaseResult` impose :

```text
APPLICATION_OUTPUT / RESULT / UNTRUSTED
```

Les outputs, metrics, validations, side effects, events, failures et détails
d'erreur sont évalués avec `InstructionDataBoundaryPolicy`. Une clé
structurelle d'autorité échoue fermé. Un texte hostile ou une revendication
textuelle reste isolé comme donnée.

Generation et Review exigent une couverture exacte entre `labeled_inputs` et
`input_security_assessments`. La provenance et la confiance ne peuvent pas
être promues. Aucun résultat Tool n'est transformé automatiquement en
Evidence ; l'owner Evidence/provenance reste obligatoire.

## SecurityEvent et erreurs sûres

Le mapping pur utilise les types B existants : `TOOL_INJECTION`,
`APPLICATION_INJECTION`, `AUTHORITY_SMUGGLING`,
`HOSTILE_CONTENT_PROPAGATION` et `TRUST_BOUNDARY_VIOLATION`. Il conserve labels,
refs et reason codes, jamais les arguments, payloads, résultats ou textes
bruts.

`ToolRoutingError` et `UseCaseRoutingError` n'exposent que des reason codes et
messages sûrs. Les détails de `ErrorEnvelope`, `ApplicationFailure` et
`BusinessError` passent par les contrôles structurels avant de franchir la
frontière.

## Sandbox et recovery

Le `SandboxPolicy` unique, les profils, la résolution de chemins et les
contrôles pré/post-exécution sont inchangés. Un fichier autorisé par le sandbox
peut contenir un texte hostile ; ce texte demeure `TOOL_OUTPUT` non fiable et
est isolé par C.

Les clés `record_id`, `effect_state`, `retry_facts`,
`reconciliation_status`, `circuit_binding` et snapshot refs sont refusées dans
les mappings non fiables. Aucun module 12.11 n'est modifié et aucun fait de
recovery n'est reconstruit depuis un payload.

## Couverture de tests D

Les tests D couvrent :

- variantes imbriquées snake/camel/kebab/compactes et anti-faux-positifs ;
- arguments Tool adversariaux, contrats descriptor et détails d'erreur ;
- outputs Tool hostiles, revendications de gate/evidence et fichier sandbox ;
- payload et `requested_effect` Application adversariaux ;
- outcome, validation, domain events et failure details hostiles ;
- provenance Tool/Application et propagation vers Generation/Review ;
- absence de promotion Evidence ;
- mapping de chacun des événements D sans contenu brut ;
- owners uniques, réutilisation de C et du sandbox, absence de E/F/G/12.13 et
  de dépendance runtime.

Les validations canoniques sont celles de `docs/development/ENVIRONMENT.md` :
Python 3.12, compileall, suite Pytest globale, Ruff, mypy backend et contrôles
Git du diff.

Résultats de clôture :

```text
Python 3.12.13
tests ciblés D             78 passed
régressions étendues      274 passed
suite globale            3215 passed
compileall backend          PASS
Ruff                        PASS
mypy backend                PASS
```

## Frontières et rationalisation

```text
ToolCallPolicy = unique Tool ALLOW/DENY owner
CapabilityAuthorizationPolicy = shared capability authority owner
UseCaseRouter = unique Application routing owner
InstructionDataBoundaryPolicy = unique content isolation owner
SandboxPolicy = unique sandbox owner
SecurityEvent = unique security event contract
TOOL_OUTPUT_IS_NEVER_EVIDENCE_BY_DEFAULT
```

`[project].dependencies` reste vide. Aucun provider, réseau, DB, filesystem
métier, secret scanner, sink ou nouvelle dépendance runtime n'est ajouté.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
