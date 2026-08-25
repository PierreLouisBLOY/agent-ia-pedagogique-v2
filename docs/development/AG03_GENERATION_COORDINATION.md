# AG-03 — Préparation et coordination de génération

## Objet du lot 12.8-C

La couche C relie C-07 `ProductionRequest` à la boundary provider-neutral B sans
implémenter l’agent complet. Elle prépare un appel technique déterministe,
exécute au plus un appel `GenerationPort.generate()` et valide sa lineage avant
de restituer le même `GenerationPortResult`.

```text
ProductionRequest + capability + caller-supplied inputs
→ GenerationPreparationRequest
→ GenerationCoordinator.prepare()
→ PreparedGenerationCall
→ GenerationCoordinator.execute()
→ GenerationPort.generate() (0 ou 1 appel)
→ GenerationPortResult techniquement cohérent
```

## Mapping capability vers operation

| Capability | Operation technique | Règle C-07 |
| --- | --- | --- |
| `CAP-G01` | `GENERATE` | `target_ref` interdite |
| `CAP-G02` | `TRANSFORM` | `target_ref` obligatoire |
| `CAP-G03` | `CORRECT` | refus `CORRECTION_REQUEST_REQUIRED` |

Ce mapping est local et fermé. Il ne route aucun agent, ne consulte pas la
registry, n’évalue pas une permission et ne modifie pas l’access matrix. CAP-G03
sera relié à C-11 `CorrectionRequest` en 12.8-E.

## Préparation et anti-forgery

`prepare()` copie exactement depuis C-07 :

- `meta.step_id` vers `source_step_id` ;
- `production_kind`, `brief` vers `objective` et `output_format` ;
- `constraints`, `evidence_refs`, `target_ref` et `expected_sections`.

`resolved_inputs` et `output_contract` sont les seules données injectées depuis
`GenerationPreparationRequest`. Elles doivent déjà avoir été résolues et
autorisées par l’amont ; le coordinator ne lit aucune source.

`PreparedGenerationCall` est immutable, mais `execute()` revalide tous ses
champs avant l’appel outbound. Un objet forgé, une capability étrangère, une
operation divergente, un step différent ou une copie altérée échoue de manière
fail-closed et le port n’est pas appelé.

## Lineage de cible et d’evidence

CAP-G02 conserve exactement la même `target_ref` entre C-07 et la requête
technique. Le coordinator ne charge jamais cette cible.

Le résultat peut utiliser zéro, une ou plusieurs références déjà présentes dans
la requête canonique, selon la règle :

```text
set(evidence_refs_used) ⊆ set(ProductionRequest.evidence_refs)
```

Une référence étrangère ou dupliquée est refusée. Aucun fetch, `EvidenceSet`,
score d’autorité ou recherche autonome n’est effectué.

## Appel unique et erreurs

`execute()` appelle `GenerationPort.generate()` exactement une fois après la
revalidation. Il n’effectue aucun retry, fallback, repair ou replan.

- `GenerationCoordinationError` représente une incohérence déterministe de
  capability, target ou lineage ;
- `GenerationPortError` reste une erreur technique de boundary et est propagée
  sans traduction.

Les statuts `PARTIAL`, `REFUSED` et `INSUFFICIENT_EVIDENCE` restent inchangés et
ne sont jamais promus artificiellement en `SUCCEEDED`.

La formule « validated technical result » signifie uniquement que la cohérence
technique et la lineage ont été contrôlées. Elle ne signifie jamais
`ValidationResult` métier, review, approbation, canonicalisation ou promotion.

## Hors scope maintenu

Cette couche ne construit aucun `ProductionCandidate` ou `CorrectionResult`, ne
persiste rien, n’appelle aucun use case Application et n’importe ni runtime ni
orchestration. Elle ne choisit aucun provider, modèle, prompt ou endpoint et
n’effectue aucun HTTP, SQL ou accès filesystem.

Restent différés : l’assemblage AG-03 en 12.8-D, CAP-G03 en 12.8-E, le hardening
en 12.8-F, les workflows en 12.8-G et la clôture en 12.8-H.
