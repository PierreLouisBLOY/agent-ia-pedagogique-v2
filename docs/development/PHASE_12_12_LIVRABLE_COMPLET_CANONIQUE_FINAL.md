# Phase 12.12 — Livrable complet canonique final

## 1. Objet de la phase

La Phase 12.12 ferme le lot canonique :

```text
GLOBAL_SECURITY_HARDENING
```

Elle durcit les frontières contre la prompt injection, l'injection par
documents et données, l'injection Tool/Application, le transport clandestin
d'autorité entre agents, l'exfiltration et l'exposition de secrets, les entrées
structurelles non bornées et les incohérences de composition entre sécurité,
runtime et recovery.

La phase reste provider-neutral, sans I/O de sécurité ni dépendance runtime.
L'observabilité n'entre pas dans ce périmètre :

```text
12.13 observability remains deferred
```

## 2. Baseline d'entrée et résultat fonctionnel

La baseline d'entrée est la clôture canonique de la Phase 12.11 :

```text
main@52d1c774bfa07e2f7378fb4d9dcf44bec015eac0
```

Le SHA fonctionnel final de la Phase 12.12 est :

```text
ff9c87f75f5b70356c8b6405979404a9a6e78bd5
```

Son tree fonctionnel est :

```text
3e0b26c3f61f5e38adeaf9272708951851b91460
```

La lignée fonctionnelle exacte est :

```text
fee299c60c23a4cd800af722a4ba475be9031387  feat: establish security trust and event contracts
c10d8eaa0c811b6b9ffcb045bc9d2553ffe7455a  feat: isolate untrusted instructional content
acb3455d48ac4e1b6b050956c9ce8d9335fc3162  feat: harden tool and application boundaries
1942a4017524d11ee4782116a20fbdce1fbdb0e7  feat: harden multi-agent delegation boundaries
b8408f87e0b70f3bb5100d30054dc3b99f1a6d90  feat: harden secret and exfiltration boundaries
ff9c87f75f5b70356c8b6405979404a9a6e78bd5  feat: integrate global runtime security hardening
```

Le merge-base avec la baseline est exactement le SHA d'entrée. Aucun commit
parasite ou merge commit ne figure dans cette chaîne.

## 3. Phase 12.12-A — audit et threat model

Le lot A a été un audit-only sans commit fonctionnel. Il a cartographié le
graphe de confiance entre entrées utilisateur, documents, Evidence, agents,
Tools, Application, gates, runtime, recovery et infrastructure.

Les surfaces d'attaque recensées couvraient le contenu instruction-like, les
pseudo-faits d'autorité dans les données, les arguments et résultats Tool, les
payloads et effets demandés Application, les handoffs et résultats agentiques,
les valeurs sensibles, les chemins privés, les structures amplifiées et les
reprises après crash. La matrice de menaces a relié chaque surface à son owner
canonique, à son mode d'échec fermé et aux tests adversariaux nécessaires.

Les gaps initiaux ont été rationalisés selon quatre dimensions : sémantique,
invariant, autorité et cycle de vie. Aucune façade globale donnant de
l'autorité à la sécurité n'a été retenue. Les invariants fondateurs étaient la
non-promotion du contenu, la conservation de provenance, la séparation des
owners et la revalidation du courant avant toute reprise.

## 4. Phase 12.12-B — vocabulaire, confiance et SecurityEvent

Le lot B a établi les contrats communs suivants :

- `SecurityBoundary` pour les frontières user input, document, Evidence,
  agent, Tool, Application, gate, runtime, recovery et infrastructure ;
- `ContentOrigin` et `ContentRole` pour conserver provenance et fonction ;
- `ContentTrustClass` et `ContentTrustLabel` pour une confiance descriptive ;
- `SecurityEventType`, `SecuritySeverity` et `SecurityReasonCode` pour une
  taxonomie fermée ;
- `SecurityEvent` pour un fait de sécurité immutable, minimal et data-only.

La confiance contient exactement :

```text
ContentTrustClass =
UNTRUSTED
STRUCTURALLY_VALIDATED
```

`STRUCTURALLY_VALIDATED` n'accorde aucune permission. Il n'existe ni
`TRUSTED_INTERNAL`, ni fonction générique de promotion. `ContentTrustLabel`
conserve origin, role, trust class et une référence opaque optionnelle, sans
payload, secret, route, capability, permission ou gate.

