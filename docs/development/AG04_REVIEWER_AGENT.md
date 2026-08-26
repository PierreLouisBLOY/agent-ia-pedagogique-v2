# AG-04 — ReviewerAgent CAP-V01

## Portée du lot 12.9-D

`ReviewerAgent` relie C-09 `ReviewRequest` à C-10 `ReviewResult` pour la seule
capability `CAP-V01 semantic_review`. Il réutilise la préparation et l'appel
unique du `ReviewCoordinator`, puis matérialise explicitement les contrats
canoniques existants.

```text
C-09 + cible/inputs résolus
→ ReviewerAgent.semantic_review()
→ ReviewCoordinator
→ ReviewPort.review() [1 appel]
→ ReviewPortResult technique
→ ReviewResultMaterializationRequest
→ ReviewerAgent.build_review_result()
→ Finding* + ReviewResult C-10
```

L'API publique contient uniquement `semantic_review()` et
`build_review_result()`. CAP-V02 est refusée par l'agent D et aucune méthode
`assess_findings()` n'existe à ce stade.

## Appel semantic review

`semantic_review()` reçoit un `ReviewPreparationRequest` déjà autorisé et exige
exactement `CAP-V01`. Le coordinator :

- lie C-09, la cible exacte et les inputs caller-supplied ;
- revalide le Prepared ;
- appelle le port exactement une fois ;
- borne step, opération et evidence utilisées.

Le tuple retourné contient le `PreparedReviewCall` exact et le même
`ReviewPortResult` technique. Les erreurs de port sont propagées sans retry ni
traduction.

## Demande de matérialisation

`ReviewResultMaterializationRequest` est frozen et slotted. Elle conserve :

- le Prepared exact ;
- le résultat technique exact ;
- un `ContractMeta[ReviewStatus]` caller-supplied ;
- un `review_id` caller-supplied.

La metadata doit correspondre au schema, run, step et correlation C-09, porter
l'acteur AG-04 et utiliser le statut déterminé par le mapping technique :

| `ReviewPortResultStatus` | `ReviewStatus` |
| --- | --- |
| `SUCCEEDED` | `COMPLETED` |
| `PARTIAL` | `INCOMPLETE` |
| `REFUSED` / `FAILED` | aucune matérialisation |

Le provider ou `execution_metadata` ne peuvent fournir ni `review_id`, ni
metadata C-10, ni statut canonique.

## Schéma fermé des findings

Chaque mapping de `technical_findings` doit contenir exactement les dix champs
suivants :

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

Les valeurs `dimension` et `severity` sont les `.value` exactes de
`ReviewDimension` et `FindingSeverity`. Les mappings sont agent-safe et gelés.
Les IDs sont non vides et uniques. Une evidence de finding doit appartenir à
C-09 et avoir été déclarée dans `technical_result.evidence_refs_used`.

La validation du locator contre la géométrie réelle du contenu est différée à
12.9-F ; D vérifie uniquement sa forme agent-safe.

## Payload et C-10

Le `structured_payload` accepte exactement :

```text
overall_assessment
correction_required
coverage
confidence
```

L'assessment est une valeur exacte de `OverallAssessment`. Il est déclaré par la
sortie CAP-V01 et non calculé par une policy D. La coverage doit être unique,
bornée aux dimensions demandées et couvrir les dimensions des findings.
Warnings et limitations utilisent les champs techniques dédiés.

`build_review_result()` applique seulement les invariants structurels déjà
définis par C-10. Il n'ajoute aucune règle fondée sur la sévérité, aucun score,
seuil, consensus ou algorithme d'agrégation CAP-V02.

## Hors scope

Le lot ne crée aucun C-11 `CorrectionRequest`, provider, dispatcher, workflow,
appel réseau, persistence, validation ou promotion. Il ne modifie ni contrats,
registry ni access matrix. CAP-V02 et l'agrégation appartiennent à 12.9-E ; le
hardening locator/evidence appartient à 12.9-F.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
