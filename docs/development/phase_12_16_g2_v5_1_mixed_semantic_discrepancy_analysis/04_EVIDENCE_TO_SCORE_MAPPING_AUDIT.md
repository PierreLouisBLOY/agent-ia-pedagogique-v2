# Phase 12.16-G2-V5.1 — Audit evidence vers score

## Invariants du contrat

Le parser V5.1 normalise le JSON puis délègue au contrat canonique V5. Celui-ci :

- refuse les checks inconnus ou dupliqués;
- exige que les défauts couvrent exactement les checks manquants;
- calcule le niveau par le nombre de checks positifs (`0..4`);
- force `0` uniquement en présence d'une contradiction matérielle;
- rejette tout score qui ne correspond pas à ce calcul.

Le statut parser/schema `PASS` prouve donc que le score `0` était compatible avec
l'evidence structurée effectivement reçue. Le ledger ne conserve pas les formulations
de cette evidence : seules la couverture evidence-first, la valeur `0` et les
métadonnées sûres sont disponibles.

## Vérification indépendante sur le contenu local

| Check | Constat sur le Mixed | Satisfait |
|---|---|---|
| Points par question | « 6 points globalement », explicitement sans répartition par question | Non |
| Formule | Explicitement aucune attribution pour la formule | Non |
| Application numérique | Explicitement aucune attribution pour l'application | Non |
| Résultat, unité, vérification | Explicitement aucune attribution pour résultat ou unité; aucune vérification | Non |

Le résultat local est `0/4`, donc niveau `0`. Il n'est pas nécessaire d'invoquer une
contradiction ni une règle bloquante pour atteindre ce niveau.

## Recherche d'un collapse binaire

Le mapping du contrat n'est pas binaire : les niveaux `1`, `2` et `3` correspondent
respectivement à un, deux et trois checks satisfaits et sont couverts par les fixtures
synthétiques. Le cas analysé tombe réellement sur l'extrême `0` parce que son texte
nie ou omet chacun des quatre checks. Le collapse se trouve dans l'attente de la gate,
qui assimile le nom `mixed` à un niveau intermédiaire, pas dans le calcul evidence vers
score.

## Résultat

`SCORE_MAPPING_CONSISTENCY = PASS`

La conclusion porte sur la cohérence du score. Les formulations provider de
confidence, evidence, défauts et rationale restent `NOT_PERSISTED_BY_SAFE_CONTRACT`
et ne font l'objet d'aucune reconstruction.