`SecurityEvent` transporte uniquement des identifiants opaques bornés, une
classification, le contexte de corrélation, des refs sûres, un label optionnel
et des métadonnées récursivement gelées et minimisées. Les clés de contenu
brut, prompts, documents, payloads, messages, résumés, chemins privés et clés
d'idempotence brutes sont interdites. L'événement ne décide aucune autorité,
n'est pas persisté et n'est relié à aucun sink, logger ou exporter.

## 5. Phase 12.12-C — isolation instruction/data/content

Le lot C a rationalisé les signaux de menace communs sous
`ContentThreatSignalCode`, sans confondre les signaux de qualité propres à
Evidence, Generation ou Review. `LabeledContent` associe le contenu de travail
à sa provenance explicite ; `LabeledEvidenceItem` enveloppe un `EvidenceItem`
sans le promouvoir ni le muter.

`ContentSecurityDisposition`, `ContentSecurityAssessment` et l'unique
`InstructionDataBoundaryPolicy` classent les données en `PASS_AS_DATA`,
`ISOLATE_AS_DATA`, `QUARANTINE`, `REJECT_CONTENT` ou `ESCALATE_REVIEW`. Un
signal lexical isolé reste une donnée et ne suffit pas à conclure à une attaque.
Une contradiction structurelle de rôle ou un pseudo-champ d'autorité échoue
fermée.

La rationalisation Evidence/Generation/Review conserve leurs owners :

- Evidence porte source, excerpt, identité et rôle EVIDENCE cohérents ;
- Generation consomme des Evidence labellisées et produit un résultat non
  fiable dont la lineage entre dans les fingerprints ;
- Review conserve provenance, target, refs et lineage, sans devenir gate ou
  promotion.

Les tests anti-faux-positifs couvrent les impératifs pédagogiques, les
citations de prompt injection, les URLs institutionnelles, les extraits de
code et les descriptions d'action. Le texte est isolé comme donnée lorsque
nécessaire ; il n'est ni suivi, ni exécuté, ni interprété comme permission.

La provenance est monotone : USER_INPUT, DOCUMENT, EVIDENCE, AGENT_OUTPUT,
REVIEW_OUTPUT ou CORRECTION_OUTPUT ne peuvent être réétiquetés vers une origine
plus autoritaire. Rôle et origine traversent les frontières sans promotion.

## 6. Phase 12.12-D — sécurité Tool et Application

Le lot D a introduit le classifieur structurel commun
`normalize_structural_key`, `structural_key_locations` et
`contains_structural_keys`. Il détecte les variantes imbriquées de clés
d'autorité et ne renvoie que des positions logiques ; la décision reste chez
l'owner de la frontière.

Pour Tool, les arguments sont contrôlés avant exécution contre les tentatives
de redéfinition de Tool, capability, permission, gate, provider, handler,
sandbox, target, binding, owner, route, policy facts ou faits recovery.
`ToolCallPolicy` reste l'unique owner de `ALLOW/DENY`, et `SandboxPolicy`
reste l'unique owner des décisions filesystem pré/post-exécution. Les schémas
des descriptors, les bindings et les chemins produits sont vérifiés sans
nouveau framework de schéma.

Pour Application, le payload et `requested_effect` sont évalués séparément.
Ils ne peuvent redéfinir capability, permission, gate, promotion, route,
target, provider, handler, owner ou succès/commit d'effet. L'unique
`UseCaseRouter` conserve le routage et `CapabilityAuthorizationPolicy` produit
la disposition Application `REQUEST`. La validation de frontière complète,
mais ne remplace jamais, la validation métier du use case.

Les résultats gardent une provenance non fiable :

```text
ToolCallResult -> TOOL_OUTPUT / RESULT / UNTRUSTED
UseCaseResult  -> APPLICATION_OUTPUT / RESULT / UNTRUSTED
```

Outputs, validations, side effects, domain events, metrics et erreurs restent
soumis à C puis F. Une revendication hostile se propage comme donnée isolée ou
refusée, jamais comme fait. Un output Tool ou Application n'est pas Evidence
par défaut ; seul le propriétaire Evidence/provenance peut matérialiser cette
transition.

## 7. Phase 12.12-E — sécurité multi-agent

