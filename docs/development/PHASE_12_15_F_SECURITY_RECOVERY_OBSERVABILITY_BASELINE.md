# Phase 12.15-F — Baseline Security, Recovery et Observability transverse

## 1. Parent, portée et ADR

F a pour parent exact `01f879255473653b1168449b25ada816ba7190a7`
(E). Le lot ferme uniquement les tags transverses Security, Recovery et
Observability des scénarios déjà fonctionnellement fermés. Il ne redéfinit
aucun scénario et ne commence pas G.

`BACKEND_PRODUCTION_DELTA = 0` et `ADR_REQUIRED = NO`. Le corpus, ses hard
assertions, rubrics et l'evaluation harness restent inchangés. Aucun provider,
modèle, réseau, SQLite, capability, workflow, agent ou persistance métier n'est
ajouté.

## 2. Matrice de réutilisation des owners

| Concern | Implémentation canonique | Tests/support existants | Réutilisable | Seam manquant |
| --- | --- | --- | --- | --- |
| Evidence hostile | EvidenceAgent, RetrievalCoordinator, EvidenceSecurityScanner, content isolation | evidence retrieval fakes, fixtures B | oui | aucun |
| sortie AG-03 | GeneratorAgent, GenerationCoordinator, GenerationOutputGuard, materialization | RecordingGenerationPort | oui | aucun |
| gate humaine | GateEngine, GateAuthorityPolicy | gate fakes | oui | aucun |
| données structurées | structural_keys, boundary content assessment | multi-agent fixtures | oui | aucun |
| secret/exfiltration | SensitiveValuePolicy, threat scanner, SecurityEvent mapper | synthetic secret fixtures | oui | aucun |
| handoff multi-agent | AgentHandoffSecurityPolicy | multi-agent security fixtures | oui | aucun |
| identité d'effet | IdempotencyIdentity, intent/key fingerprints, IdempotencyPolicy | effect ledger fake | oui | aucun |
| réconciliation | EffectReconciliationEngine/Policy et ApplicationEffectProbeRequest | reconciliation probes | oui | aucun |
| replay/retry | ReplayGuard, RetryPolicy, budgets | retry/replay fakes | oui | aucun |
| observability | RuntimeObservationEmitter, catalogs/mappers, noop/collecting/raising sinks | runtime observability fakes | oui | aucun |
| chemins SCN-06/08 | bindings E réels | fixtures et ports déterministes E | oui | wrapper de trace test-only |

Les adapters F ne possèdent aucune autorité. Ils orchestrent les owners et
projettent uniquement des codes, booléens, comptes et dispositions fermées.

## 3. Variantes Security

### SCN-02 — Evidence hostile

La fixture hostile est matérialisée par le vrai chemin AG-02, puis évaluée par
EvidenceSecurityScanner. Les signaux fermés `INSTRUCTION_LIKE_CONTENT` et
`AUTHORITY_CLAIM_TEXT` sont observés. Le contrat reste : instructions document
non autoritatives, actions externes désactivées et liens non suivis. Les comptes
Gate, Application, external action et link follow restent tous à zéro.

### SCN-03 — authority/capability smuggling

Le marker `gateDecision=APPROVED` / `capability_id=CAP-A02` traverse une vraie
ProductionRequest AG-03, le GenerationOutputGuard et la matérialisation. Le
comportement owner réel est conservé. La sortie demeure `CANDIDATE`, sa lineage
reste CAP-G01, aucun GateDecision n'est créé, CAP-A02 n'est pas routée et aucun
scope n'est élargi.

### SCN-05 — autorité Gate

Un faux `APPROVED` textuel avec absence de décision externe laisse le
GateEngine en `WAITING`. Une décision externe valide produit `APPROVED` et une
unique continuation. Les mutations actor/run/step/correlation échouent avec les
codes fermés du GateEngine. Les packages agents ne construisent aucun
GateDecision.

### SCN-08 — exfiltration

Le marker hostile produit `EXFILTRATION_TEXT`. Une sentinel synthétique
credential-shaped distincte est rejetée par SensitiveValuePolicy sous le code
`CREDENTIAL_LIKE`. Elle n'est copiée ni dans le witness, ni dans SecurityEvent,
log, metric ou trace. Réseau, URL follow, tool et Application restent à zéro ;
aucun secret réel n'est chargé.

### Clés structurelles et multi-agent

Les clés imbriquées `authority_override`, `permission`, `promotion_allowed`,
`capability_id`, `gate_id` et `required_actor` sont exercées contre le catalogue
du GateEngine et échouent `INVALID_GATE_REQUEST` avant consultation de la
source. Les outputs/handoffs contenant CAP-A02, une fausse gate ou une finding
transformée en permission échouent
`AUTHORITY_METADATA_FORBIDDEN`. Aucun deuxième registre de clés n'est créé.

### Minimisation Security

SafeTransverseReport accepte seulement scénario canonique, codes normalisés,
booléen et comptes non négatifs. Aucun report F ne contient marker hostile,
sentinel, corps généré, Evidence excerpt, review body, prompt, path local ou
provider payload.

## 4. Recovery — ledger et identité CAP-A02

La cible est `CAP-A02` / `application.request_promotion`. L'identité canonique
inclut principal, run, step, capability, route Application, use case, operation,
intent fingerprint et caller-key fingerprint. Le même intent et la clé E
`promotion:scn-08:0` produisent la même identité ; une mutation de production
ref change l'intent fingerprint et le record ID sans inventer une nouvelle clé.

