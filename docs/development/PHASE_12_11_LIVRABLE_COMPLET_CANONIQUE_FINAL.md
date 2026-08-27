# Phase 12.11 — Livrable complet canonique final

## 1. Objet de la Phase 12.11

La Phase 12.11 rend les effets techniques rejouables de façon sûre, les effets
inconnus réconciliables, les reprises déterministes et les retries strictement
bornés. Elle compose idempotence, effect ledger, accounting, snapshots,
reconciliation, replay guard, retry/backoff et circuit breaker autour du runtime
12.10 sans transformer le recovery en autorité métier.

Le principe cumulatif est : un `DENY`, une gate rejetée, une permission invalide,
un budget inconnu ou dépassé, un snapshot stale, un circuit bloqué, un effet
`UNKNOWN`, `PARTIAL` ou `COMMITTED` ne peut jamais devenir une autorisation de
replay.

## 2. Baseline d'entrée

La baseline officielle d'entrée est :

```text
main@c708037e5efd5602a64604c70126e8f376d063d5
```

Elle correspond à la clôture canonique de la Phase 12.10. Le SHA fonctionnel
intégré de la Phase 12.11 est :

```text
06aa0d28768cd5888eb9d42fe09073c5faadab89
```

## 3. Phase 12.11-A — audit d'ouverture

L'audit A a inventorié les contrats existants (`EffectState`, `ErrorEnvelope`,
`ApplicationFailure`, clés d'idempotence, `RunState`, `StepState`,
`attempt_count`, `BudgetSpec` et directives runtime), puis confirmé les gaps :
absence de ledger persistant abstrait, accounting recovery, snapshot recovery,
probes typés, replay guard, retry/backoff et circuit breaker.

Il a retenu une architecture autour de `PlanExecutor`, avec recovery technique
distinct de `OrchestrationCoordinator`, sans boucle de retry, sans I/O de
production et sans déplacement d'autorité. Le découpage B à H a été confirmé.

```text
PHASE 12.11-A — PASS / CLOSED
IMPLEMENTATION_GATE = 12.11-B_READY
```

## 4. Phase 12.11-B — idempotence et effect ledger

B a introduit des modèles immutables, `IdempotencyPolicy` et l'unique
`EffectLedgerPort`. L'identité représente l'intention stable, tandis que les
tentatives appartiennent à la lignée du record. La réservation est atomique et
toute mutation ultérieure est un CAS versionné sans retry interne.

Un duplicate actif ne déclenche jamais un second effet. Un duplicate finalisé
`COMMITTED` ne peut pas être rejoué ; `UNKNOWN` et `PARTIAL` exigent une
reconciliation ou un traitement manuel. Les stores concurrents concrets restent
uniquement sous `tests/support/`.

## 5. Phase 12.11-C — budget, accounting et snapshots

C a réutilisé l'unique `BudgetSpec` et l'unique `AgentRuntimePolicy`, puis créé
`BudgetState`, `BudgetAccountingPolicy`, `BudgetStatePort`, `PlanFingerprint`,
`StateSnapshot`, `SnapshotSequencePolicy` et `StateSnapshotStorePort`.

Les scopes run/enveloppe et per-step restent séparés. Une mesure absente est
`UNKNOWN`, jamais zéro. Les compteurs, versions et séquences sont monotones ;
aucun restore ne réinitialise budget, attempts, ledger ou circuit. Le snapshot
est un checkpoint technique et non une vérité métier.

## 6. Phase 12.11-D — reconciliation

D a établi deux frontières distinctes : `ToolEffectProbePort` pour la route
`UTILITY` et `ApplicationEffectProbePort` pour la route `APPLICATION`. Il
n'existe aucun probe générique et les routes AGENT/RUNTIME sont refusées par
cette frontière.

`EffectReconciliationEngine` réalise au plus un probe typé et un CAS par appel.
Une version stale bloque avant le probe ; une course CAS après le probe ne
déclenche ni second probe ni retry. La reconciliation observe un effet technique
mais n'accorde aucune permission, gate, validation ou promotion.

## 7. Phase 12.11-E — ReplayGuard, RetryPolicy et backoff

E a créé les uniques `ReplayGuard`, `RetryPolicy` et
`DeterministicBackoffPolicy`. Seul un record `FINALIZED/NONE`, une identité
exacte et des faits trusted tous courants peuvent être potentiellement
retryables.