Le lot E ferme l'autorité de délégation sur AG-01. `DelegationEnvelope` relie
le step canonique au spécialiste, à la capability exacte, au scope enfant et
aux Evidence refs. `DelegationResult` lie le résultat à l'envelope, tandis que
le producteur de `AgentResult` est dérivé de `meta.actor` et ne peut pas être
usurpé.

`ValidatedAgentHandoff` matérialise uniquement une preuve data-only après
validation exacte des IDs de délégation et invocation, source, target,
capability, schema, run, step, parent step, correlation, refs et lineage. Le
scope enfant ne peut ni s'élargir ni redéléguer, et la profondeur spécialiste
est exactement 1. `DelegationScopePolicy` reste l'évaluateur canonique du scope.

L'exclusivité est explicite : AG-01 est l'unique delegation owner. AG-02,
AG-03 et AG-04 restent spécialistes. AG-04 est uniquement
`REVIEWER_CRITIC` : ses findings et suggestions sont descriptifs, ne sont pas
auto-exécutables et doivent retourner vers AG-01. Une correction passe ensuite
par une requête explicitement planifiée, avec target version, review ID,
finding IDs et Evidence refs cohérents.

Les contextes, payloads, warnings, metrics, erreurs et stop reasons inter-agent
sont contrôlés par les frontières C, D et F. Un statut `SUCCEEDED`, un texte
« approved » ou une suggestion de reviewer ne crée ni gate, ni validation
métier, ni permission, ni promotion.

## 8. Phase 12.12-F — secrets, exfiltration et limites

Le lot F maintient des responsabilités distinctes :

- key safety dans le gel canonique refuse les noms de clés dangereux ;
- le classifieur D détecte les clés structurelles d'autorité ;
- C détecte les signaux textuels, dont `EXFILTRATION_TEXT` ;
- l'unique `SensitiveValuePolicy` inspecte localement les valeurs ;
- `StructuredDataLimits` borne profondeur, cardinalités, chaînes et nœuds.

`SensitiveValuePolicy` reconnaît les formes fortes de credential, token
d'authentification, clé privée, secret de connexion ou chemin privé. Son
assessment ne contient que la classe et une position logique. Aucun extrait,
hash ou fingerprint de la valeur n'est produit.

`ErrorEnvelope` est borné et minimisé : message, details et refs agent-safe
refusent valeurs sensibles, structures excessives et chemins privés. Les
metadata de `SecurityEvent` appliquent un profil encore plus strict. Tool,
Application et Agent contrôlent aussi outputs, warnings, erreurs, artifacts et
refs avant toute propagation.

Les limites structurelles génériques sont depth 16, mapping 256, sequence 512,
string 65 536 et nodes 4 096. Des profils plus étroits s'appliquent aux erreurs
et événements. Les limites historiques Evidence, runtime, sandbox et snapshot
gardent leurs owners propres et ne sont pas fusionnées.

Les tests de secrets utilisent uniquement des marqueurs synthétiques assemblés
dans les fixtures. Aucun secret réel, SecretStore, Vault, KMS, provider SDK,
loader de credential ou backend DLP n'est introduit.

## 9. Phase 12.12-G — intégration globale runtime/recovery

Le lot G compose les contrôles autour du chemin runtime réel :

```text
RoutingPreLaunchGuard
  -> canonical Tool / Application / Agent / Gate authority
  -> SecurityRuntimeGuard
  -> RoutingStepRunner
  -> post-result security validation
  -> PlanExecutor / directives
  -> OrchestrationCoordinator
  -> RecoveryCoordinator / ReplayGuard
```

`SecurityRuntimeGuard` est pur, sans port ni I/O. Il compose les assessments
en `PASS`, `RESTRICT`, `DENY`, `QUARANTINE` ou `ESCALATE`. La sécurité est
restriction-only : elle peut réduire une décision déjà produite par l'owner
canonique, jamais créer `ALLOW`, `REQUEST`, `DELEGATE` ou `APPROVED`.

Une interdiction pré-effet provoque zéro appel Tool, inbound Application ou
spécialiste. Un rejet post-effet ne prétend pas que l'effet n'a pas eu lieu :
il produit un état conservateur et impose la réconciliation. Les
`SecurityEvent` de `ExecutionCycleResult` sont transitoires et bornés.

