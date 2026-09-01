# Phase 12.16-G2-V5 — Carte d'intégration sémantique hors ligne

## Résultat

`scorer_contract_v5` est intégré à la pipeline de calibration sans modifier les chemins V4 historiques. L'intégration est compositionnelle et strictement hors ligne.

| Responsabilité | Intégration V5 | Garantie |
|---|---|---|
| Observation absolue | `build_v5_observation` produit un `V5ScorerObservation` | projection bornée, critère unique, scénario canonique, aucune identité fournisseur/producteur |
| Observation pairwise | `build_v5_observation` produit un `V5PairwiseObservation` | identifiants opaques, deux projections, aucun tier ou score attendu sérialisé |
| Parser/validation | `parse_v5_call_result` route vers `parse_v5_score_output` ou `parse_v5_pairwise_output` | schémas fermés, evidence-first, incohérences rejetées |
| Métriques | `build_semantic_pilot_report` calcule distribution 0–4, extrêmes, intermédiaires, monotonie, inversions et pairwise | tiers utilisés uniquement côté analyse |
| Reporting | `V5PilotReport.safe_payload` | aucun contenu candidat, provenance et verdict typés |
| Call planning | `V5_LOGICAL_CALL_MATRIX` | 102 records V4.2 mappés et 11 comparaisons V5 ajoutées |
| Runner guard | `V5PilotBudgetGuard` | baseline, matrice, pricing, manifest et contrat vérifiés avant toute frontière credential |
| Canaries | `evaluate_canary_gate` | `Strong > Mixed > Weak`, score intermédiaire et pairwise correct requis avant fanout |

## Topologie

La matrice logique V5 contient 113 records :

- 20 appels OpenAI V4.2 inchangés, éligibles au carry-forward ;
- 82 appels Anthropic absolus à rejuger sous V5 ;
- 5 pairwise directs d'anchors ciblant les cinq inversions historiques ;
- 6 pairwise directs d'outputs sur SCN-03, SCN-06 et SCN-07.

Le contrat V5 n'est jamais branché dans un adaptateur OpenAI ou Anthropic. Il demeure provider-neutral. Les appels historiques V4.2, leurs artefacts et leurs contrats n'ont pas été modifiés.

## Frontières préservées

- génération/review OpenAI : contrat V4.2 inchangé ;
- scoring V4 historique : code et artefacts conservés comme preuve ;
- V5 : nouveau module `tests/calibration/pedagogical/semantic_integration_v5.py` ;
- aucune base SQLite, donnée runtime ou sortie brute n'entre dans Git ;
- aucune route runtime n'est modifiée.

`LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.