`UNKNOWN` impose `RECONCILE_FIRST`. `PARTIAL` et `COMMITTED` ne sont jamais
retryables automatiquement. Les catégories `DOMAIN`, `PERMISSION`, `GATE`,
`BUDGET` et `CANCELLED` sont fermées au retry. Une recommandation `RETRY` ne
contourne aucun autre invariant. Le backoff est exponentiel, déterministe,
plafonné et sans `sleep`.

## 8. Phase 12.11-F — circuit breaker

F a créé une clé exacte composée de la route, de la cible et du binding :

```text
CapabilityExecutionRoute + target_id + binding_id
```

Le circuit n'est jamais capability-global et `RUNTIME` est unsupported. Les
états sont exactement `CLOSED`, `OPEN` et `HALF_OPEN`. `OPEN` bloque fail-closed ;
le passage à `HALF_OPEN` exige un CAS et une lease atomique unique liée au
circuit, à sa version, au run, au step et à l'attempt. L'expiration d'une lease
n'est jamais un succès.

La configuration est injectée, la fenêtre de failures est bornée et seules les
erreurs techniques `TRANSIENT`, `PROVIDER` et `TOOL` sont comptées. Aucun reset,
fallback ou changement silencieux de provider n'existe.

## 9. Phase 12.11-G — intégration runtime recovery

G compose B à F autour du runtime 12.10. `PlanExecutor` reste unique, inchangé
fonctionnellement et mono-cycle. `OrchestrationCoordinator` reste unique et
distinct de `RecoveryCoordinator`. `RecoveryRuntimeController.execute_cycle()`
effectue exactement un appel à chacun :

```text
PlanExecutor.execute_cycle
-> OrchestrationCoordinator.coordinate
-> RecoveryCoordinator.recover
```

Il n'existe aucune boucle interne. Le caller doit réinvoquer explicitement un
nouveau cycle.

## 10. Phase 12.11-H1 — audit pré-merge

H1 a confirmé la baseline, la lignée B à G, l'absence de commit parasite et de
merge commit, le delta fonctionnel, l'autorité intacte, les scénarios crash,
l'absence de double appel protégé, les validations et la rationalisation.

```text
PHASE 12.11-H1 — PASS / CLOSED
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_GATE = FAST_FORWARD_READY
```

## 11. Phase 12.11-H2 — fast-forward strict

H2 a avancé `main` de `c708037e5efd5602a64604c70126e8f376d063d5`
vers `06aa0d28768cd5888eb9d42fe09073c5faadab89` uniquement avec
`git merge --ff-only`, puis a poussé `main`. Aucun merge commit, rebase, squash,
cherry-pick, force-push ou déplacement de la branche fonctionnelle n'a eu lieu.

Après push, `main`, `origin/main`, la branche source locale et sa référence
distante pointaient toutes sur le SHA fonctionnel, avec une divergence `0/0`.

```text
PHASE 12.11-H2 — PASS / CLOSED
MERGE_MODE = FAST_FORWARD_ONLY
POST_MERGE_GATE = H3_REQUIRED
```

## 12. Architecture finale recovery

L'architecture finale sépare les modèles/policies purs, les ports abstraits, les
moteurs I/O bornés et l'intégration runtime :

```text
Runtime 12.10
  PlanExecutor + RoutingPreLaunchGuard + RoutingStepRunner
        |
        v
Wrappers recovery
  RecoveryPreLaunchGuard + RecoveryAwareStepRunner
        |
        +-> budgets / snapshots / circuit / ledger
        |
        v
RecoveryRuntimeController
  OrchestrationCoordinator -> RecoveryCoordinator
```

Le code de production réel est sous `backend/agent_runtime/recovery/`. Les ports
sont des `Protocol` provider-neutral. Les implémentations mémoire, probes et
resolvers concrets utilisés pour les preuves restent sous `tests/support/`. Aucun
fake n'est composé comme un adapter de production.

## 13. EffectState, lifecycle et reconciliation

`EffectState` conserve son unique définition contractuelle : `NONE`, `UNKNOWN`,
`COMMITTED`, `PARTIAL`. `UNSEEN` est l'absence de record et non un état persisté.
Le lifecycle du ledger est exactement :

```text
RESERVED -> IN_PROGRESS -> FINALIZED
RESERVED -> ABANDONED
```

Le statut de reconciliation est orthogonal : `NOT_REQUIRED`, `PENDING`,
`RESOLVED`, `MANUAL_REQUIRED`. Une tentative active porte conservativement
`UNKNOWN/PENDING`. Un record `FINALIZED` peut être mis à jour par reconciliation
sans créer de nouvel attempt.

