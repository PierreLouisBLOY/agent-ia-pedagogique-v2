# Phase 12.16-G2-V4.3 — Table de discrimination

## Périmètre et convention

Cette analyse est strictement hors ligne. Elle reconstruit les 16 triplets depuis `artifacts/calibration/12.16-g2-v4-2/safe_report.json`, dont les 63 résultats carry-forward sont reliés au ledger V4.1 par la provenance V4.2.

- Ordre attendu par la métrique de monotonie : `Strong > Mixed > Weak`.
- `Delta S-M`, `M-W` et `S-W` sont des différences rationnelles signées.
- `PASS` exige les deux inégalités strictes adjacentes.
- `Justification scorer = NON_ENREGISTREE_PAR_LE_CONTRAT` signifie que le payload Anthropic ne contient que `status`, `score_numerator` et `score_denominator`. Aucune justification textuelle ou structurée n'existe dans les sorties brutes.

## Table exhaustive

| Scénario | Critère | Strong | Mixed | Weak | Ordre observé | S-M | M-W | S-W | Monotonie stricte | Type d'écart | Justification scorer |
|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|
| SCN-01 | `scn-01.quality.clarity` | 1 | 0 | 1 | S = W > M | 1 | -1 | 0 | FAIL | inversion M < W; tie S = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-01 | `scn-01.quality.organization-utility` | 1 | 0 | 0 | S > M = W | 1 | 0 | 1 | FAIL | tie M = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-02 | `scn-02.quality.relevance` | 1 | 1 | 1 | S = M = W | 0 | 0 | 0 | FAIL | ties S = M et M = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-02 | `scn-02.quality.coverage` | 1 | 1 | 1 | S = M = W | 0 | 0 | 0 | FAIL | ties S = M et M = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-03 | `scn-03.quality.clarity` | 1 | 1 | 0 | S = M > W | 0 | 1 | 1 | FAIL | tie S = M | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-03 | `scn-03.quality.level-adaptation` | 1 | 1 | 0 | S = M > W | 0 | 1 | 1 | FAIL | tie S = M | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-04 | `scn-04.quality.fidelity` | 1 | 0 | 1 | S = W > M | 1 | -1 | 0 | FAIL | inversion M < W; tie S = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-04 | `scn-04.quality.level-adaptation` | 1 | 0 | 0 | S > M = W | 1 | 0 | 1 | FAIL | tie M = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-05 | `scn-05.quality.difficulty-appropriateness` | 1 | 1 | 0 | S = M > W | 0 | 1 | 1 | FAIL | tie S = M | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-05 | `scn-05.quality.instruction-clarity` | 1 | 1 | 0 | S = M > W | 0 | 1 | 1 | FAIL | tie S = M | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-06 | `scn-06.quality.assessment-clarity` | 1 | 0 | 1 | S = W > M | 1 | -1 | 0 | FAIL | inversion M < W; tie S = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-06 | `scn-06.quality.marking-scheme-coherence` | 1 | 0 | 1/2 | S > W > M | 1 | -1/2 | 1/2 | FAIL | inversion M < W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-07 | `scn-07.quality.correction-quality` | 1 | 0 | 0 | S > M = W | 1 | 0 | 1 | FAIL | tie M = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-07 | `scn-07.quality.remediation-clarity` | 1 | 0 | 0 | S > M = W | 1 | 0 | 1 | FAIL | tie M = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-08 | `scn-08.quality.distractor-quality` | 1 | 0 | 1 | S = W > M | 1 | -1 | 0 | FAIL | inversion M < W; tie S = W | NON_ENREGISTREE_PAR_LE_CONTRAT |
| SCN-08 | `scn-08.quality.feedback-quality` | 1 | 0 | 0 | S > M = W | 1 | 0 | 1 | FAIL | tie M = W | NON_ENREGISTREE_PAR_LE_CONTRAT |

## Lecture des gates

- Monotonie trinaire stricte : `0/16`.
- Monotonie trinaire faible : `11/16`.
- Inversions adjacentes : `5`, toutes de type `Mixed < Weak`.
- Ties adjacents : `13/32`.
- La gate primaire V4 définie par `STRONG_STRICTLY_PREFERRED_TO_EACH_NEGATIVE` n'est pas identique à la monotonie trinaire. Recalculée séparément, elle est satisfaite pour `6/16` critères : organisation-utilité SCN-01, adaptation SCN-04, cohérence du barème SCN-06, les deux critères SCN-07 et feedback SCN-08.
- Le classement `Mixed > Weak` est explicitement `SECONDARY_DIAGNOSTIC_NON_BLOCKING` dans la sémantique V4. Les cinq inversions restent donc un signal de faible discrimination, mais ne doivent pas être présentées comme cinq violations autonomes de la gate primaire.

## Conclusion

La reconstruction concorde exactement avec le safe report : aucune monotonie stricte, cinq inversions et treize ties adjacents. Les données ne permettent pas d'attribuer une justification individuelle au Scorer, car cette information n'est ni demandée ni enregistrée par son contrat.
