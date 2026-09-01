# Phase 12.16-G2-V5.2 — Modèle de gate sémantique

## Contrat

- Version : `12.16-g2-v5.2-semantic-gate-v1`.
- SHA-256 logique :
  `8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea`.
- Dérivation du score : `EXPLICIT_PREVALIDATED_CHECK_COUNT`.
- Inférence depuis un nom de tier : `FORBIDDEN`.
- Intermédiaire : exigé seulement si un anchor prévalidé est disponible.
- Distribution : au moins deux niveaux absolus distincts.

Chaque attente encode : call et anchor IDs, scénario, critère, rôle, checks attendus,
score exact ou plage, relation pairwise éventuelle, sources humaines et version.

## Attentes explicites

| Call | Anchor(s) | Rôle | Checks attendus | Score/relation | Source |
|---|---|---|---|---|---|
| `cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1` | `cal.v4.scn-06.315be9953fb2` | `DELIVERY_CANDIDATE` | checks 1, 2, 3, 4 | `4` | audit V5.1 + formulaire humain corrigé |
| `cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1` | `cal.v4.scn-06.a74ef2a40cb1` | `NON_DELIVERABLE_NEGATIVE_CONTROL` | aucun | `0` | audit V5.1 + formulaire humain corrigé |
| `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1` | `cal.v4.scn-06.74ba8e9a9af4` | `NON_DELIVERABLE_NEGATIVE_CONTROL` | check 1 | `1` | audit V5.1 + formulaire humain corrigé |
| `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1` | Strong / Mixed SCN-06 | `BLIND_PAIRWISE_PREVALIDATED` | n/a | `A_BETTER` | formulaire humain corrigé |
| `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1` | Strong / Mixed SCN-01 | `BLIND_PAIRWISE_PREVALIDATED` | n/a | `A_BETTER` | formulaire humain corrigé |

Les attentes Mixed et Weak partagent volontairement le même rôle. Leurs scores
diffèrent uniquement parce que leurs ensembles de checks sont respectivement de
cardinalité `0` et `1`. La relation SCN-06 dérivée est donc :

`Strong (4) > Weak (1) > Mixed (0)`.

## Verdict futur

Le verdict V5.2 vérifiera :

1. parser/schema;
2. equality des checks observés et prévalidés;
3. score dans la plage explicite;
4. relations pairwise explicites;
5. intermédiaire seulement si prévalidé et disponible;
6. distribution absolue non dégénérée;
7. evidence-first et provenance.

La gate séquentielle reste fail-closed et exige une approbation de plafond ainsi que
deux flags live explicites. Dans ce lot, le plafond n'est pas approuvé et le live
reste fermé.
