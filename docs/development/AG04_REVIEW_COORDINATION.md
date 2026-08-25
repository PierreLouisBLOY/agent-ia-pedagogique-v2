# AG-04 — Préparation et coordination de review

## Objet du lot 12.9-C

La couche C relie C-09 `ReviewRequest` à la frontière provider-neutral B. Elle
prépare un appel déterministe, exécute exactement un `ReviewPort.review()` et
revalide sa lineage. Elle retourne le même `ReviewPortResult` technique, sans
créer C-10 `ReviewResult` ou `Finding`.

```text
ReviewRequest + cible résolue + inputs caller-supplied
→ ReviewPreparationRequest
→ ReviewCoordinator.prepare()
→ PreparedReviewCall
→ ReviewCoordinator.execute()
→ ReviewPort.review() (1 appel)
→ ReviewPortResult technique revalidé
```

## Mapping capability vers opération

| Capability | Opération technique | Traitement des inputs |
| --- | --- | --- |
| `CAP-V01` | `SEMANTIC_REVIEW` | transmis sans interprétation additionnelle |
| `CAP-V02` | `ASSESS_FINDINGS` | findings résolus conservés dans `resolved_inputs` |

Le mapping est local et fermé. Il ne consulte ni registry ni access matrix, ne
route pas d'agent et n'accorde aucune autorité. Une autre capability est refusée
avec `UNSUPPORTED_CAPABILITY`.

## Snapshot et binding exacts

`ReviewPreparationRequest` contient l'objet C-09 exact, une
`ResolvedReviewTarget` portant le même `ObjectVersionRef`, ainsi que les inputs
et le contrat de sortie déjà résolus par le caller. Aucun chargement de cible ou
fetch d'evidence n'est réalisé.

`prepare()` lie exactement :

- `ReviewRequest.meta.step_id` à `source_step_id` ;
- la capability à l'opération fermée ;
- `target_production_ref`, dimensions, critères, evidence et budget aux champs
  canoniques correspondants ;
- le contenu/payload à la cible caller-supplied ;
- `severity_policy`, `context_slice` et `independence_requirements` à trois clés
  explicites de `coverage_context` ;
- `resolved_inputs` et `output_contract` aux mappings caller-supplied.

Ces mappings sont profondément immutables. Ils ne fusionnent pas les trois
contextes C-09 et ne donnent aucune autorité aux données reçues.

## Anti-forgery et appel unique

`PreparedReviewCall` conserve la préparation originale, la capability, C-09, la
cible et la requête technique. Sa construction puis chaque `execute()`
revalident tous ces liens. Une falsification de capability, requête, cible,
contenu/payload, dimensions, critères, evidence, contexte, budget, inputs,
contrat, step ou opération échoue avant l'appel outbound.

Après l'unique appel, le coordinator vérifie :

- le type exact `ReviewPortResult` ;
- le même step source et la même opération ;
- l'unicité de `evidence_refs_used` ;
- `set(evidence_refs_used) ⊆ set(ReviewRequest.evidence_refs)`.

Une erreur `ReviewPortError` est propagée telle quelle. Aucun retry, fallback,
repair, boucle ou traduction provider n'est effectué.

## Nature du résultat

Le résultat reste strictement technique et non canonique. La cohérence de sa
lineage ne signifie ni review métier achevée, ni validation, ni approbation, ni
promotion. Le coordinator ne crée aucun `Finding`, `ReviewResult` ou
`CorrectionRequest` et ne décide pas si une correction est requise.

## Hors scope maintenu

Ce lot ne crée ni `ReviewerAgent`, provider, dispatcher runtime, workflow,
persistance ou accès direct aux données. Il ne modifie ni registry ni access
matrix. La matérialisation C-10 appartient à 12.9-D, l'assessment canonique de
findings à 12.9-E et le hardening complet à 12.9-F.

La coordination de génération est structurellement proche mais sémantiquement
distincte ; aucune factorisation commune sûre n'est établie.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
