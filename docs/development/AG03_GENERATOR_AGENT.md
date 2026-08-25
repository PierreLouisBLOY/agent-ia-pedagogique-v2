# Agent generateur AG-03

La Phase 12.8-D ouvre uniquement CAP-G01 `generate_production` et CAP-G02
`transform_production` sur le contrat `ProductionRequest` C-07.

```text
CAP-G01/G02
→ GenerationCoordinator.prepare()
→ GenerationCoordinator.execute()
→ GenerationPortResult revalide
→ materialisation explicite caller-supplied
→ ProductionCandidate C-08 dans l'etat CANDIDATE
```

`GeneratorAgent` recoit un `GenerationCoordinator` injecte. Les methodes de
generation et de transformation retournent le `PreparedGenerationCall` et le
resultat technique exacts afin que le caller puisse ensuite fournir un
`result_meta` coherent et une `production_id` nouvelle. `build_candidate()`
revalide cette chaine avant de construire C-08.

```text
GenerationPortResult.execution_metadata (non fiable)
→ controle authority-free deterministe et recursif
→ ProductionCandidate.generation_metadata
```

Le controle refuse toute cle reservee a une validation, approbation, promotion,
review, confiance, qualite canonique, decision de gate ou permission, y compris
dans les mappings imbriques et sans tenir compte de la casse. Il echoue sans
filtrer silencieusement les metadata. Ce garde-fou ne signifie jamais que les
metadata restantes sont `SAFE` ou `TRUSTED` ; le hardening complet du contenu
reste differe a 12.8-F.

## Statuts

| Statut technique | Effet |
| --- | --- |
| `SUCCEEDED` | candidat avec `AgentResultStatus.SUCCEEDED` |
| `PARTIAL` | candidat `PARTIAL`, warnings et incertitudes conserves |
| `REFUSED` | aucun candidat |
| `INSUFFICIENT_EVIDENCE` | aucun candidat |

CAP-G02 conserve le `target_ref` exact dans la lineage du nouveau candidat sans
charger ni modifier la cible. CAP-G01 ne synthetise aucune cible ou relation
parent. Dans les deux cas, les references de preuve utilisees restent bornees
par celles de C-07 et les metadata techniques ne conferent aucune autorite.

Cette couche n'effectue aucune recherche, review, validation, promotion ou
persistance. Elle ne contient aucun provider, retry, fallback ou dispatcher
runtime. CAP-G03 reste en attente de 12.8-E ; le grounding et le hardening
complets restent en attente de 12.8-F.