`RunState`, `ExecutionDirective`, `StepState`, checkpoints et snapshots ne
stockent ni contenu brut, ni assessment ancien, ni événement, ni secret, ni
chemin privé. `SecurityRevalidationStatus` encode la revalidation courante.
`RecoveryCoordinator` repasse par le `RoutingPreLaunchGuard` canonique et
`ReplayGuard` bloque toute reprise si l'autorité ou la sécurité courante est
invalide.

Les règles recovery 12.11 restent inchangées :

```text
UNKNOWN -> reconcile
PARTIAL -> no auto retry
COMMITTED -> no replay
NONE -> only potentially retryable
```

## 10. Phase 12.12-H1 — audit cumulatif pré-merge

H1 a audité cumulativement B à G, la lignée, les owners d'autorité, les
frontières sécurité/recovery, les scénarios adversariaux et les validations.
Le delta fonctionnel réel entre la baseline et G est :

```text
134 files changed
10 628 insertions
642 deletions
0 merge commit
```

Les validations canoniques H1 étaient :

```text
targeted cumulative = 598 PASS
global = 3300 PASS
blocking findings = 0
merge readiness = FAST_FORWARD_READY
```

## 11. Phase 12.12-H2 — fast-forward strict

Avant H2, `main` et `origin/main` pointaient sur
`52d1c774bfa07e2f7378fb4d9dcf44bec015eac0`. H2 a avancé `main` vers G avec
`git merge --ff-only`, sans merge commit, rebase, squash, cherry-pick ou
force-push.

Après le push, `main`, `origin/main`, la branche fonctionnelle locale et sa ref
distante pointaient toutes sur G. Le tree de `main` était identique au tree
fonctionnel, la branche fonctionnelle n'avait pas été déplacée séparément et la
relation `main...phase12/12-12-security-hardening` était `0/0`.

```text
MERGE_MODE = FAST_FORWARD_ONLY
```

## 12. Architecture finale de sécurité

```text
Untrusted content
    |
    v
B Trust / SecurityEvent
    |
    v
C Instruction/Data isolation
    |
    +----> Evidence / Generation / Review
    |
    v
D Tool + Application boundary security
    |
    v
E Multi-Agent handoff security
    |
    v
F Sensitive values + structural limits
    |
    v
G Runtime/Recovery security composition
```

L'échelle d'autorité demeure indépendante de cette chaîne de restriction :

```text
TOOL        -> ALLOW
APPLICATION -> REQUEST
AGENT       -> DELEGATE
GATE        -> APPROVED
RUNTIME     -> execution control
RECOVERY    -> technical admissibility
SECURITY    -> restrict only
```

## 13. Invariants globaux

```text
UNTRUSTED_CONTENT_NEVER_BECOMES_AUTHORITY
CONTENT_ROLE_AND_ORIGIN_ARE_PRESERVED_ACROSS_BOUNDARIES
DATA_NEVER_OVERRIDES_TRUSTED_INSTRUCTION_CHANNEL
LLM_OUTPUT_NEVER_BECOMES_PERMISSION_OR_GATE_FACT
PAYLOAD_NEVER_OVERRIDES_ROUTE_CAPABILITY_OWNER_OR_TARGET
AGENT_RESULT_NEVER_OVERRIDES_DELEGATION_LINEAGE
TOOL_OR_APPLICATION_OUTPUT_IS_NEVER_EVIDENCE_BY_DEFAULT
SECRET_VALUE_NEVER_ENTERS_AGENT_SAFE_CONTRACT
SECURITY_EVENT_CONTAINS_ONLY_MINIMIZED_SAFE_DATA
RECOVERY_ALWAYS_REVALIDATES_CURRENT_SECURITY_AUTHORITY
SECURITY_CAN_ONLY_RESTRICT_DENY_CLASSIFY_OR_ESCALATE
```

## 14. Invariants recovery 12.11 préservés

```text
UNKNOWN -> reconcile before replay
PARTIAL -> never auto retry
COMMITTED -> never replay
NONE -> only potentially retryable
COMMITTED != SUCCEEDED without trusted terminal receipt
no synthetic idempotency identity
no retry loop
snapshot/budget/ledger/circuit monotone
recovery technical-only
```

