# ADR-P12-049 — Frontière offline du harness d'évaluations agentiques

## Statut

Accepté pour la Phase 12.14-B.

## Contexte

La baseline 12.13 fournit le runtime agentique, ses frontières Tool/Application,
les agents AG-01 à AG-04, Gate, security, recovery, observability et un paysage
pytest important. Elle ne possède aucun contrat canonique pour décrire un cas,
une suite ou un résultat d'évaluation offline.

Le module `backend/modules/quality_evaluation` est réservé au futur domaine
métier de qualité. Un harness de test ne peut pas en devenir l'owner. De même,
un résultat d'évaluation ne peut ni valider le métier, ni accorder une
permission, ni approuver une gate, ni décider d'un retry/replay, ni modifier une
décision de sécurité.

## Décision

### Emplacement offline

Le core vit dans le package top-level :

```text
evaluation_harness/
  contracts/
```

Ce package est une bibliothèque offline data-only. Les tests, fakes et futurs
adapters pytest restent sous `tests/`. Aucun fichier de
`backend/modules/quality_evaluation` n'est modifié ou importé.

### Direction des dépendances

Le graphe autorisé est :

```text
evaluation_harness -> stdlib
evaluation_harness -> backend.shared_kernel._value_safety
tests              -> evaluation_harness
tests              -> tests/support
```

La dépendance au classificateur partagé évite un second scanner de secrets ou
de chemins privés. Aucun type d'autorité ou contrat runtime n'est réutilisé.

Le graphe interdit est :

```text
backend             -> evaluation_harness
evaluation_harness  -> tests
evaluation_harness  -> pytest
evaluation_harness  -> backend.agent_runtime
evaluation_harness  -> backend.infrastructure
evaluation_harness  -> backend.modules.quality_evaluation
evaluation_harness  -> provider SDK
```

### Distinction avec pytest

Pytest demeure le runner, le collecteur, le mécanisme de sélection et le moteur
d'assertions de la suite existante. Le package offline décrit seulement des
objets immutables. Il n'exécute, ne collecte et ne rapporte aucun test.

### Versioning

Le harness possède `EvaluationSchemaVersion` et la baseline explicite `1.0`.
Cette version n'est ni convertible ni substituable à une version des contrats
runtime. Les contrats B acceptent uniquement les versions déclarées dans leur
registre offline fermé.

### Verdict

`EvaluationVerdict` est un `Enum` fermé, et non un `StrEnum` :

```text
PASS | FAIL | INCONCLUSIVE | ERROR | SKIPPED
```

- `PASS` : tous les critères applicables sont satisfaits ;
- `FAIL` : au moins un critère normatif est violé ;
- `INCONCLUSIVE` : les observations ne permettent pas de conclure ;
- `ERROR` : le harness ne peut exécuter ou interpréter l'évaluation ;
- `SKIPPED` : le cas n'est volontairement pas exécuté.

Le choix d'un `Enum` ordinaire empêche l'égalité implicite avec une chaîne ou un
autre `StrEnum` de même valeur.

```text
PASS != ALLOW
PASS != APPROVED
PASS != SUCCEEDED
PASS != COMMITTED
PASS != SECURITY_ACCEPTANCE
```

### Targets, tags et refs

Le vocabulaire target minimal est `SYSTEM`, `WORKFLOW`, `AGENT`, `PIPELINE`,
`BOUNDARY`, `COMPONENT`. `EvaluationTargetRef` associe un kind à un code opaque
et ne résout rien.

Les identités et refs sont caller-supplied, typées, bornées à 128 caractères et
limitées aux caractères alphanumériques, point, underscore et tiret. Les chemins,
URLs, espaces et valeurs reconnues sensibles sont refusés. Aucun UUID ou hash
n'est produit implicitement.

Les tags sont des `EvaluationTagCode` minuscules normalisés, bornés à 64
caractères, uniques et limités à 16 par objet. Ils sélectionnent des évaluations
mais ne confèrent aucune autorité. Aucun tag fournisseur ou modèle n'est défini
en B.

### Case et suite

`EvaluationCase` référence un target, une factory d'input, une fixture
optionnelle et des assertion refs opaques. Il ne contient ni callable, payload,
prompt, mapping libre, permission, gate fact ou route d'exécution.

`EvaluationSuite` embarque directement des cases ordonnés. Cette composition
évite un registry et interdit naturellement les suites imbriquées. Les case IDs
sont uniques. `EvaluationInfrastructureErrorPolicy` contient `CONTINUE` et
`ABORT_SUITE` ; un `FAIL` de cas n'est jamais une erreur d'infrastructure.

### Résultats minimaux

B crée uniquement :

```text
CaseExecutionResult
CaseEvaluationResult
SuiteEvaluationResult
```

`AssertionResult` appartient à C et `ScoreResult` à D. Les résultats B ne
contiennent que versions, IDs, statuts/verdicts, refs d'observation, durées
caller-supplied et codes fermés. Aucun output, exception, prompt, contenu
Evidence ou raisonnement privé n'est stocké.

Une suite `PASS` exige uniquement des cases `PASS`. Un `FAIL`, `ERROR`,
`INCONCLUSIVE` ou `SKIPPED` ne peut donc pas être transformé silencieusement en
`PASS`.

### Erreurs d'infrastructure

Les erreurs brutes sont exclues des contrats. Une exécution en erreur porte
seulement un `EvaluationReasonCode` borné. La future policy E interprétera
`CONTINUE` ou `ABORT_SUITE`. Un échec normatif de case reste un `FAIL` et ne
déclenche jamais implicitement l'arrêt de suite.

### Autorité et séparation des owners

```text
EVALUATION_RESULT_NEVER_CREATES_AUTHORITY
EVALUATION_RESULT != DOMAIN_VALIDATION
EVALUATION_RESULT != GATE_APPROVAL
EVALUATION_RESULT != SECURITY_DECISION
EVALUATION_RESULT != RECOVERY_DECISION
EVALUATION_RESULT != OBSERVABILITY_FACT
```

Les observations 12.13 peuvent devenir des inputs explicites d'assertion, mais
ne deviennent pas des résultats d'évaluation. Les contrats n'importent aucun
owner runtime, Gate, security, recovery ou observability.

### Limites

La baseline impose : title 256, identités 128, 16 tags, 64 assertion refs,
256 cases par suite, 100 répétitions déclarées, timeout maximal 86 400 secondes,
64 observation refs et 32 reason codes par résultat. Ce sont des limites offline
indépendantes d'`AgentRuntimePolicy`.

### Agrégation et invariants réservés

La cohérence structurelle suivante est établie sans moteur de scoring :

```text
FAIL cannot become PASS by score
ERROR cannot silently become PASS
INCONCLUSIVE cannot silently become PASS
SKIPPED is not PASS
HARD_INVARIANT_FAILURE_CANNOT_BE_HIDDEN_BY_WEIGHTED_SCORE
```

Le calcul des scores et invariants reste différé.

## Scopes différés

- C : assertion specs, policies et hard invariants ;
- D : scores, rubrics et agrégation ;
- E : runner, fixtures, répétitions et timeouts ;
- F : reporting, comparaison et artifacts ;
- G : intégration aux frontières agent/runtime ;
- 12.15 : scénarios pédagogiques canoniques ;
- 12.16 : fournisseurs, modèles et calibration.

## Conséquences

Le dépôt obtient un langage contractuel offline, immutable et provider-neutral
sans second runtime de test. Le coût assumé est une frontière top-level et un
versioning propres, protégés par des tests d'architecture.

```text
RATIONALIZATION = NO_DUPLICATE_TEST_RUNTIME_CREATED
```
