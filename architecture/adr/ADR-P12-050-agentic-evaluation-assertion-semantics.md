# ADR-P12-050 — Sémantique des assertions agentiques offline

## Statut

Accepté pour la Phase 12.14-C.

## Contexte

ADR-P12-049 a établi les contrats du harness offline et laissé les
`assertion_refs` opaques. C doit leur donner une sémantique normative sans
créer un second runner de tests, anticiper le scoring, ni prendre l'autorité
des owners runtime.

Les observations peuvent inclure des fixtures synthétiques adversariales. Leur
contenu doit donc être évaluable sans être persisté dans les specs ou résultats.

## Décision

### Assertions data-only

Le vocabulaire fermé est : `EXACT`, `STRUCTURAL`, `COUNT`, `SEQUENCE`,
`MEMBERSHIP`, `RANGE`, `FORBIDDEN_CONTENT`, `INVARIANT`.

Chaque kind possède une dataclass frozen/slotted spécialisée. Les specs portent
uniquement une version, une assertion ref, des observation refs et les petits
paramètres strictement nécessaires. Elles n'embarquent ni valeur attendue
brute, mapping libre, metadata, callable, predicate, expression Python ou
import path.

Une assertion du harness n'est ni une assertion pytest, ni un score, ni une
validation métier, ni une décision d'autorité. Les assertions C sont des
contrôles normatifs durs ; les qualités graduées appartiennent à D.

### Valeurs d'observation canoniques

Le modèle offline immutable est une algèbre fermée :

```text
ObservationScalar(None | bool | int | Decimal | str)
ObservationSequence(tuple[value, ...])
ObservationObject(tuple[ObservationField, ...])
```

Les objets conservent l'ordre des champs et imposent des codes uniques. Les
scalaires distinguent explicitement leurs kinds : `True` n'est pas `1`. Les
floats sont exclus pour éviter NaN, Inf et les ambiguïtés binaires. Les Decimal
doivent être finis et bornés.

Les limites sont indépendantes d'`AgentRuntimePolicy` : profondeur 8, séquence
64, champs d'objet 32, chaîne 4 096 caractères et graphe total 512 nœuds. Les
entiers et Decimal ont aussi des bornes explicites.

Une chaîne d'observation peut contenir un contenu synthétique interdit. Elle
n'est donc pas soumise au classificateur de secrets des identités. Elle reste
éphémère, bornée, non exportée et n'est jamais copiée dans `AssertionResult`.

### Résolution explicite

`EvaluationObservationSourcePort` résout une ref vers une valeur canonique.
L'instance est injectée dans `AssertionEvaluator` ; le core ne fait aucune I/O
implicite et ne possède aucune source globale. Une ref est résolue au plus une
fois durant l'évaluation d'une assertion, via un cache local éphémère.

`EvaluationAssertionCatalog` relie un tuple ordonné de specs à leurs refs. Il
est immutable, borné à 512 specs, refuse les doublons et effectue une résolution
déterministe. Il ne constitue pas un registre d'autorité.

### Sémantique pure

- `EXACT` compare le type canonique et la valeur profonde.
- `STRUCTURAL` compare les kinds, longueurs, ordre/codes de champs et formes
  imbriquées, sans comparer les valeurs scalaires.
- `COUNT` compare exactement la taille d'une séquence ou d'un objet canonique.
- `SEQUENCE` exige deux séquences et compare ordre et valeurs canoniques.
- `MEMBERSHIP` cherche une valeur canonique dans une séquence par égalité
  profonde, sans invoquer un objet runtime.
- `RANGE` accepte seulement int/Decimal, au moins une borne et une inclusivité
  explicite. Une valeur hors plage est `FAIL`; un type ou intervalle invalide
  est `ERROR`.
- `FORBIDDEN_CONTENT` effectue une recherche littérale, éventuellement par
  Unicode `casefold`, sur des chaînes résolues par refs. Aucun texte, motif,
  extrait ou index n'entre dans le résultat.
- `INVARIANT` délègue un code borné à `InvariantEvaluatorPort` avec une seule
  projection offline. Le checker observe le résultat d'un owner canonique ; il
  ne réimplémente pas sa policy.

`AssertionEvaluator` évalue exactement une spec et ne modifie aucun état
externe. Il n'exécute ni case, suite, répétition, retry ou timeout. Il ne produit
ni métrique, log, artifact ou événement sécurité.

### Containment et résultat

Les erreurs d'une source ou d'un checker injecté sont contenues en
`EvaluationVerdict.ERROR` avec un reason code fermé. Aucun message ou objet
d'exception n'est copié ou journalisé automatiquement. Une invariant peut
retourner seulement `PASS`, `FAIL` ou `INCONCLUSIVE`; C ne produit pas
`SKIPPED` au niveau assertion.

`AssertionResult` contient uniquement version, ref, kind, verdict et reason
code fermé. Il ne porte ni actual, expected, diff, message, exception, payload,
path ou valeur brute.

### Intégration au résultat de case

Option A est retenue : `CaseEvaluationResult` reçoit
`assertion_results: tuple[AssertionResult, ...] = ()`. Le défaut conserve la
construction B. Un case `PASS` ne peut contenir une assertion non-PASS et un
case `SKIPPED` ne contient aucune assertion. Aucun second résultat de case n'est
créé et aucun scoring n'est introduit.

```text
ASSERTION_FAIL_CANNOT_BE_HIDDEN_BY_SCORE
HARD_INVARIANT_FAILURE_CANNOT_BE_HIDDEN_BY_WEIGHTED_SCORE
```

### Autorité et frontières

```text
ASSERTION_RESULT_NEVER_CREATES_AUTHORITY
ASSERTION_FAILURE_NEVER_MUTATES_RUNTIME
ASSERTION_INPUT_VALUE_IS_EPHEMERAL_OFFLINE_DATA
ASSERTION_RESULT_NEVER_COPIES_RAW_OBSERVATION_VALUE
ASSERTION_SPEC_NEVER_CONTAINS_ARBITRARY_CALLABLE
ASSERTION_SPEC_NEVER_CONTAINS_ARBITRARY_METADATA
INVARIANT_CODE_NEVER_BECOMES_DOMAIN_POLICY
NO_GLOBAL_MUTABLE_ASSERTION_REGISTRY
NO_GLOBAL_MUTABLE_INVARIANT_REGISTRY
PRODUCTION_RUNTIME_MUST_NOT_DEPEND_ON_EVALUATION_HARNESS
```

Le graphe d'ADR-P12-049 est inchangé. Le seul import `backend.*` autorisé reste
`backend.shared_kernel._value_safety`; C n'en ajoute aucun.

## Scopes différés

- D : score, rubric, pondération et agrégation douce ;
- E : runner, fixtures, répétitions, timeouts et isolation ;
- F : sérialisation, rapports et artifacts ;
- G : projection des résultats runtime vers les observations et adapters
  d'invariants ;
- 12.15 : scénarios pédagogiques ;
- 12.16 : fournisseurs, modèles et calibration.

## Conséquences

Le harness peut interpréter les assertion refs de B avec des valeurs bornées et
des résultats sans donnée brute. Le coût assumé est une projection explicite
des objets runtime par les futurs adapters G et une taxonomie volontairement
fermée.

```text
RATIONALIZATION = ASSERTION_SEMANTICS_REUSE_EXISTING_TEST_OWNERS
```
