# Phase 12.17.5 — Audit de couverture des tests

```text
TEST_COVERAGE_PERCENT = 89.3
COVERED_AUDIT_CONTROLS = 25
TOTAL_AUDIT_CONTROLS = 28
HTTP_TESTS_REQUIRED_NOW = 0
```

Le pourcentage mesure 28 contrôles critiques auditables, et non le nombre de
lignes de code : READ-15 `9/10`, handoffs CAP `3/3`, vocabulaires `10/10`,
migration `3/5`. Les tests HTTP ne sont pas pénalisés puisque l'endpoint est
explicitement hors périmètre.

| Bloc | Couverture | Preuves principales | Gap |
|---|---:|---|---|
| READ-15 | 9/10 | unit query/not-found, route Application, adapter réel, architecture, B09 | pas de test inbound négatif + aucune borne ref |
| CAP-R02/A01/A02 handoff | 3/3 | guard B09 owner/order/not-implemented | use cases futurs non comptés |
| dix familles | 10/10 | `test_sqlite_vocabulary_mappings.py` | aucun gap de codec |
| migration/runtime | 3/5 | SHA, checksum/idempotence, count/FK/seed safety | defaults et contraintes non-SHA non préservés/testés |

## Replays exécutés

- contrats/mappings/READ-15/B09 : `32 passed in 6.79s` ;
- cycle SQLite réel et seed/runtime : `18 passed in 43.83s` ;
- guards architecture ciblés complémentaires : `17 passed in 2.58s` ;
- mypy actif : `0/42` ;
- mypy backend : `0/671` ;
- freeze historique : `40/40`, nouveaux drifts `0`.

La suite globale n'a pas été rejouée : la preuve d'entrée 12.17.4
`4725 passed, 24 skipped, 0 failed` est conservée comme carry-forward.

## Tests exigés avant remédiation

1. comparer le DDL de `document` avant/après 001, en autorisant uniquement le
   CHECK SHA et le ledger ;
2. prouver la conservation des quatre defaults ;
3. prouver la conservation du CHECK `size_bytes >= 0` ;
4. ajouter un test négatif de payload READ-15 et un contrat explicite de borne.
