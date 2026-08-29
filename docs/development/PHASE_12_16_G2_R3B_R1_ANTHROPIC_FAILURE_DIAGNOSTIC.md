# Phase 12.16-G2-R3B-R1 — Diagnostic Anthropic hors ligne

## Décision

- Diagnostic : `COMPLETE`.
- Classification : `UNKNOWN_WITH_INSUFFICIENT_EVIDENCE`.
- Cause plus précise : `NON PROUVÉE` faute de statut HTTP, de type SDK fermé et de preuve de réponse.
- Appels fournisseurs R1 : `0` ; coût fournisseur R1 : `0.000000 USD`.
- R3 reste interrompu ; aucun retry, resume ou appel R2 n'a été exécuté.

## Preuves R3B gelées

- Ledger SHA-256 : `5722c7e4ba80a40d169997c34de9d764fe63781bc804b74ed2d3d19d1f46175f`.
- Summary SHA-256 : `44b71e0d6e0da0828235af15a26bb66a6e6d5ff923264c413cc454420c3b79b7`.
- Raws présents : `9`.
- Matrice/manifeste SHA-256 : `245f0c8b2e4d74f61ec58bd5b02824b4d0edfae3dbd55c1c518a9a09ccecee98` / `cace6d138a8ac1fef2920fc45abedbae7b3c99cc30ab9e76af86a16ed3f0ca4e`.
- Plafond approuvé : `2.687480 USD`.
- États : `{"COMPLETED": 9, "FAILED": 1, "PENDING": 71, "STARTED": 0}`.
- Appels tentés : `10` ; retry/rerun/duplicate : `0/0/0`.

## Appel échoué — champs sûrs

- Call : `r3.cal.score.anchor.scn-01.c.clarity.r1` ; slot : `cal.score.anchor.scn-01.c.clarity.r1`.
- Début/fin/latence : `2026-08-29T19:37:16+00:00` / `2026-08-29T19:37:24+00:00` / `8448 ms`.
- Provider/modèle/profil : `anthropic` / `claude-sonnet-5` / `anthropic.claude-sonnet-5.scorer`.
- Input ref / critère : `anchor:cal.scn-01.c` / `scn-01.quality.clarity`.
- Max output : `512` ; usage input/cache/output/total : `0/0/0/0`.
- Statuts : `FAILED` / `ERROR` / `None`.
- Erreur fermée/catégorie : `ANTHROPIC_SCORER_TRANSPORT_UNAVAILABLE` / `UNAVAILABLE`.
- Raw présent/path/hash : `False` / `None` / `None` ; réserve : `0.021120 USD`.

## Reconstitution locale exacte

- Observation SHA-256 : `ca1906fafb88814565125c344f31e051fd154d4bd17ca267517d991f70dabd79`.
- Input sérialisé SHA-256 : `b6cc367de3229a83ac3af9cdf717db21b00aad6a9dc23b490dd2fb35343b914f` ; taille : `971 / 8000 octets`.
- System SHA-256 : `fcbefdcfa849619f27637c581475b2d2bbfd45063e7e4f476bee802bf3eb69ea`.
- Schéma logique/provider SHA-256 : `968312b8f7f4059cfb47b4c70bff98ec14f61089b2b72fa78821368d62bc4dc1` / `607a6736853b8ab5ab3e95926a51ebef12191ffa8b2f43b5ef9826fca19d54f7`.
- Bounded / logique valide / transformable : `True` / `True` / `True`.
- Modèle/profil/max tokens : `claude-sonnet-5` / `anthropic.claude-sonnet-5.scorer` / `512`.

## Comparaison avec les trois succès Anthropic

| Call | Slot logique | Observation SHA-256 | Input SHA-256 | Raw SHA-256 | Score |
|---|---|---|---|---|---|
| `r3.cal.score.anchor.scn-01.a.organization-utility.r1` | `cal.score.anchor.scn-01.a.organization-utility.r1` | `be4998662dd15e8a6f713c91965061638f4042e85b6d27f937d21b09afa4abfd` | `83d6a522c35bdf7dce432214a7c862a2ca6baf8d2095351a34ba466a6ec62c74` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `1/1` |
| `r3.cal.score.anchor.scn-01.b.clarity.r1` | `cal.score.anchor.scn-01.b.clarity.r1` | `518126c3b23def9d351928cb2d286c32d5f2fef1da0475ae85327e610199241c` | `4e84e18d5b6d8a38b1835610392066e8e22d55d9ae028b347dbedd0f52c5aefa` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `1/1` |
| `r3.cal.score.anchor.scn-01.b.organization-utility.r1` | `cal.score.anchor.scn-01.b.organization-utility.r1` | `abab1bbb8b8ea9f3fd585d8512ecfb3a9c6ddeb33a5ed3bf63d3d65e02460801` | `78386202089728bbb88616a6163168a759be488fa663b3421406e631827a216f` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `1/1` |

- Inputs distincts : `4` ; observations distinctes : `4`.
- Slots succès distincts : `3` ; schémas logique/provider distincts sur les quatre requêtes : `1/1`.
- Hashes raw distincts : `1` pour `3` appels terminés.
- `IDENTICAL_SCORE_BYTES != DUPLICATE_PROVIDER_CALL` : les identités d'entrée et les call IDs prouvent trois appels distincts ayant retourné le même score rationnel `1/1`.

## Renforcement privé

- Taxonomie ajoutée : `CONFLICT`, `REQUEST_TOO_LARGE`, `OVERLOADED`, `EMPTY_RESPONSE`.
- Diagnostics fermés : statut HTTP, type d'erreur, réponse reçue, stop reason, nombre de blocs texte et usage numérique.
- `409`, `413`, `529/OverloadedError`, réponse 200 vide et exception SDK non mappée sont désormais distingués sans corps, message, header ni request ID.
- Le SDK conserve `max_retries=0`. Les contrats publics `EvaluationScorerPort` et `ScorerOutcome` ne changent pas.
- Aucun ADR : aucune politique de retry ni frontière architecturale n'est modifiée.

## Validations hors ligne

- Tests ciblés calibration/Anthropic/architecture : `PASS`.
- R3B selftest : `PASS`.
- Pytest global : `4227 passed, 3 skipped` ; skips = gates live explicitement fermés.
- Ruff, mypy backend+harness, compileall et diff-check : `PASS`.
- Gates SQLite réelles locales : `22 passed`.
- Gates live provider : `FERMÉS` ; résolution de credentials et construction de transport R1 : `0`.
- Scan sécurité/path/raw : `PASS` ; aucun contenu brut, secret ou chemin utilisateur dans les rapports.

## Suite fermée

Le canary distinct `12.16-g2-r3b-r2-anthropic-canary-v1` est seulement préparé. Son exécution exige l'approbation exacte publiée dans le plan de coût compagnon.
Même après un futur canary réussi, les 71 appels ne seront pas repris directement : un lot offline R3B-R3 devra importer le résultat par hash, préserver les 9 succès, dériver 71 appels, recalculer checksum/plafond et demander une nouvelle approbation.
