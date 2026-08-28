# Phase 12.14-F — Baseline reporting et comparaison

## 1. Parent E

F prolonge les contrats et le runner fermés jusqu'à E sans les modifier.
Parent Git exact : `c9daa394d10371648246202ce6a34c9bf357c033`.

Décision :
[ADR-P12-053](../../architecture/adr/ADR-P12-053-agentic-evaluation-reporting-comparison-artifacts.md).

## 2. Modèle minimisé

La hiérarchie report suite/case/répétition/assertion/score/rubric est immutable,
ordonnée et bornée. Elle réutilise les IDs, enums, reason codes et
`NormalizedScore` existants. Elle n'est ni un résultat fonctionnel parallèle ni
une autorité.

Les titles, observation refs/values, outputs, exceptions, prompts, payloads,
paths et metadata sont exclus avant rendering.

## 3. Schema

`EvaluationReportSchemaVersion(1, 0)` versionne le format artifact séparément
du schema d'évaluation. Aucun run ID, UUID, timestamp ou host implicite.

## 4. Projection

Le projector exige la cohérence exacte de suite ID, version, case IDs et ordre.
Il copie uniquement l'allowlist de l'ADR, ne mute pas les sources et ne relance
aucun owner B-E.

Les résultats plats antérieurs à E restent au niveau case ; aucun verdict de
répétition n'est inventé. Les résultats E restent attribués par index.

## 5. JSON

JSON est UTF-8, compact, clés triées et `allow_nan=False`. La conversion est
explicite champ par champ, sans `asdict` générique ou `default=str`.

```json
{"denominator":3,"numerator":1}
```

Aucun float ou rounding.

## 6. Markdown

Markdown projette la même surface sûre : suite, counts, cases, répétitions,
assertions, scores, rubrics et codes fermés. Les IDs/codes sont échappés ; aucun
HTML, title, lien ou chemin privé.

## 7. Limites

La taille maximale canonique est 2 000 000 octets pour JSON, Markdown et
artifact. Une limite de canal plus stricte est injectable. Un dépassement est
refusé explicitement et jamais tronqué.

## 8. Comparaison

Les reports minimisés sont alignés par suite ID, case ID, repetition index,
assertion ref, criterion ref et rubric ref. Les changements fermés sont
`UNCHANGED`, `ADDED`, `REMOVED`, `CHANGED`.

Une transition garde seulement les verdicts source. La comparaison ne produit
ni PASS, ni acceptation, ni recommandation de release.

## 9. Delta exact

`RationalScoreDelta` est une fraction signée normalisée dans `[-1,1]`. Il vaut
candidate moins baseline. Il est absent si l'un des statuts n'est pas `SCORED`.
Il n'existe aucune moyenne, renormalisation, statistique ou threshold.

## 10. Répétitions et rubrics

Les répétitions sont comparées 1-to-1 par index ; une différence de cardinalité
devient ADDED/REMOVED. Les rubrics sont comparées sur leur sortie D existante,
leurs criteria refs et leur score exact, sans recalcul.

## 11. Artifacts et sink

Formats fermés : JSON et MARKDOWN, avec media types déterministes. Le nom
logique est path-safe et refuse `/`, `\`, `..`, drive prefix et URL.

Le core ne possède aucun filesystem sink. La frontière injectée reçoit un
artifact déjà rendu. Une panne est contenue comme `ARTIFACT_SINK_ERROR`, un seul
appel, sans retry et sans mutation du report/résultat.

## 12. Confidentialité

Les tests injectent des valeurs synthétiques ressemblant à credentials, paths
et HTML. Elles sont absentes du report, JSON, Markdown, comparaison et artifact.
Les messages d'exception de sink sont également absents du résultat de livraison.

## 13. Déterminisme

Même résultat produit le même report ; même report produit les mêmes bytes JSON
et Markdown ; mêmes reports produisent la même comparaison. L'ordre source est
stable et aucun environnement local n'est consulté.

## 14. JUnit

```text
JUNIT_BRIDGE_DEFERRED_UNTIL_CI_USE_CASE
```

F ne crée pas d'abstraction spéculative sans workflow CI canonique.

## 15. Architecture

`evaluation_harness/reporting` n'importe ni runtime, infrastructure, pytest,
tests, filesystem, réseau, provider ou quality_evaluation. Les règles fitness
interdisent I/O, float, champs bruts, dynamic loading et policy d'acceptation.

## 16. Frontières futures

| Scope | Owner futur |
| --- | --- |
| adapters/projections runtime | G |
| scénarios pédagogiques STMG/BTS | 12.15 |
| providers, modèles et calibration | 12.16 |

F ne commence aucun de ces scopes et ne produit aucun report généré suivi Git.

```text
RATIONALIZATION = REPORTING_PROJECTS_SAFE_EXISTING_EVALUATION_RESULTS
```