Le mapping fermé est :

```text
COMMITTED       -> COMMITTED / RESOLVED
NOT_COMMITTED   -> NONE      / RESOLVED
PARTIAL         -> PARTIAL   / RESOLVED
STILL_UNKNOWN   -> UNKNOWN   / PENDING
MANUAL_REQUIRED -> effet préservé / MANUAL_REQUIRED
```

## 14. IdempotencyIdentity et fingerprints

`IdempotencyIdentity` contient principal, run, step, capability, route, cible,
opération, fingerprint d'intention et fingerprint de clé caller. Elle exclut
`attempt`, `plan_version`, payload et résultat.

Les fingerprints et IDs utilisent SHA-256 avec séparation de domaine. La clé
caller brute n'est jamais persistée. L'intention est sérialisée en JSON canonique
avec clés triées, séparateurs stables, types explicites pour `Decimal`, float,
enum et dataclass, et refus des nombres non finis. Aucun `repr()`, `str(dict)` ou
fingerprint fourni par un LLM n'est trusted.

## 15. EffectLedgerPort et CAS

`EffectLedgerPort` est unique et expose réservation atomique, lecture et CAS.
Chaque replacement exige la version courante et produit `version + 1`. Il
n'existe aucun retry CAS interne.

Les dispositions distinguent nouvelle réservation, duplicate actif, duplicate
finalisé, reconciliation requise, collision et expiration. `UNKNOWN`, `PARTIAL`
et `COMMITTED` ne peuvent jamais redevenir implicitement `NONE` ou `UNSEEN`.

## 16. BudgetState et accounting

`BudgetState` conserve des compteurs non négatifs, des complétudes de mesure et
une version CAS. Les totaux dérivés évitent la divergence. L'attempt initial vaut
1 et le nombre de retries vaut `max(0, attempt_count - 1)`.

Le retry budget est consommé exactement au lancement de la tentative suivante,
par un delta CAS lié à l'attempt attendu. Il n'est pas consommé lors de la seule
planification du retry. Usage inconnu, limite atteinte, incohérence de compteur
ou conflit CAS bloque fail-closed.

## 17. StateSnapshot et checkpoint

`StateSnapshot` contient le `RunState`, l'identité/version/fingerprint du plan,
le `BudgetState`, les références ledger/circuit version-only, la séquence, le
timestamp et, si nécessaire, un `RecoveryCheckpoint` minimal.

`EffectLedgerSnapshotRef` contient uniquement `record_id/version` et
`CircuitBreakerSnapshotRef` uniquement `circuit_id/version`. Le snapshot ne
copie pas l'état d'effet ou du circuit. Budget, ledger, circuit ou plan plus
récents rendent le snapshot stale ; le courant gagne toujours. Un checkpoint
conserve action, step, record/version, next attempt, retry ordinal et
`not_before`, sans payload, gate, scope ou `ErrorEnvelope` complet.

## 18. Probes et moteur de reconciliation

Les requêtes Tool et Application sont typées et minimales. Leur cible provient
de l'identité trusted et ne peut pas être remplacée par le caller. Une requête
ne contient ni payload, clé brute, credential, URL provider ou chemin absolu.

Le moteur relit le ledger courant, vérifie la version avant probe, appelle au
plus un probe, vérifie l'observation anti-forgery, puis effectue au plus un CAS.
Un `IN_PROGRESS` expiré est finalisé sans nouvel attempt. Une course CAS n'est
jamais réparée par reprobe.

## 19. ReplayGuard

`ReplayGuard` exige l'identité exacte et des faits trusted réévalués : autorité,
gate, budget, deadline et fraîcheur snapshot. Les sorties sont data-only :
`ELIGIBLE`, `RECONCILE_FIRST`, `REPLAN_REQUIRED`, `BLOCKED` ou
`MANUAL_REQUIRED`.

Une identité ou un plan différent exige un replan. Permission/gate invalides,
budget dépassé/inconnu, deadline expirée et snapshot stale bloquent. Tout chemin
éligible conserve structurellement l'obligation d'un circuit check.

## 20. RetryPolicy

`RetryPolicy` utilise l'`ErrorEnvelope` reconstruit depuis des faits sûrs, le
record courant, le `BudgetState` versionné, le budget check et la décision du
ReplayGuard. Aucun compteur libre caller-controlled n'est accepté.

