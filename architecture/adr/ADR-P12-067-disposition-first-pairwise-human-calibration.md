# ADR-P12-067 — Calibration humaine disposition-first et pairwise

- Statut : Accepté
- Date : 2026-08-31
- Phase : 12.16-G2-V4-DISPOSITION-FIRST-REMEDIATION-A

## Contexte

La prévalidation humaine v3 est clôturée comme `CLOSED_FAILED_HUMAN_PREVALIDATION_BASELINE`. Les labels absolus ont confirmé la qualité des contenus livrables, mais ils n'ont pas discriminé uniformément les deux contrôles négatifs. La politique produit reste `STRONG_ONLY`; le changement porte sur l'instrument humain, sans baisse d'exigence.

## Décision

La disposition globale mesure directement la livrabilité avec `DELIVER_AS_IS`, `REVISE_BEFORE_DELIVERY`, `REJECT` ou `NON_EVALUABLE`. La comparaison pairwise aveugle mesure séparément, pour chaque critère, la préférence entre les trois candidats. Les labels absolus restent un diagnostic secondaire.

Le rôle `DELIVERY_CANDIDATE` reste réservé au contenu de référence. Les rôles `NON_DELIVERABLE_NEGATIVE_CONTROL` restent distincts; leur ordre relatif demeure secondaire et non bloquant. La gate primaire exige que le candidat livrable soit `DELIVER_AS_IS`, que les deux contrôles ne le soient pas et que le candidat livrable soit strictement préféré à chacun d'eux sur les seize critères.

Un scorer ou un model judge n'obtient aucune autorité runtime. Aucun seuil produit, aucune route fournisseur et aucune gate runtime ne sont créés. Les corpus v1, v2 et v3 restent byte-exact immuables.

## Conséquences

- Le corpus v4 reste un owner test-only offline.
- Les huit contenus livrables sont carry-forward byte-equivalent.
- Seuls les cinq contrôles négatifs associés à l'action humaine v3 `aucune` sont révisés.
- Les onze autres contrôles négatifs sont carry-forward byte-equivalent.
- Le paquet humain masque les tiers, les historiques et les mappings.
- La calibration fournisseur reste interdite.
