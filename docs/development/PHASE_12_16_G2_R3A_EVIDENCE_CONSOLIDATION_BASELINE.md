# Phase 12.16-G2-R3A � Consolidation des preuves

## Baseline et port�e

- Branche : `phase12/12-16-provider-model-calibration`
- HEAD/upstream d'entr�e : `fe6530528b00dfcb2b2d34797a97fe94ac349815`
- Parent : `4d3b93be82bbda1e1600ba5a17c0c7906fcb4d50`
- Main/origin-main : `7ae02ee109bcc6399ec0f71616da6aef07abda81`
- Appels provider R3A : `0`
- Co�t provider R3A : `0 USD`
- Ex�cution live R3 : `NOT_STARTED`

## Proof sets hash-only

| Chemin relatif | SHA-256 |
|---|---|
| `artifacts/calibration/12.16-g2-r2/ledger.json` | `45316f4e72f3d634cb31117e6f9cc690b68da43891b035558ed9a2aa46b33eb9` |
| `artifacts/calibration/12.16-g2-r2/summary.json` | `bf8aa0277c04dbceec63d2c8dff004bf9fb2849cfc069449b159d428025c67b7` |
| `artifacts/calibration/12.16-g2-r2b/ledger.json` | `c37e2587e6d408233c716d7ce4c27c3364baec50e0c1ab180b9f344f23a509c8` |
| `artifacts/calibration/12.16-g2-r2b/summary.json` | `accab7309c4a3c5a25e8bbb40c8b494218da498c2808f26b4774eb3f7299ea2e` |
| `artifacts/calibration/12.16-g2/ledger.json` | `909a973d6532570ce95a65018d6016ed8ecaeb6af45ff4216ec568a21fecf0d7` |

## Manifeste des 15 r�utilisations

SHA-256 canonique : `cace6d138a8ac1fef2920fc45abedbae7b3c99cc30ab9e76af86a16ed3f0ca4e`

