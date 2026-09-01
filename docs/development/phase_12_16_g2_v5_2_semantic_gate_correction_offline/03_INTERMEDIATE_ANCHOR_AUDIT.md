# Phase 12.16-G2-V5.2 — Audit d'un anchor intermédiaire réel

## Résultat

`INTERMEDIATE_ANCHOR_AVAILABLE = FALSE`

Les 24 anchors historiques V4 disposent d'une revue humaine de disposition et de
relations pairwise, mais pas d'une prévalidation humaine check-by-check établissant
explicitement un niveau V5 `2` ou `3`. Les 96 fixtures synthétiques V5 couvrent ces
niveaux, mais ne constituent pas des anchors historiques prévalidés par l'humain.

Aucun nom Strong/Mixed/Weak, label historique ou score provider antérieur n'est donc
utilisé pour fabriquer une attente intermédiaire.

## Proposition à prévalider

- Version : `12.16-g2-v5.2-intermediate-proposal-v1`.
- ID : `cal.v5.2.proposed.scn-06.marking-scheme-coherence.intermediate-v1`.
- Critère : `scn-06.quality.marking-scheme-coherence`.
- Cible : checks 1 et 2 seulement, score théorique `2`.
- SHA-256 de projection proposée :
  `fa4d7468a5c40a285b45066b7341f1e2f32a1e496ff1f593c3710806c15ebb87`.
- Statut : `PROPOSED_REQUIRES_HUMAN_PREVALIDATION`.

Le barème proposé répartit six points entre deux questions et identifie un point de
formule par question, sans point séparé pour application numérique, unité ou
vérification. Ce contenu est seulement un candidat de revue : il n'est ajouté ni au
corpus, ni à la matrice, ni au mini-pilote, ni au scope de transfert.

## Condition de promotion

Une future intégration exige une validation humaine explicite des checks, une nouvelle
version d'anchor, un nouveau hash de projection, une nouvelle matrice et une nouvelle
autorisation. Jusqu'alors, la présence d'un score intermédiaire est diagnostique et
non bloquante.