Les limites envelope, step et policy runtime sont évaluées dans leur scope
d'origine. `NONE` est le seul effet potentiellement retryable ; catégories,
flag `retryable`, action recommandée, attempt exact et limites doivent tous être
compatibles. La policy ne lance aucun effet et ne consomme aucun budget.

## 21. Backoff déterministe

La baseline est exponentielle et déterministe : délai initial 1 seconde,
multiplicateur 2, plafond 60 secondes, sans jitter. `not_before` est calculé à
partir d'un `Instant` explicite. Aucun timer, thread, scheduler secondaire,
polling ou `sleep` n'est introduit.

## 22. CircuitBreaker

`CircuitBreakerPolicy`, `CircuitBreakerEngine` et `CircuitBreakerStorePort`
restent distincts. Chaque opération moteur fait au plus un get puis un create ou
un CAS. Une course devient un conflit explicite, jamais une boucle de réparation.

`OPEN` bloque avant appel. `HALF_OPEN` accorde au plus une lease concurrente et
un appel. La lease est vérifiée sur circuit/version/run/step/attempt. Une erreur
métier ou d'autorité libère la lease sans marquer la dépendance malade. Une
référence snapshot ne restaure ni ne ferme jamais un circuit.

## 23. RecoveryRuntimeController

`RecoveryRuntimeController` est l'unique façade du cycle recovery. Son corps ne
contient ni boucle ni second scheduler : un cycle executor, une coordination,
une décision recovery, puis un résultat data-only. Il ne décide ni permission,
gate, validation, promotion ou succès métier.

## 24. RecoveryCoordinator

`RecoveryCoordinator` est distinct de l'orchestrateur. Il traite au plus une
directive décisive par cycle. `RETRY_REQUIRED` et `RECONCILIATION_REQUIRED`
relisent les états techniques courants et passent par les policies propriétaires.
Le snapshot est sauvegardé par un CAS unique, sans overwrite ni retry automatique.

## 25. RecoveryPreLaunchGuard

Le guard recovery appelle d'abord le `RoutingPreLaunchGuard` canonique. Toute
décision différente de `ALLOW` est retournée exactement. Ensuite seulement, il
vérifie checkpoint/backoff et circuit. `OPEN`, `HALF_OPEN_BUSY`, checkpoint
incohérent ou exception de résolution bloquent avant lancement et avant
incrément d'attempt.

## 26. RecoveryAwareStepRunner et ordre protégé

Le runner est un wrapper de l'unique `RoutingStepRunner`, pas un second router.
`GATE`, `JOIN` et `DECISION` sont délégués directement. Pour une opération
protégée, l'ordre réel est :

```text
autorité canonique (prelaunch)
-> checkpoint/backoff
-> consommation CAS du retry budget au lancement
-> circuit check / lease half-open
-> ledger reserve puis RESERVED -> IN_PROGRESS
-> exactement un appel inner runner
-> finalisation ledger
-> enregistrement outcome circuit
```

Il n'existe aucune double exécution ni retry CAS. Un conflit ledger post-call
produit `LEDGER_FINALIZATION_CONFLICT` et exige recovery/reconciliation ; il ne
relance jamais l'appel. Un conflit de bookkeeping circuit survient après la
finalisation ledger et ne peut donc jamais réécrire l'effet connu en `NONE`.

## 27. Périmètre idempotent final

Le périmètre issu des descriptors canoniques est :

| Route/cible | Effect ledger | Règle |
| --- | ---: | --- |
| T02/T03 | oui | clé caller obligatoire, succès `COMMITTED` |
| A02/A03 | oui | clé caller obligatoire, succès `COMMITTED` |
| R01/R02/R03/A01 | non | aucune identité synthétique |
| AGENT baseline | non | aucune identité synthétique |
| GATE/JOIN/DECISION/RUNTIME | non | comportement 12.10 délégué |

Changer le binding technique change la clé circuit mais ne constitue ni un
fallback ni une permission de changer la cible ou l'intention.

## 28. Recovery ABANDONED

Une réservation expirée passe explicitement `RESERVED -> ABANDONED` par CAS.
La réactivation n'est possible qu'après revalidation complète de l'autorité, du
budget, du snapshot et du circuit, avec identité et `record_id` identiques,
`version + 1`, attempt ledger 0 et `attempt_count` runtime 0.

Cette reprise n'est pas un retry et ne consomme aucun retry budget. La transition
directe `ABANDONED -> IN_PROGRESS` est interdite ; la réactivation repasse par
`RESERVED` avant le start normal.

## 29. RetryFailureFacts