| Slot logique original | Set | Classe | Mod�le | Statut | Input SHA-256 | Schema SHA-256 | Output SHA-256 | Tokens in/out/total | Co�t USD |
|---|---|---|---|---|---|---|---|---|---|
| `cal.generation.course.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `e992146ad686e2835e08f7951bd2823fb73308c804ab69f0c7eac9296fd3ce28` | `38119a91a7a8f8a26cbd7d3397092b35ba9103d0336b89b6c7b349ffbc75cb97` | `4c224e7b85af14a1f9a33cbd292c4567a45aef7fcbda02fde7d64ff6cf8d3fcb` | `551/159/710` | `0.003010` |
| `cal.generation.course.primary.r2` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `01534c3cca946c94b8b9e72c43cd48833e83123ac2eba312f243d6b52a60bb75` | `38119a91a7a8f8a26cbd7d3397092b35ba9103d0336b89b6c7b349ffbc75cb97` | `53d4b056c16cc1212a4b9f7995f1d01bb2c8333793aaeca5ed77abdba8baf1a5` | `551/186/737` | `0.003334` |
| `cal.generation.course.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-sol` | `COMPLETED` | `fc729ee231f8c5e21683162c09c60acf9a22a24d51521c26dd2f2b5e81ff1bb1` | `38119a91a7a8f8a26cbd7d3397092b35ba9103d0336b89b6c7b349ffbc75cb97` | `e264b018ede1f08f38540e5142f73f1f655fea664887c8c64217a1c5ce87d249` | `552/154/706` | `0.005288` |
| `cal.generation.exercise.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `e36cd6f9e81e579f2c314fac6f8adf7da8ebbb0d76161aa7d1f9802a04c79101` | `84d081b46ca537d8a5ba44ab68e308eedd3ab516e27403f651b1949f3aa84958` | `aded5d6dd52e3250670954803445ac4dddc9ae81843af62eaab85bcd2335f01b` | `531/207/738` | `0.003546` |
| `cal.generation.assessment.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `37addb2cd37969d0d1c636f1d567b8a928db26ce34ca3af0abd0080064fe0781` | `ef6ced46cea0eded0b8452a4e927f591b5359d165ea8cd02619cf1a083732491` | `6f1436688c314bc3e900c6d77747d7e5eb12f60c107cfc1a3d9772072876d059` | `559/233/792` | `0.003914` |
| `cal.generation.assessment.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-sol` | `COMPLETED` | `b5efddae7128f701181ee6aef3cffc88a7c366d1a23db8522dee82c38d55e317` | `ef6ced46cea0eded0b8452a4e927f591b5359d165ea8cd02619cf1a083732491` | `e88365bc63f7f40774e3c44df19ad61e6ab0290035e9b19b3a64c305451f6955` | `560/296/856` | `0.008160` |
| `cal.generation.qcm.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `7039bdd223e727f113a9fccd05782b14ab7a867eb958b40aa4f0b16cd8ef91f9` | `ad45276fd7157873ffd8e7e554d34ac2e8440becac9f9ab179213829cbc0e316` | `a4567ef0f93d856799cc1df88924a2ecd95ce0273c6a1aefdb2f23831bba1036` | `558/151/709` | `0.002928` |
| `cal.generation.qcm.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-sol` | `COMPLETED` | `d56a41015eb4a5ed7c262fb609a4a3e1573491934a5121d68cdac8ba6dfc75cf` | `ad45276fd7157873ffd8e7e554d34ac2e8440becac9f9ab179213829cbc0e316` | `6884150bf6a88db77fd0d2e0afdd623d6a30f2f2ba4be8efca09f77fef1a7306` | `559/148/707` | `0.005196` |
| `cal.transformation.resource.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `e4d2698d6d204fac0490b4fc0f14cebcfc251b74064f462960624cc7fa78a523` | `bbb1434db8699c03e27c587265ffd777c571d8e1b908fe436b74f58ecab22fc0` | `965d11d36db35d200c1616930e0357d2089e18a3878d44e4f71a981714c94975` | `585/167/752` | `0.003174` |
| `cal.transformation.resource.primary.r2` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `97f6f00f84de340c011139d6696d05e159e657e6f86241d7883937a8139c6e1c` | `bbb1434db8699c03e27c587265ffd777c571d8e1b908fe436b74f58ecab22fc0` | `b7e67be59faf25133033eabdcccd6048dd2359bea7c9c5e6592ae41ef1887590` | `585/173/758` | `0.003246` |
| `cal.correction.remediation.primary.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-sol` | `COMPLETED` | `4c4a8a49c8ca71b490e69f016f49c2a018ae3a4acdaa49e8e59cebb789f8bcea` | `0f296374247427a04bc2118acf146ee2bb9d1be4f112c2e7811a3e66ccdc827f` | `9966a3cc5773a25db17c370a749cb20e691907d42e1413f75f96e938c93c3122` | `586/199/785` | `0.006324` |
| `cal.correction.remediation.primary.r2` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-sol` | `COMPLETED` | `5ae5d7c6c273f82810be1e6457bcfd0ae71fc04bea3f3ac71cd2c197ed0b5ecc` | `0f296374247427a04bc2118acf146ee2bb9d1be4f112c2e7811a3e66ccdc827f` | `02b5f41ec210c535dd5eef249ee9d2ff4b7c5cc03d9536eaeda4bf49f7beb07f` | `586/194/780` | `0.006224` |
| `cal.correction.remediation.fallback.r1` | `G2` | `EXACT_ORIGINAL_RESULT` | `gpt-5.6-terra` | `COMPLETED` | `9e6796744031339ad28609ce09040358d09d86caeb95ccaabe63de846d770dec` | `0f296374247427a04bc2118acf146ee2bb9d1be4f112c2e7811a3e66ccdc827f` | `04b29a9193b71cc596ed61586fbfef9f1c600d6a17126c2e62bdd68a66170bf1` | `587/203/790` | `0.003610` |
| `cal.score.anchor.scn-01.a.clarity.r1` | `R2` | `EXACT_REMEDIATION_EQUIVALENT` | `claude-sonnet-5` | `PASSED` | `6c6ff1c3b4d4b3687b4e3c8230559577a7e5d3582d53b44157e4e6ee9fe39e68` | `968312b8f7f4059cfb47b4c70bff98ec14f61089b2b72fa78821368d62bc4dc1` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `979/168/1147` | `0.003638` |
| `cal.review.exercise.primary.r1` | `R2B` | `AUTHORIZED_PARAMETER_REMEDIATION` | `gpt-5.6-sol` | `PARTIAL` | `4200833083b1709e581c3c6fa374acdcfc064f95b9fec0507fff4c7609ec117a` | `844a0a76f9dc828c9e7dc89ed3ea724e209fb8abbb5f1d688683aa04ea20851f` | `8430b6ae90a17451a94f69557de3aef1bca45e3e78ca6dff743ac161a4aac65b` | `873/1561/2434` | `0.034712` |

