# Phase 12.16-G2-V5.1 — Audit de l'attente de la gate

## Sémantique canonique V4

La baseline V4 déclare :

- `mixed_role = NON_DELIVERABLE_NEGATIVE_CONTROL`;
- `weak_role = NON_DELIVERABLE_NEGATIVE_CONTROL`;
- `ABSOLUTE_QUALITY_LABELS = DIAGNOSTIC_ONLY`;
- `MIXED_VS_WEAK_ORDERING = SECONDARY_DIAGNOSTIC_NON_BLOCKING`.

La revue humaine corrigée confirme pour SCN-06 : Strong livrable, Weak à réviser,
Mixed à rejeter, avec `Strong > Weak > Mixed` sur le critère exact. Le corpus V4 ne
promet donc pas que ce Mixed soit situé entre Strong et Weak sur l'échelle V5.

## Confusion introduite par la gate V5.1

Le corpus synthétique V5 possède bien une classe artificielle `MIXED = 2`, mais la
documentation précise que les 24 anchors historiques V4 restent inchangés et que leur
compatibilité structurelle ne prouve pas leur classement sémantique réel.

La gate du mini-pilote franchit cette frontière :

- `_semantic_role()` déduit `INTERMEDIATE` de la seule présence de `.mixed.` dans le
  call ID;
- `_prior_stage_passes()` impose ensuite `1 <= mixed.score_level <= 3`;
- aucun audit check-by-check de l'anchor historique ne justifie cette conversion.

Elle impose ainsi une propriété des fixtures synthétiques à un contrôle négatif
historique dont le contenu et la revue humaine établissent au contraire le niveau `0`.

## Résultat

`MIXED_GATE_EXPECTATION = OVERCONSTRAINED`

Le run historique reste correctement classé `V5_1_MINI_PILOT_FAIL` selon sa gate
figée. La présente analyse ne réécrit pas ce résultat; elle établit que la condition
qui l'a produit n'est pas une attente sémantique valide pour cet anchor.