`RetryFailureFacts` est l'unique projection crash-safe de l'échec. Elle contient
exactement :

- `error_code` ;
- `category` ;
- `retryable` ;
- `recommended_action` ;
- `source`.

Elle ne contient ni message libre, details, payload, stack ou réponse provider.
La reconstruction d'un `ErrorEnvelope` utilise un message constant et les seuls
faits fermés persistés.

## 30. Pipeline RETRY_REQUIRED

Le pipeline exige un step décisif unique, le record exact `FINALIZED/NONE`, des
retry facts sûrs, la revalidation par le guard 12.10, le budget courant, la
fraîcheur snapshot, `ReplayGuard`, `RetryPolicy`, puis un checkpoint.

Si la décision est `RETRY`, le step passe à `PENDING` avec `attempt_count`
préservé. Aucune exécution immédiate n'a lieu. `PlanExecutor` incrémente l'attempt
au cycle suivant ; le runner consomme une seule unité de retry budget au
lancement. Avant `not_before`, le prelaunch bloque sans dormir.

## 31. Pipeline RECONCILIATION_REQUIRED

Une reconciliation au maximum est effectuée par cycle :

```text
STILL_UNKNOWN  -> RECONCILE, aucun retry
MANUAL_REQUIRED -> MANUAL_REQUIRED, aucun retry
PARTIAL        -> MANUAL_REQUIRED, aucun retry
COMMITTED      -> RESULT_RECOVERY_REQUIRED, aucun replay
NONE/RESOLVED  -> pipeline retry complet uniquement
```

Invariant central :

```text
COMMITTED != SUCCEEDED
```

Sans receipt terminal trusted, un effet commis avec résultat perdu exige la
récupération du résultat et ne permet ni succès inféré ni nouvel appel.

## 32. Scénarios crash/restart

| Scénario | Décision sûre |
| --- | --- |
| crash avant effet, réservation active | attente/blocage, aucun second appel |
| réservation expirée | ABANDONED puis réactivation explicitement revalidée |
| crash pendant effet | reconciliation obligatoire |
| crash après effet avant résultat | `UNKNOWN`, reconciliation obligatoire |
| crash après ledger commit avant snapshot | ledger courant gagne ; aucun replay |
| snapshot stale | stop/replan selon dimension stale |
| ledger `UNKNOWN` | reconciliation avant toute reprise |
| `PARTIAL` | manuel, aucun retry automatique |
| `MANUAL_REQUIRED` | manuel, aucun retry |
| gate expirée | stop |
| permission révoquée | stop |
| budget épuisé/inconnu | stop |
| circuit `OPEN` | condition requise, aucun appel |
| `HALF_OPEN` concurrent | une seule lease/candidat |
| backoff pending | condition requise, aucun sleep/attempt |

Dans tous ces scénarios, aucune double exécution n'est autorisée.

## 33. Matrice d'autorité finale

La chaîne d'autorité reste :

```text
TOOL        -> ALLOW
APPLICATION -> REQUEST
AGENT       -> DELEGATE
GATE        -> APPROVED -> trusted facts
RUNTIME     -> orchestration
RECOVERY    -> technical admissibility only
```

Recovery n'est pas une sixième autorité d'effet. Resolvers, ledger, snapshots,
budgets, probes, retry et circuit ne peuvent créer `ALLOW`, `REQUEST`,
`DELEGATE`, `APPROVED`, validation ou promotion.

## 34. Audit sécurité final

L'audit du delta de production et les fitness tests ne trouvent aucun secret ou
credential, clé d'idempotence brute persistée, payload/path brut persisté, SDK
provider, HTTP/réseau, DB/ORM, filesystem de production, subprocess/shell,
sleep/polling, worker/queue, retry loop, CAS retry, import dynamique/reflection,
fallback/provider switch, clé synthétique, replay d'effet
`UNKNOWN/PARTIAL/COMMITTED`, reset de budget/attempt, restore stale ou store
mutable caché de production.

Les occurrences de `payload` dans l'intégration servent uniquement à produire
les octets canoniques immédiatement hashés pour le fingerprint d'intention ; le
payload brut n'entre ni dans `IdempotencyIdentity`, ni dans le ledger, ni dans le
snapshot. Les messages recovery persistables sont fermés et minimaux.

```text
SECURITY_AUDIT = PASS
BLOCKING_FINDINGS = 0
```

## 35. Rationalisation finale

Les ports, policies, engines, coordinators, guards, runners, resolvers,
références snapshot, projections d'erreur et helpers CAS ont été comparés selon
leur sémantique, leurs invariants, leur autorité et leur cycle de vie.

