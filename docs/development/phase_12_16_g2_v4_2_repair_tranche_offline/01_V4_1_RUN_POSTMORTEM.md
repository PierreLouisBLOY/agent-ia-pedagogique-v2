# Phase 12.16-G2-V4.2 — Postmortem du run V4.1

Date de l'audit hors ligne : 2026-09-01.

## Source immuable

- baseline : `71e4258baacc1f0914cf9a9087638736c2a4ebdd` ;
- matrice V4.1 : `94eb067ac7dd8498eeb2605ee506315fd0c831259f454555ecac88acbe94403a` ;
- pricing : `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` ;
- safe report : `fe25523b4c72d927c4ba71df4d789c3fafeaed8414cd82a342761cc3581eea85` ;
- ledger : `697eb124e5a4883896e2eb17ef7fa4764b7396fdc434dbaf0022a3425a79788f` ;
- résultat : 102 records, 96 appels tentés, 94 terminés, 2 failed, 6 skipped,
  aucun retry et aucun rerun ;
- décision : `CALIBRATION_INCONCLUSIVE`.

Les artefacts V4.1 sont lus sans mutation. L'autorisation live V4.1 est consommée et
n'est pas réutilisable.

## Incidents connus

Le canary OpenAI Review `cal.review.exercise.primary.r1` s'est arrêté au plafond exact
de 2 048 output tokens. Le rapport persiste `provider_response_status=incomplete`,
`incomplete_reason=max_output_tokens`, `structured_output_validation=FAILED` et
`parse_error_category=OUTPUT_TRUNCATED_CONFIRMED`. Il s'agit d'une troncature
confirmée du contrat Review V4.1.

Le call `cal.score.anchor.scn-08.strong.feedback-quality.r2` a échoué avant tout token
avec `ANTHROPIC_SCORER_TRANSPORT_SERVER`. Aucun élément hors ligne ne permet de
requalifier cet incident : il reste un incident serveur fournisseur. Sa future
réexécution explicite reste sans retry automatique.

## Écart supplémentaire découvert par l'audit d'identité

La matrice V4.1 transforme les références
`corpus:12.16-g2-v4-plan-v1:*` en
`corpus:12.16-g2-v4.1-plan-v1:*`. Le runner V4.1 sélectionne cependant le corpus V4
uniquement si la référence commence encore par l'ancien préfixe. Le test échoue donc
pour les références V4.1 et le runner retombe sur `anchor_by_id(...)`, c'est-à-dire les
projections legacy.

Les projections legacy et V4 diffèrent pour chacun des scénarios SCN-01 à SCN-08.
Conséquences méthodologiques :

- 13 sorties OpenAI terminées ont une dépendance source différente de la V4.2 ;
- 18 scores Anthropic de ces sorties dépendent d'un upstream à régénérer ;
- 63 scores Anthropic d'anchors V4 terminés restent identiques et réutilisables ;
- les 7 Reviews non terminées et le scoring Anthropic failed restent à exécuter.

La tranche de huit appels envisagée n'est donc pas sûre. La plus petite tranche
démontrable contient 39 appels.
