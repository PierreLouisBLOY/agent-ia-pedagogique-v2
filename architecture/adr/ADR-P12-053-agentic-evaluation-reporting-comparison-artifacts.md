# ADR-P12-053 — Reporting, comparaison et artifacts d'évaluation sûrs

## Statut

Accepté pour la Phase 12.14-F.

## Contexte

B définit les cases et résultats, C les assertions hard, D le scoring rationnel
et E le lifecycle par répétition. F doit rendre ces résultats lisibles et
comparables sans devenir une nouvelle source d'autorité, sans relire les
observations et sans intégrer le runtime.

```text
REPORTING_IS_PROJECTION_NOT_AUTHORITY
MINIMIZATION_BEFORE_RENDERING
```

## Audit de reportability

| Champ source | Reportable | Raison | Machine | Markdown | Clé de comparaison |
| --- | --- | --- | --- | --- | --- |
| schema/version | oui | versionne le contrat | oui | oui | suite |
| suite/case ID et code | oui | identité opaque sûre | oui | oui | oui |
| title | non | surface libre inutile | non | non | non |
| repetition index | oui | attribution exacte | oui | oui | oui |
| execution status/verdict | oui | état déjà décidé | oui | oui | oui |
| reason codes fermés | oui | diagnostic borné | oui | oui | non |
| assertion ref/kind/verdict | oui | trace hard minimale | oui | oui | ref |
| criterion/scorer ref/status/score | oui | trace soft exacte | oui | oui | criterion ref |
| rubric ref/status/score/criteria refs | oui | sortie D existante | oui | oui | rubric ref |
| duration test-only | oui | mesure bornée existante | oui | oui | non |
| infrastructure error | oui | fait structurel existant | oui | oui | non |
| observation refs | non | inutile au report général | non | non | non |
| observation values | non | donnée brute interdite | non | non | non |
| target/input/fixture output | non | objet brut/runtime | non | non | non |
| exception/message/traceback | non | fuite potentielle | non | non | non |
| prompt/evidence/provider response | non | contenu privé ou externe | non | non | non |
| arbitrary metadata/payload | non | canal non borné | non | non | non |

## Décision

### Modèle de report

Le package `evaluation_harness.reporting` possède une hiérarchie immutable,
frozen/slotted et bornée : suite, case, répétition, assertion, score et rubric.
Les tuples gardent l'ordre source et les identités sont uniques.

Les résultats B/C/D plats restent reportables au niveau case. Leurs exécutions
sont projetées comme répétitions dont le verdict est explicitement non attribué
plutôt que d'inventer une sémantique. Les résultats E conservent leurs
évaluations exactes par répétition.

Le format possède `EvaluationReportSchemaVersion(1, 0)`, indépendant du schema
d'évaluation. Aucun UUID, timestamp, hostname, user ou path n'est généré.

### Projector

`EvaluationReportProjector` reçoit `EvaluationSuite` et
`SuiteEvaluationResult`. Il exige suite ID, schema, case IDs et ordre identiques.
Il ne corrige aucune divergence, ne relance ni runner, assertion, score ou
runtime et ne mute pas les sources.

```text
REPORT_NEVER_CREATES_AUTHORITY
REPORT_NEVER_MUTATES_SOURCE_RESULT
REPORT_NEVER_RECOMPUTES_RUNTIME_DECISION
```

### JSON canonique

Le renderer JSON utilise uniquement une construction allowlistée explicite et
`json.dumps` stdlib avec clés triées, séparateurs canoniques, UTF-8,
`allow_nan=False`. Il n'utilise ni `asdict`, ni `default=str`.

Les scores sont des objets exacts `{numerator, denominator}`. Aucun float ou
arrondi n'est produit. La limite canonique est 2 000 000 octets ; une limite
plus stricte peut être injectée pour un canal donné. Tout dépassement est
refusé par `ReportSizeLimitError`, sans truncation.

### Markdown

Le renderer Markdown expose la même surface minimisée. Les IDs/codes sont
échappés pour les caractères Markdown et aucun HTML ou title n'est émis. Les
scores restent `numerator/denominator`.

### JUnit

```text
JUNIT_BRIDGE_DEFERRED_UNTIL_CI_USE_CASE
```

Aucun workflow CI canonique ne justifie une abstraction JUnit en F.

### Comparaison descriptive

`EvaluationReportComparator` compare exclusivement deux reports minimisés de
même suite. Il aligne par case ID, repetition index, assertion ref, criterion
ref et rubric ref. L'ordre baseline est préservé puis les ajouts candidate sont
appendus dans leur ordre.

Les change kinds fermés sont `UNCHANGED`, `ADDED`, `REMOVED`, `CHANGED`. Une
transition ne contient que `from_verdict` et `to_verdict`. Aucun champ
d'acceptation, de régression, d'amélioration ou de sélection n'existe.

```text
COMPARISON_RESULT != RELEASE_GATE
COMPARISON_NEVER_CHANGES_BASELINE_OR_CANDIDATE_VERDICT
```

### Delta rationnel exact

`RationalScoreDelta` est distinct de `NormalizedScore`. Il contient une
fraction normalisée signée dans `[-1,1]` et calcule exactement candidate moins
baseline. Si l'un des deux statuts n'est pas `SCORED`, le delta est absent ; il
n'existe aucun fallback à zéro, moyenne inter-répétitions ou threshold.

```text
SCORE_DELTA_IS_MEASUREMENT_NOT_ACCEPTANCE_THRESHOLD
```

Les rubrics sont comparées depuis leurs sorties D : status, score et critères
correspondants. Elles ne sont jamais recalculées.

### Artifacts et sink

`EvaluationArtifact` contient uniquement un nom logique validé, un format fermé
JSON/MARKDOWN et les bytes UTF-8 issus d'un renderer. Le media type dépend du
format. Le nom refuse séparateurs, `..`, drive prefixes et URL.

Le core ne fait aucune I/O. `EvaluationArtifactSinkPort` est injecté et F ne
fournit qu'un fake in-memory sous `tests/support`. La livraison appelle le sink
une fois. Une exception devient `ARTIFACT_SINK_ERROR`, sans message, retry,
SecurityEvent ou recovery, et ne change ni résultat ni report.

```text
ARTIFACT_WRITE_FAILURE_NEVER_CHANGES_EVALUATION_RESULT
NO_INTERNAL_ARTIFACT_RETRY_LOOP
```

### Confidentialité et déterminisme

Les modèles, renderers, comparaisons et artifacts ne possèdent aucun champ pour
une observation brute, exception, raisonnement privé ou payload. Des tests
adversariaux vérifient l'absence de fausses credentials, paths et injections.

Même source implique même report, mêmes JSON/Markdown et même comparaison. Il
n'existe aucun registre mutable global de report ou artifact.

## Frontières différées

- G : adapters/projections vers les owners runtime ;
- 12.15 : scénarios pédagogiques E2E ;
- 12.16 : providers, modèles, coûts et calibration.

F ne crée aucun fichier report généré, aucune intégration runtime et aucune
policy de release.

## Conséquences

Le harness dispose de projections sérialisables et comparables sans augmenter
l'autorité ou la surface sensible des résultats existants.

```text
RATIONALIZATION = REPORTING_PROJECTS_SAFE_EXISTING_EVALUATION_RESULTS
```
