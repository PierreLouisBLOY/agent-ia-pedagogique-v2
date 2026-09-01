# Phase 12.16-G2-V5 — Diff canonique V4.2 vers V5

## Audit exhaustif

`build_v42_to_v5_diff()` émet exactement 102 décisions, une par `call_id` de `V42_LOGICAL_CALL_MATRIX`. Chaque décision enregistre séparément : provider, model, model profile, role, workload, scenario, task kind, repetition, prompt/input, dépendances, criterion refs, contrat scorer/parser, budget tokens, input refs, pricing et hash canonique final.

Résultat :

| Partition exhaustive | Records | `CALL_SPEC_UNCHANGED` | Raison |
|---|---:|---|---|
| OpenAI génération/transformation/correction/review | 20 | `TRUE` | `UNCHANGED` |
| Anthropic scoring absolu | 82 | `FALSE` | `SCORER_CONTRACT_AND_PROMPT_CHANGED` |

Pour les 82 records Anthropic, provider, model, profile, rôle, workload, scénario, task kind, répétition, dépendance source, criterion refs, budget tokens, input refs et pricing restent identiques. Le prompt/input structuré et le contrat scorer/parser changent ; le hash canonique change donc nécessairement.

## Les 20 records strictement inchangés

1. `cal.generation.course.primary.r1`
2. `cal.generation.course.primary.r2`
3. `cal.generation.course.fallback.r1`
4. `cal.generation.exercise.primary.r1`
5. `cal.generation.assessment.primary.r1`
6. `cal.generation.assessment.fallback.r1`
7. `cal.generation.qcm.primary.r1`
8. `cal.generation.qcm.fallback.r1`
9. `cal.transformation.resource.primary.r1`
10. `cal.transformation.resource.primary.r2`
11. `cal.correction.remediation.primary.r1`
12. `cal.correction.remediation.primary.r2`
13. `cal.correction.remediation.fallback.r1`
14. `cal.review.exercise.primary.r1`
15. `cal.review.exercise.primary.r2`
16. `cal.review.exercise.fallback.r1`
17. `cal.review.assessment.primary.r1`
18. `cal.review.correction.primary.r1`
19. `cal.review.qcm.primary.r1`
20. `cal.review.qcm.fallback.r1`

Leur `v5_call_spec_sha256` est exactement le `call_spec_sha256` V4.2, et pas une approximation reconstruite.

## Les 82 records modifiés

La seconde partition est définie exhaustivement comme l'ensemble des records V4.2 dont `provider = anthropic`, soit :

- 48 scores initiaux d'anchors ;
- 16 répétitions strong ;
- 18 scores d'outputs sélectionnés.

Chaque ligne est disponible sous forme typée dans l'audit exécutable et possède ses deux hashes, son statut source `COMPLETED`, ses booléens de propriété et la raison fermée `SCORER_CONTRACT_AND_PROMPT_CHANGED`.

## Nouveaux records

Onze records `V5_DIRECT_PAIRWISE` n'ont aucun antécédent V4.2 et ne sont jamais présentés comme carry-forward : cinq comparaisons d'anchors et six comparaisons d'outputs. Leur raison conceptuelle est `NEW_V5_PAIRWISE_CALL`.

`MATRIX_SHA256 = 3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c`.

