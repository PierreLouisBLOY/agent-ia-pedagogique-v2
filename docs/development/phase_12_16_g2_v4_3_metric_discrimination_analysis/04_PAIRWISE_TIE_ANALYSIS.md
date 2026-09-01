# Phase 12.16-G2-V4.3 — Analyse des six pairwise ties

## Nature exacte du « pairwise »

Le protocole n'effectue pas un jugement comparatif direct. Chaque output primary ou fallback est scoré indépendamment. `summarize_pairwise_quality` groupe ensuite par scénario et critère, compare les deux `Fraction` exactes et déclare un tie uniquement si elles sont égales.

Les six ties proviennent tous de `1/1 == 1/1`. Le payload brut de chacun des douze scores est identique et a le SHA-256 `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b`. Aucune rationale n'est disponible.

## Table des six comparaisons

| Scénario | Critère | Primary / source / modèle | Fallback / source / modèle | Scores | Différences substantielles observées | Justification du tie |
|---|---|---|---|---|---|---|
| SCN-03 | `scn-03.quality.clarity` | `cal.generation.course.primary.r1` / gpt-5.6-terra | `cal.generation.course.fallback.r1` / gpt-5.6-sol | 1 = 1 | Primary étiquette explicitement économique/social dans l'exemple ; fallback laisse ce lien plus implicite. Structure et contenu restent quasi équivalents. | Tie arithmétique exact ; rationale scorer non enregistrée. L'équivalence sémantique rend le tie plausible. |
| SCN-03 | `scn-03.quality.level-adaptation` | `cal.generation.course.primary.r1` / gpt-5.6-terra | `cal.generation.course.fallback.r1` / gpt-5.6-sol | 1 = 1 | Même vocabulaire, même coopérative, même distinction et même niveau de détail ; différences rédactionnelles mineures. | Tie arithmétique exact ; rationale scorer non enregistrée. Aucune différence de niveau nette dans les données. |
| SCN-06 | `scn-06.quality.assessment-clarity` | `cal.generation.assessment.primary.r1` / gpt-5.6-terra | `cal.generation.assessment.fallback.r1` / gpt-5.6-sol | 1 = 1 | Primary emploie l'euro et précise l'arrondi ; fallback conserve « unités monétaires » et signale que la devise n'est pas fournie. Les deux exigent formule, application, calcul et unité. | Tie arithmétique exact ; rationale scorer non enregistrée. Les deux satisfont fortement la contrainte de clarté. |
| SCN-06 | `scn-06.quality.marking-scheme-coherence` | `cal.generation.assessment.primary.r1` / gpt-5.6-terra | `cal.generation.assessment.fallback.r1` / gpt-5.6-sol | 1 = 1 | Les deux barèmes ont exactement deux questions de trois points, réparties en trois éléments d'un point, avec formules et résultats. | Tie arithmétique exact ; rationale scorer non enregistrée. Le barème est substantiellement équivalent. |
| SCN-07 | `scn-07.quality.correction-quality` | `cal.correction.remediation.primary.r1` / gpt-5.6-sol | `cal.correction.remediation.fallback.r1` / gpt-5.6-terra | 1 = 1 | Primary diagnostique explicitement « l'oubli des charges » ; fallback formule directement la règle produits moins charges. Tous deux corrigent la confusion chiffre d'affaires/résultat. | Tie arithmétique exact ; rationale scorer non enregistrée. Les forces rédactionnelles diffèrent sans écart qualitatif majeur. |
| SCN-07 | `scn-07.quality.remediation-clarity` | `cal.correction.remediation.primary.r1` / gpt-5.6-sol | `cal.correction.remediation.fallback.r1` / gpt-5.6-terra | 1 = 1 | Les deux proposent la même activité : classer trois montants, calculer le résultat, puis expliquer sa différence avec le chiffre d'affaires. | Tie arithmétique exact ; rationale scorer non enregistrée. Les remédiations sont pratiquement équivalentes. |

## Vérification des identités et sources

- SCN-03 : primary `gpt-5.6-terra` depuis `cal.generation.course.primary.r1`; fallback `gpt-5.6-sol` depuis `cal.generation.course.fallback.r1`.
- SCN-06 : primary `gpt-5.6-terra` depuis `cal.generation.assessment.primary.r1`; fallback `gpt-5.6-sol` depuis `cal.generation.assessment.fallback.r1`.
- SCN-07 : primary `gpt-5.6-sol` depuis `cal.correction.remediation.primary.r1`; fallback `gpt-5.6-terra` depuis `cal.correction.remediation.fallback.r1`.
- Les douze score calls référencent le bon `source_call_id`, le bon `producer_role` et le bon `producer_model` dans le safe report.
- Aucun résultat carry-forward n'est confondu avec les nouveaux selected outputs.

## Normalisation et agrégation

- Le parser construit un `NormalizedScore` exact dans `[0,1]` et le réduit par PGCD.
- Le safe report reconvertit en `Fraction`; aucun flottant ni arrondi n'intervient.
- Le regroupement utilise `(scenario_code, criterion_ref)` puis les rôles exacts `PRIMARY` et `FALLBACK`.
- La métrique exige la présence des deux rôles ; sinon la comparaison n'est pas créée.
- La moyenne par modèle présentée ailleurs n'intervient pas dans la décision de tie.

## Le tie handling est-il trop permissif ?

Non au niveau arithmétique : seul `primary_score == fallback_score` produit un tie, sans epsilon. Oui au niveau du protocole : l'égalité de deux scores absolus indépendants et saturés est assimilée à une égalité qualitative, sans comparaison directe, définition de « différence substantielle », evidence locator ni adjudication.

Les six ties ne démontrent donc pas à eux seuls un bug. Pour SCN-03, SCN-06 et SCN-07, les outputs sont réellement très proches. Ils démontrent toutefois que la métrique dite pairwise ne peut pas départager des nuances que son Scorer absolu et son contrat binaire implicite ont déjà perdues.
