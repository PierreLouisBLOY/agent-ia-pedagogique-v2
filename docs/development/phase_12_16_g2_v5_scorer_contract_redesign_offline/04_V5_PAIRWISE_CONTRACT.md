# Phase 12.16-G2-V5 — Contrat pairwise indépendant

## Séparation des scores absolus

Le pairwise V5 ne reçoit et ne retourne aucun score absolu. A et B sont évalués simultanément selon une rubrique unique. Le contrat ne compare donc jamais deux résultats issus de calls indépendants.

## Entrée

Une `V5PairwiseObservation` contient :

- un `comparison_id` opaque ;
- scénario et contraintes ;
- la rubrique complète du seul critère évalué ;
- `candidate_a` et `candidate_b`, chacun avec ID opaque et projection bornée.

Les IDs de rôle, modèles et providers sont absents. L'ordre A/B est une propriété du paquet de comparaison, pas une indication de préférence.

## Sortie

| Champ | Contrat |
|---|---|
| `differences` | 1 à 8 différences observables listées avant la décision |
| `decision` | `A_BETTER`, `B_BETTER` ou `TIE` |
| `confidence` | `LOW`, `MEDIUM`, `HIGH` |
| `rationale` | justification courte et bornée |

Chaque différence contient :

- locator A ;
- locator B ;
- observation ;
- significance `MATERIAL`, `NON_MATERIAL` ou `OUT_OF_SCOPE` ;
- candidat favorisé `A`, `B` ou `NEITHER`.

## Règles de décision

- `A_BETTER` exige au moins une différence `MATERIAL` favorisant A.
- `B_BETTER` exige au moins une différence `MATERIAL` favorisant B.
- `TIE` est rejeté dès qu'une différence est `MATERIAL`, même si elle est mal étiquetée `NEITHER`.
- Deux avantages matériels contradictoires A et B sont rejetés comme conflit ; ils ne sont pas transformés en tie.
- Une différence `OUT_OF_SCOPE` est documentée mais ignorée pour la préférence.
- Une nuance `NON_MATERIAL` autorise un tie.

Ces invariants rendent le tie plus strict que V4 : une égalité de scores n'existe plus dans la décision.

## Fixtures

Les quatre classes sont instanciées pour chacun des 16 critères :

| Classe | Signal contrôlé | Décision attendue | Nombre |
|---|---|---|---:|
| A clairement meilleur | différence matérielle favorisant A | `A_BETTER` | 16 |
| B clairement meilleur | différence matérielle favorisant B | `B_BETTER` | 16 |
| Quasi-identiques | différence non matérielle | `TIE` | 16 |
| Différence hors critère | différence hors scope, même si elle favorise A | `TIE` | 16 |

Résultat : `64/64` décisions correctes, `32` ties attendus, `0` faux tie.

## Cas rejetés explicitement

- tie avec différence matérielle ;
- gagnant sans evidence matérielle correspondante ;
- avantages matériels contradictoires ;
- clé supplémentaire ;
- différence absente ;
- enum ou texte hors contrat.

## Statut

Le pairwise V5 est démontré sur différences contrôlées offline. Il n'est relié à aucun transport et ne constitue pas une autorisation de scoring live.
