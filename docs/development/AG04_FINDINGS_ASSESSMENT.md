# AG-04 — Assessment CAP-V02 et handoff AG-01

## Portée du lot 12.9-E

CAP-V02 évalue les findings déjà matérialisés dans C-10. Il produit uniquement
un `ReviewAssessmentSignal` interne non canonique et, si une correction est
requise, un `CorrectionHandoffSignal` destiné à AG-01.

```text
C-10 ReviewResult
→ ReviewerAgent.assess_findings()
→ ReviewCoordinator.prepare()/execute()
→ ReviewPort ASSESS_FINDINGS [1 appel]
→ revalidation des agrégats
→ ReviewAssessmentSignal
→ CorrectionHandoffSignal | None
```

AG-04 ne crée pas C-11 et n'appelle jamais AG-03 ou CAP-G03. AG-01 décidera
ultérieurement, selon le workflow et les policies autorisées, s'il faut créer un
`CorrectionRequest`, replanifier, stopper ou demander une gate.

## `FindingsAssessmentRequest`

La demande frozen/slotted contient CAP-V02, C-09, C-10, la cible exacte déjà
résolue, un `review_ref` caller-supplied, des inputs additionnels et le contrat
de sortie fermé.

Les contrôles avant appel imposent :

- cible C-09 = cible C-10 = cible résolue ;
- metadata C-10 liée au schema, run, step et correlation C-09, acteur AG-04 ;
- C-10 `COMPLETED` ou `INCOMPLETE` ;
- IDs de findings uniques ;
- coverage, dimensions et evidence bornées à C-09 ;
- evidence de findings incluses dans les evidence utilisées par C-10 ;
- tout blocking reflété par `source_result.correction_required=True` ;
- `review_ref` valide et jamais dérivé du provider.

## Snapshot des findings

Le `resolved_inputs` envoyé au port sépare `source_review` et
`additional_inputs`. `source_review.findings` contient exactement :

```text
finding_id
dimension
severity
description
target_locator
rationale
correction_required
evidence_refs
confidence
suggested_action
```

Les enums sont sérialisés par leur `.value` canonique. Le snapshot et le contrat
de sortie sont profondément immutables et recomparés au Prepared avant
l'exécution. Les inputs additionnels et tous les mappings techniques sont
revalidés contre le vocabulaire d'autorité, y compris face à un objet provider
forgé qui contournerait son constructeur normal.

## Résultat technique attendu

Pour CAP-V02, `technical_findings` doit être `()`. Le payload accepte exactement
les six champs suivants :

```text
assessed_finding_ids
blocking_finding_ids
correction_finding_ids
overall_assessment
correction_required
confidence
```

Les agrégats attendus sont recalculés dans l'ordre C-10 :

```text
assessed = tous les findings
blocking = severity BLOCKING
correction = flag correction_required UNION blocking
```

Toute omission, addition ou requalification est refusée. `REFUSED` et `FAILED`
ne produisent aucun signal. `PARTIAL` exige l'assessment `INCOMPLETE`, préserve
les limitations et ne masque aucun blocking.

## Sémantique du signal

`promotion_blocked_by_review` vaut exactement
`bool(blocking_finding_ids)`. Il s'agit d'un signal sémantique transmis à
AG-01/Application, jamais d'une décision de `PromotionPolicy` ou d'une mutation
transactionnelle.

L'assessment reste une valeur de `OverallAssessment`, pas un statut métier :

- `ACCEPTABLE` interdit correction et blocking ;
- un blocking interdit aussi `ACCEPTABLE_WITH_RESERVATIONS` ;
- `CORRECTION_REQUIRED` exige au moins un finding de correction ;
- `INCOMPLETE` reste une incomplétude, jamais un PASS ;
- `UNUSABLE` ne canonise aucun rejet métier.

Aucun score pondéré, vote ou consensus n'est calculé.

## Handoff de correction

Le handoff est absent lorsque la liste de correction est vide. Sinon, il cible
AG-01 avec exactement les findings requis, les blocking, l'union ordonnée de
leurs evidence et les actions suggérées publiques. Ces actions restent des
recommandations et ne sont jamais converties automatiquement en champs C-11.

Le modèle ne contient ni CAP-G03, provider, handler, tool, permission, gate,
promotion, validation ou mutation de cible.

## Hors scope

La sécurité complète de la cible, la validation des locators et le hardening
global evidence/lineage appartiennent à 12.9-F. Les workflows et la décision
AG-01 appartiennent à G. Aucun runtime, orchestration, registry, access matrix,
contrat canonique ou dépendance runtime n'est modifié dans E.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