## Selected-output dependencies

| Source logique | Output SHA-256 | Appels scorer d�pendants |
|---|---|---|
| `cal.generation.course.primary.r1` | `4c224e7b85af14a1f9a33cbd292c4567a45aef7fcbda02fde7d64ff6cf8d3fcb` | `cal.score.output.scn-03.clarity.r1, cal.score.output.scn-03.level-adaptation.r1` |
| `cal.transformation.resource.primary.r1` | `965d11d36db35d200c1616930e0357d2089e18a3878d44e4f71a981714c94975` | `cal.score.output.scn-04.fidelity.r1, cal.score.output.scn-04.level-adaptation.r1` |
| `cal.generation.exercise.primary.r1` | `aded5d6dd52e3250670954803445ac4dddc9ae81843af62eaab85bcd2335f01b` | `cal.score.output.scn-05.difficulty-appropriateness.r1, cal.score.output.scn-05.instruction-clarity.r1` |
| `cal.generation.assessment.primary.r1` | `6f1436688c314bc3e900c6d77747d7e5eb12f60c107cfc1a3d9772072876d059` | `cal.score.output.scn-06.assessment-clarity.r1, cal.score.output.scn-06.marking-scheme-coherence.r1` |
| `cal.correction.remediation.primary.r1` | `9966a3cc5773a25db17c370a749cb20e691907d42e1413f75f96e938c93c3122` | `cal.score.output.scn-07.correction-quality.r1, cal.score.output.scn-07.remediation-clarity.r1` |
| `cal.generation.qcm.primary.r1` | `a4567ef0f93d856799cc1df88924a2ecd95ce0273c6a1aefdb2f23831bba1036` | `cal.score.output.scn-08.distractor-quality.r1, cal.score.output.scn-08.feedback-quality.r1` |

R�sultat : `SELECTED_OUTPUT_DEPENDENCIES = 6/6`, couvrant exactement 12 slots de scoring.

## �quivalences de rem�diation

- Anthropic R2 mappe exactement vers `cal.score.anchor.scn-01.a.clarity.r1` avec la classe `EXACT_REMEDIATION_EQUIVALENT`.
- OpenAI Review R2B mappe vers `cal.review.exercise.primary.r1` avec la classe `AUTHORIZED_PARAMETER_REMEDIATION`.
- Hash logique input original/rem�diation : `f8c7988a4edf2529d7bb0e201087f52d5635c96de98c804ca6d539c8e82af172` / `f8c7988a4edf2529d7bb0e201087f52d5635c96de98c804ca6d539c8e82af172`.
- Hash schema original/rem�diation : `844a0a76f9dc828c9e7dc89ed3ea724e209fb8abbb5f1d688683aa04ea20851f` / `844a0a76f9dc828c9e7dc89ed3ea724e209fb8abbb5f1d688683aa04ea20851f`.
- Diff�rences autoris�es : `max_output_tokens 1024 -> 4096` et `reasoning effort implicit/default -> low`.
- Le r�sultat R2B est `PARTIAL`, post-valid�, sans incompl�tude ni diagnostic priv�.

## Comptabilit� et co�ts historiques

- Slots originaux : `96`
- R�sultats r�utilisables : `15`
- Slots restants : `81`
- Co�ts r�els d�j� mesur�s : G2 `1.958050 USD`, R2 `0.027598 USD`, R2B `0.034712 USD`.
- Les r�serves historiques ne sont pas trait�es comme des factures.
- Aucun contenu brut n'est reproduit dans ce baseline.
