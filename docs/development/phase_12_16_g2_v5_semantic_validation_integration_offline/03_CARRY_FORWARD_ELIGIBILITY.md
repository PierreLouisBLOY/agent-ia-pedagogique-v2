# Phase 12.16-G2-V5 — Éligibilité carry-forward

## Source certifiée

La source est `artifacts/calibration/12.16-g2-v4-2/safe_report.json`, SHA-256 `3cbe5c7bbf5fc0a4b34f0b3810656666969355d7fde3fa643b9ae05371082c1a`. Elle contient 102 résultats sur 102 au statut `COMPLETED` et une décision `CALIBRATION_COMPLETE`.

Le statut `COMPLETED` n'est pas suffisant. Un résultat est réutilisable seulement si toutes les propriétés canoniques et le hash de call-spec sont identiques.

## Décision

| Disposition | Nombre | Justification |
|---|---:|---|
| `CARRY_FORWARD` | 20 | appels OpenAI exacts, résultat source completed, hash V4.2 = hash V5 |
| `REJUDGE_WITH_V5` | 82 | prompt et contrat scorer/parser modifiés |
| `NEW_V5_PAIRWISE` | 11 | aucun résultat historique équivalent |

`CARRY_FORWARD_COUNT = 20`.

Les 20 résultats carry-forward ne doivent pas être retransmis à un fournisseur. Les 82 anciens résultats Anthropic ne sont pas réutilisés comme jugements V5. Les onze comparaisons directes ne peuvent hériter d'aucun résultat post-hoc V4.

## Provenance

Le rapport pilote expose :

- le hash de matrice V5 ;
- le hash du contrat scorer ;
- le hash pricing ;
- le nombre de carry-forward ;
- le nombre de nouveaux appels attendus et observés ;
- l'absence de contenu candidat dans le payload sûr.

Une divergence du safe report, une ligne manquante, un doublon ou un statut non terminal provoque un arrêt fail-closed.