Les ressemblances de forme ne justifient pas de fusion : ledger et lease circuit,
budget et step state, snapshot et état métier, guard d'autorité et ReplayGuard,
orchestration et recovery ont des responsabilités distinctes. Les fakes test-only
ne sont pas consolidés avec les ports de production. Aucun finding réel ne
justifie une refactorisation H3.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## 36. Validations et métriques finales H3

Toutes les validations ont été réellement exécutées sur `main` avec le Python de
la `.venv` du dépôt :

| Validation | Résultat observé |
| --- | --- |
| Python | 3.12.13 |
| Suites G réelles | 32 PASS |
| Régression workflows et routes explicites | 75 PASS |
| Tous les tests recovery touchés B à G, 37 fichiers | 327 PASS |
| Suite globale | 3 040 PASS |
| `python -m compileall -q backend` | PASS |
| Ruff | PASS |
| mypy `backend` | PASS, 576 fichiers source |
| `git diff --check` | PASS |
| diff-check baseline fonctionnelle vers SHA G | PASS |

La régression workflow exécutée couvre les scénarios canoniques, les routes
runtime, WF-0, WF-2, WF-4, WF-5, WF-6, WF-7, WF-10, WF-11 et les plans TOOL
explicites T02/T03. Les valeurs ci-dessus sont les résultats observés lors de H3.

## 37. Dépendances

La lecture réelle de `[project].dependencies` dans `pyproject.toml` donne :

```text
[]
```

Aucune dépendance runtime, provider, framework ou store concret n'est ajoutée.

## 38. Lignée Git, delta et mode de merge

La lignée fonctionnelle exacte est :

```text
24d19c6f1420f847e68a55b1afacf1e84a022ef1  feat: establish idempotent effect ledger boundary
390e378e981d3bfd4636d3167452785fe5491c48  feat: establish recovery budget and snapshot state
cba8f084a76ce720d0b51d0b80fc377e2538cf6a  feat: establish effect reconciliation boundary
cf899415a97aaa314d752725c4287a92a5f71c16  feat: establish replay and retry policy boundary
be16d44c19db30295a326c39c3d5d7ed36350b8f  feat: establish circuit breaker recovery boundary
06aa0d28768cd5888eb9d42fe09073c5faadab89  feat: integrate deterministic runtime recovery
```

Le delta réel depuis `c708037e5efd5602a64604c70126e8f376d063d5` est :

```text
79 files changed, 16273 insertions(+)
0 suppression nette
0 merge commit
```

La classification est : 22 fichiers production recovery, 6 ADR, 6 documents de
baseline, 37 fichiers de tests, 8 fakes/support dont une modification bornée du
fake de routing. Aucun module métier ou agent spécialisé n'a été déplacé.

Le mode de merge est exclusivement :

```text
MERGE_MODE = FAST_FORWARD_ONLY
```

Le commit documentaire H3 doit avoir pour parent exact le SHA fonctionnel
`06aa0d28768cd5888eb9d42fe09073c5faadab89`, modifier uniquement ce document et
laisser les refs locale/distante de la branche fonctionnelle sur ce SHA.

## 39. Responsabilités différées et handoff Phase 12.12

Restent différés hors 12.11 : stores/adapters réels, calibration empirique des
budgets et timeouts, jitter/provider tuning, fallback/provider selection,
poison-task registry, compensation métier et recovery automatique d'un résultat
terminal sans receipt trusted.

Le prochain lot canonique est :

```text
NEXT_PHASE = 12.12
PHASE_12_12_SCOPE = GLOBAL_SECURITY_HARDENING
```

Libellé canonique : **Hardening sécurité global**.

12.12 devra reprendre les surfaces différées de prompt injection, tool
injection, data/document injection, multi-agent security hardening,
authority-smuggling global, exfiltration et isolation des secrets, propagation
de contenu hostile et frontière globale `SecurityEvent`. L'observabilité reste
explicitement réservée à 12.13 et n'est pas implémentée ici.

## 40. Décision finale

Le code fonctionnel intégré est identique au SHA G, les audits post-merge sont
conformes, toutes les validations finales passent, les dépendances runtime
restent vides et le seul changement H3 est ce livrable canonique.

```text
PHASE 12.11-H3 — PASS / CLOSED
PHASE 12.11 — CLOSED / MERGED
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_MODE = FAST_FORWARD_ONLY
NEXT_PHASE = 12.12
```
