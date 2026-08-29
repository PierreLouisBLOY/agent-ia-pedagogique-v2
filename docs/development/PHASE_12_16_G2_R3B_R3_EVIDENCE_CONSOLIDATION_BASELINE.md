# Phase 12.16-G2-R3B-R3 — Baseline de consolidation des preuves

## Décision

- Consolidation offline : `PASS / CLOSED`.
- Appels fournisseurs R3 : `0` ; coût fournisseur R3 : `0.000000 USD`.
- Le ledger R3B et son échec historique restent inchangés.

## Proof sets hashés

- `artifacts/calibration/12.16-g2-r2/ledger.json` : `45316f4e72f3d634cb31117e6f9cc690b68da43891b035558ed9a2aa46b33eb9`.
- `artifacts/calibration/12.16-g2-r2/summary.json` : `bf8aa0277c04dbceec63d2c8dff004bf9fb2849cfc069449b159d428025c67b7`.
- `artifacts/calibration/12.16-g2-r2b/ledger.json` : `c37e2587e6d408233c716d7ce4c27c3364baec50e0c1ab180b9f344f23a509c8`.
- `artifacts/calibration/12.16-g2-r2b/summary.json` : `accab7309c4a3c5a25e8bbb40c8b494218da498c2808f26b4774eb3f7299ea2e`.
- `artifacts/calibration/12.16-g2-r3/ledger.json` : `5722c7e4ba80a40d169997c34de9d764fe63781bc804b74ed2d3d19d1f46175f`.
- `artifacts/calibration/12.16-g2-r3/summary.json` : `44b71e0d6e0da0828235af15a26bb66a6e6d5ff923264c413cc454420c3b79b7`.
- `artifacts/calibration/12.16-g2-r3b-r2/ledger.json` : `aa254f931f417f5be267f1dd5e65dd1c667ab65bb0e2510b3cd586079ea16ae9`.
- `artifacts/calibration/12.16-g2-r3b-r2/raw/remediation.r3.anthropic-scorer.scn-01.c.clarity.canary.r1.3d2e4cb76ed3d5f10eabd369f19933404a5900df95674eaa2bc96c67b815ba3d.json` : `3d2e4cb76ed3d5f10eabd369f19933404a5900df95674eaa2bc96c67b815ba3d`.
- `artifacts/calibration/12.16-g2-r3b-r2/summary.json` : `e3aed0e2e49a10a64096fdc6765ae6222f2fff1c142c00d8081780726b8ad18d`.
- `artifacts/calibration/12.16-g2/ledger.json` : `909a973d6532570ce95a65018d6016ed8ecaeb6af45ff4216ec568a21fecf0d7`.

## Canary R3B-R2

- Statut : `HTTP 200 / STRUCTURED / SCORED` ; score : `0/1`.
- Usage input/cache/output/total : `938/0/391/1329` ; latence : `7302 ms`.
- Coût : `0.005786 USD` ; raw SHA-256 : `3d2e4cb76ed3d5f10eabd369f19933404a5900df95674eaa2bc96c67b815ba3d`.
- Mapping : `EXACT_REMEDIATION_EQUIVALENT` vers `cal.score.anchor.scn-01.c.clarity.r1`.
- Toutes les dimensions d'identité sont égales ; seul le call ID et le cycle d'autorisation diffèrent.

## Preuves R3B

- Succès réutilisables : `9/9` (`6` OpenAI Review, `3` Anthropic Scorer).
- Échec historique `r3.cal.score.anchor.scn-01.c.clarity.r1` : `FAILED`, préservé et non réutilisé.

## Manifeste consolidé hash-only

- Résultats logiques : `25` uniques.
- SHA-256 canonique : `b9eb583ccf5c6fcbc6b7b5d4491dd74a53889ffd92521b3270f9984f61d12aa9`.