Le ledger courant, la reconciliation, le budget, le snapshot, le circuit et
les owners d'autorité sont relus avant toute reprise. Un conflit ou un état
inconnu échoue fermé et ne provoque jamais un second effet automatique.

## 15. Rationalisation finale

Les responsabilités suivantes restent séparées malgré certaines ressemblances
de forme :

- key safety protège le gel de mappings contre les noms dangereux ;
- structural authority classification localise les pseudo-clés d'autorité ;
- content threat signals qualifient un texte sans décider une attaque ;
- value safety refuse secrets probables et chemins privés ;
- `ContentSecurityAssessment` décrit l'isolation du contenu ;
- `StructuredContentSecurityAssessment` décrit les violations structurelles ;
- `RuntimeSecurityAssessment` compose uniquement des restrictions runtime ;
- Tool, Application, Agent et Gate gardent chacun leur owner d'autorité ;
- `ReplayGuard` statue sur l'admissibilité technique après revalidation de la
  sécurité et de l'autorité courantes.

Une fusion changerait la sémantique, l'autorité ou le cycle de vie d'au moins
une responsabilité et créerait une façade trop puissante.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## 16. Sécurité des données et dépendances

Le delta fonctionnel et le livrable final ne contiennent aucun secret brut,
credential, clé d'idempotence brute, payload provider, stack, chemin privé ou
donnée runtime. Les contrats agent-safe n'acceptent pas de chemins privés.

`SecurityEvent` reste data-only et transitoire : aucune persistence, aucun
logger, sink, exporter, metric ou trace n'est livré en 12.12. Aucun SDK
provider, framework, réseau, base, ORM, subprocess ou dépendance runtime n'est
ajouté.

La lecture réelle du manifeste donne :

```text
[project].dependencies == []
```

## 17. Tests finaux

Les chiffres canoniques de H1 sont :

```text
targeted cumulative = 598 PASS
global = 3300 PASS
Python = 3.12.13
Ruff = PASS
mypy = PASS
compileall = PASS
```

La gate H3 a rejoué la suite globale avec le présent document dans le
worktree. Son résultat final est :

| Validation | Résultat |
| --- | --- |
| Python | 3.12.13 |
| tests ciblés cumulatifs H1 | 598 PASS |
| suite globale H3 | 3300 PASS |
| `python -m compileall backend` | PASS |
| `python -m ruff check .` | PASS |
| `python -m mypy backend` | PASS |
| `git diff --check` | PASS |

## 18. Audit post-merge H3

Le préflight a confirmé `main`, un worktree propre, G sur `HEAD`, `main`,
`origin/main` et les refs locale/distante de la branche fonctionnelle, le tree
fonctionnel attendu et une relation `0/0`. Le code réel confirme :

- deux seules valeurs de `ContentTrustClass` ;
- un `SecurityEvent` minimal, raw-free et sans autorité ;
- un owner unique pour chaque policy et router canonique ;
- AG-01 unique delegation owner et AG-04 reviewer-only ;
- `SecurityRuntimeGuard` restriction-only au point de composition
  `RoutingPreLaunchGuard` ;
- revalidation de l'état courant par `RecoveryCoordinator` et `ReplayGuard` ;
- préservation intégrale des décisions recovery 12.11.

L'audit du delta H3 donne :

```text
ONE_FILE_ONLY = TRUE
NO_CODE_CHANGE = TRUE
NO_SECRET = TRUE
NO_PRIVATE_PATH = TRUE
NO_RUNTIME_DATA = TRUE
NO_GENERATED_ARTIFACT = TRUE
NO_DEPENDENCY_CHANGE = TRUE
```

## 19. Statut final

Le commit H3 est strictement documentaire, a G pour parent direct et ajoute
uniquement le présent livrable. Le push cible uniquement `main`; la branche
fonctionnelle reste sur G.

```text
PHASE 12.12-H3 — PASS / CLOSED
PHASE 12.12 — CLOSED / MERGED
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_MODE = FAST_FORWARD_ONLY
```

## 20. Handoff Phase 12.13

```text
NEXT_PHASE = 12.13
PHASE_12_13_SCOPE = OBSERVABILITY_LOGGING_TRACING_METRICS_EXPORTERS
```

La frontière de handoff est :

```text
12.12 SecurityEvent remains data-only.
12.13 may add observability plumbing but must not turn events into authority.
```