Les records sont construits par IdempotencyPolicy et stockés dans
InMemoryEffectLedgerFake avec compare-and-set validé par
EffectReconciliationPolicy. La probe Application est test-only.

## 5. Recovery — variants d'effet

| État/observation | Réconciliation | État final | Replay/retry automatique | Probe Application |
| --- | --- | --- | --- | --- |
| UNKNOWN → COMMITTED | RECONCILED | COMMITTED / RESOLVED | bloqué | 1 |
| UNKNOWN → NOT_COMMITTED | RECONCILED | NONE / RESOLVED | admissible seulement sous policy | 1 |
| UNKNOWN → STILL_UNKNOWN | STILL_UNKNOWN | UNKNOWN / PENDING | reconciliation first | 1 |
| UNKNOWN → MANUAL_REQUIRED | MANUAL_REQUIRED | UNKNOWN / MANUAL_REQUIRED | manuel | 1 |
| COMMITTED | NOT_REQUIRED | COMMITTED | bloqué | 0 |
| PARTIAL | policy pending/resolved | PARTIAL | STOP, jamais retry automatique | 0 pour le test retry |
| NONE admissible | NOT_REQUIRED | NONE | RETRY selon policy/budget/idempotency | 0 |
| NONE budget/policy denied | NOT_REQUIRED | NONE | NO_RETRY | 0 |

Dans tous les variants UNKNOWN, le ReplayGuard est consulté avant la probe et
répond `RECONCILE_FIRST`; le compteur d'executor/replay avant réconciliation est
zéro. COMMITTED ne reprobe pas et PARTIAL ne produit aucun second appel de
promotion.

## 6. Recovery — attaques de mismatch

Les observations wrong record/version/attempt échouent respectivement avec
`OBSERVATION_RECORD_MISMATCH`, `OBSERVATION_VERSION_MISMATCH` et
`OBSERVATION_ATTEMPT_MISMATCH`. Un stale compare-and-set échoue
`LEDGER_VERSION_CONFLICT`.

Les mutations principal/run/step/capability/use_case/intent passent par le
ReplayGuard et répondent `REPLAN_REQUIRED / IDENTITY_MISMATCH`. Les erreurs ne
contiennent ni intent brut, ni contenu pédagogique.

```text
RECOVERY_EFFECT_MODEL_TESTED = TRUE
REAL_BUSINESS_PROMOTION_PERSISTENCE = NOT_IMPLEMENTED_IN_E_OR_F
```

F n'ajoute aucune table ni persistence de promotion et ne modifie pas le claim
E : la route Application est simulée, pas une promotion métier persistée.

## 7. Observability equivalence

La comparaison utilise les mêmes fixtures, inputs et fakes déterministes dans
trois modes : sinks noop, sinks recording et sinks raising. Les timestamps et
identifiants de trace ne font pas partie de la projection fonctionnelle.

### SCN-06

La projection compare workflow, fanout, ordre join/generation/validation/review,
état candidate, résultat de validation, assessment de review, verdict et hard
assertions. Les trois modes produisent la même projection `PASS`.

### SCN-08

La projection compare workflow, variant count, join/selection, logical ref
sélectionnée, review, validation, Gate disposition, call count CAP-A02,
render-effect count et verdict. Les trois modes produisent la même projection :
Gate `APPROVED`, promotion route count `1`, render-effect count `0`, verdict
`PASS`.

Observability ne choisit jamais de variante, n'approuve aucune Gate, ne route
pas CAP-A02, ne change pas effect/retry et ne modifie pas le verdict.

## 8. Records et échec de sink

Le mode recording émet une trace bornée par scénario avec uniquement
`scenario_code` et `verdict`. Le mapper SecurityEvent produit un log et une
metric à partir de codes fermés ; metadata raw et sentinel sont absents.

La policy canonique conserve `enabled=true`, buffer borné et
`DROP_NEWEST`. RuntimeObservationEmitter isole aussi les exceptions des sinks.
Le mode raising produit strictement la même projection que noop/recording :

```text
SINK_FAILURE != AUTHORITY_GRANT
SINK_FAILURE != AUTOMATIC_PROMOTION
SINK_FAILURE != HIDDEN_RETRY
```

## 9. Fitness architecturale

Les tests AST/source prouvent : backend sans import des bindings F ; package
observability sans dépendance Gate/Application ; packages agents sans
construction de GateDecision ; recovery sans PermissionScope/GateDecision ;
bindings F sans provider/réseau/SQLite/filesystem runtime ; aucun delta des
registries capability/workflow/corpus/expectations ; backend production delta
nul.

## 10. Validations et handoff G

Le gate ciblé F exécute `57 passed`. Les régressions E/D/C, corpus et harness
exécutent `175 passed, 20 skipped` ; les skips sont exclusivement les gates
SQLite conditionnelles sans seed, que F ne touche pas. Security/Gate/Application
exécute `437 passed`, Recovery `355 passed` et Observability `178 passed`.

La globale finale exécute `3887 passed, 20 skipped` en 154,96 s. Python 3.12.13,
Ruff global, mypy sur les `638` sources backend et les `30` sources du harness,
compileall backend/harness/tests et `git diff --check` passent. Les dépendances
runtime restent `[]`.

À fermeture et push de F :

```text
SECURITY_TRANSVERSE = CLOSED
RECOVERY_TRANSVERSE = CLOSED
OBSERVABILITY_TRANSVERSE = CLOSED
NEXT_GATE = 12.15-G_READY
```