| Slot logique | Proof set | Mapping | Provider | Output SHA-256 |
|---|---|---|---|---|
| `cal.generation.course.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `4c224e7b85af14a1f9a33cbd292c4567a45aef7fcbda02fde7d64ff6cf8d3fcb` |
| `cal.generation.course.primary.r2` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `53d4b056c16cc1212a4b9f7995f1d01bb2c8333793aaeca5ed77abdba8baf1a5` |
| `cal.generation.course.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `e264b018ede1f08f38540e5142f73f1f655fea664887c8c64217a1c5ce87d249` |
| `cal.generation.exercise.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `aded5d6dd52e3250670954803445ac4dddc9ae81843af62eaab85bcd2335f01b` |
| `cal.generation.assessment.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `6f1436688c314bc3e900c6d77747d7e5eb12f60c107cfc1a3d9772072876d059` |
| `cal.generation.assessment.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `e88365bc63f7f40774e3c44df19ad61e6ab0290035e9b19b3a64c305451f6955` |
| `cal.generation.qcm.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `a4567ef0f93d856799cc1df88924a2ecd95ce0273c6a1aefdb2f23831bba1036` |
| `cal.generation.qcm.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `6884150bf6a88db77fd0d2e0afdd623d6a30f2f2ba4be8efca09f77fef1a7306` |
| `cal.transformation.resource.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `965d11d36db35d200c1616930e0357d2089e18a3878d44e4f71a981714c94975` |
| `cal.transformation.resource.primary.r2` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `b7e67be59faf25133033eabdcccd6048dd2359bea7c9c5e6592ae41ef1887590` |
| `cal.correction.remediation.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `9966a3cc5773a25db17c370a749cb20e691907d42e1413f75f96e938c93c3122` |
| `cal.correction.remediation.primary.r2` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `02b5f41ec210c535dd5eef249ee9d2ff4b7c5cc03d9536eaeda4bf49f7beb07f` |
| `cal.correction.remediation.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `openai` | `04b29a9193b71cc596ed61586fbfef9f1c600d6a17126c2e62bdd68a66170bf1` |
| `cal.review.exercise.primary.r1` | `R2B` | `AUTHORIZED_PARAMETER_REMEDIATION` | `openai` | `8430b6ae90a17451a94f69557de3aef1bca45e3e78ca6dff743ac161a4aac65b` |
| `cal.review.exercise.primary.r2` | `R3B` | `EXACT_ORIGINAL_RESULT` | `openai` | `5b5fc80fad92fd39eca3e279729a4a7d7512856a9de7389f5e41e33b310e17e1` |
| `cal.review.exercise.fallback.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `openai` | `bfecd1259be3de50cd6aa89dc5921eb7c4c98096a736330fa3c5cd2a221261ad` |
| `cal.review.assessment.primary.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `openai` | `06958c577191ffde838c5e7b9e6aa47859ccf74e88fcaee3c7ca82b7dac1d703` |
| `cal.review.correction.primary.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `openai` | `4ee34727d9c5feb7c4570ed84e7949d7fe5f71fb40fdf7b221db454b92fc9771` |
| `cal.review.qcm.primary.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `openai` | `e54af12c650691ea53e5327dfb7c465fe54ffddd120bb6169f7a095db6fc26c3` |
| `cal.review.qcm.fallback.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `openai` | `384cfcd39c69fcfdc385bdc5794310a9769d96a5fc1db393011bdcdfee8637a3` |
| `cal.score.anchor.scn-01.a.clarity.r1` | `R2` | `EXACT_REMEDIATION_EQUIVALENT` | `anthropic` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` |
| `cal.score.anchor.scn-01.a.organization-utility.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `anthropic` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` |
| `cal.score.anchor.scn-01.b.clarity.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `anthropic` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` |
| `cal.score.anchor.scn-01.b.organization-utility.r1` | `R3B` | `EXACT_ORIGINAL_RESULT` | `anthropic` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` |
| `cal.score.anchor.scn-01.c.clarity.r1` | `R3B-R2` | `EXACT_REMEDIATION_EQUIVALENT` | `anthropic` | `3d2e4cb76ed3d5f10eabd369f19933404a5900df95674eaa2bc96c67b815ba3d` |

## Comptabilité des slots

- Originaux : `96` ; réutilisés : `25` ; restants : `71`.
- Intersection réutilisés/restants : `0` ; union : `96`.
- Aucun slot inconnu, perdu ou dupliqué.
