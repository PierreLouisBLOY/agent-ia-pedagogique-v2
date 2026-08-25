# Correction versionnee AG-03

La Phase 12.8-E relie CAP-G03 `correct_production` au mandat C-11 sans charger ni
modifier la production cible.

```text
CorrectionRequest C-11
+ ResolvedCorrectionTarget caller-supplied (version exacte)
→ GenerationCoordinator.prepare_correction()
→ GenerationPortRequest CORRECT
→ GenerationCoordinator.execute_correction()
→ GenerationPortResult + operation_details declares
→ materialisation caller-supplied
→ nouvelle ProductionCandidate CANDIDATE + CorrectionResult
```

La requete technique utilise `target_version_ref: ObjectVersionRef` et garde
`target_ref` a `None`. Le contenu et le payload de la cible sont deja resolus et
places dans un bloc d'inputs ferme ; AG-03 n'accede a aucun repository.

Le bloc `operation_details` contient exactement `addressed_findings`,
`unresolved_findings` et `change_summary`. Les deux listes sont uniques,
disjointes et couvrent exactement les findings C-11. Elles restent declaratives
et devront etre revues en aval ; AG-03 ne leur accorde aucune autorite.

| Statut technique | Materialisation |
| --- | --- |
| `SUCCEEDED` | candidate + `CorrectionResult` SUCCEEDED |
| `PARTIAL` | candidate + `CorrectionResult` PARTIAL avec limites |
| `REFUSED` | aucune sortie de correction |
| `INSUFFICIENT_EVIDENCE` | aucune sortie de correction |

Le caller fournit `result_meta`, `production_id` et `new_production_ref`.
`CorrectionResult` impose meme identite d'objet et nouvelle version. Il n'existe
ni mutation de la cible, ni boucle locale, retry, validation, promotion,
persistance, provider concret ou dispatcher runtime. Le hardening complet et les
workflows restent respectivement differes a 12.8-F et 12.8-G.
