# Phase 12.17.2 — Audit de reachability runtime

## Résumé

| Reachability | Erreurs | Fichiers |
| --- | ---: | ---: |
| Runtime de production `backend` | 0 | 0 |
| Transitif depuis `pairwise_output_contract_v5_2_4.py` | 29 | 12 |
| Ajouté uniquement par `test_pairwise_output_contract_v5_2_4.py` | 4 | 3 |
| Total import-driven | 33 | 15 |

## Chemins d'import représentatifs

```text
pairwise_output_contract_v5_2_4
-> semantic_integration_v5
-> repair_tranche_v4_2
-> call_plan_v4_1
-> tests.providers.anthropic.scorer
-> tests.providers.anthropic.transport
```

```text
pairwise_output_contract_v5_2_4
-> semantic_integration_v5
-> anchor_corpus_v4
-> anchor_corpus_v2 / anchor_corpus_v3 / catalog
```

```text
test_pairwise_output_contract_v5_2_4
-> semantic_gate_v5_2
-> semantic_mini_pilot_v5_1
```

## Interprétation

Tous les fichiers sont importables et certains ont été exécutés comme outillage lors des calibrations réelles. Aucun n'est toutefois importé par le runtime produit sous `backend` ni par le package `evaluation_harness`. La classification correcte est donc `TOOLING_OR_TEST_ONLY`, avec sous-classe `OPERATIONAL_CALIBRATION_TOOLING` pour le transport/scorer et les builders live.

La présence d'un vrai SDK dans un fichier sous `tests` est traitée comme problème de placement potentiel, pas comme reachability production.
