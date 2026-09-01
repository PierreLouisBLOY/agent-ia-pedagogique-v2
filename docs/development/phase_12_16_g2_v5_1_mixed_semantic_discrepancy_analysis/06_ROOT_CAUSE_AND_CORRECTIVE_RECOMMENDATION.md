# Phase 12.16-G2-V5.1 — Cause racine et recommandation corrective

## Classification

- `PRIMARY_ROOT_CAUSE = SEMANTIC_GATE_EXPECTATION_TOO_RIGID`
- `SECONDARY_ROOT_CAUSES = NONE`
- `CONFIDENCE = HIGH`

Les alternatives sont écartées :

- `PROJECTION_DROPS_POSITIVE_EVIDENCE` : faux, égalité byte-for-byte;
- `RUBRIC_TOO_HARSH_FOR_MIXED_CASES` : non causal ici, les quatre absences sont
  explicites dans le texte;
- `SCORER_EVIDENCE_TO_SCORE_MAPPING_TOO_BINARY` : faux, le contrat expose cinq
  niveaux et le parser recalcule le score;
- `ANCHOR_MISLABELED_OR_TOO_WEAK` : le candidat est volontairement un contrôle
  négatif V4 et la hiérarchie Mixed/Weak n'est pas bloquante; c'est la gate qui a
  réinterprété son nom.

## Correction minimale recommandée

1. Clore le mini-pilote V5.1 actuel comme baseline diagnostique échouée; ne jamais le
   rerun sous l'autorisation consommée.
2. Créer une gate versionnée V5.2 qui sépare les classes des fixtures synthétiques des
   tiers historiques V4.
3. Pour ce triplet historique, prévalider hors ligne le profil attendu par rubrique :
   Strong `4`, Mixed `0`, Weak `1`, relation `Strong > Weak > Mixed`.
4. Retirer de cette gate précise l'obligation bloquante « Mixed doit être 1..3 ».
   Conserver la présence d'un score intermédiaire comme diagnostic non bloquant.
5. Si le pilote doit obligatoirement tester un niveau intermédiaire réel, sélectionner
   hors ligne un autre anchor dont un ou plusieurs checks sont positifs, le soumettre
   à validation humaine, puis produire de nouveaux hashes de matrice, call-spec et
   scope. Ne pas renommer ni modifier silencieusement l'anchor historique.
6. Exiger une nouvelle approbation propriétaire et une nouvelle autorisation live
   avant tout appel futur.

## Frontières

- Anchor historique modifié : `NON`.
- Rubrique ou scorer modifié : `NON`.
- Gate historique modifiée : `NON`.
- Appel provider : `0`.
- Credential/transport : `NONE`.
- Commit/push : `NONE/NONE`.
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.

`NEXT_GATE = 12.16-G2-V5.2-MINI-PILOT-GATE-REMEDIATION_READY`
