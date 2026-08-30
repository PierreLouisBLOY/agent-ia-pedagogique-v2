# Phase 12.16-G2 — Matrice de différenciation du corpus v2

- Version : `12.16-g1-v2`.
- Checksum : `4fe17f4286eb1a713a3d41a95b99260ef470ba32cadf33c2267dfc4dbaada427`.
- Portée : 8 scénarios, 16 critères, 24 anchors, 48 couples anchor/critère.
- Toutes les sections requises sont préservées dans les trois niveaux.

## Règles de conception

- STRONG vise exactitude, complétude, clarté, adaptation et exploitabilité immédiate.
- MIXED reste utilisable avec une insuffisance explicite et bornée sur chaque critère.
- WEAK_BUT_STRUCTURALLY_VALID reste intelligible et exact, mais présente deux déficits pédagogiques perceptibles.
- La progression visée est `STRONG > MIXED > WEAK_BUT_STRUCTURALLY_VALID` pour les deux critères.
- La différence ne repose jamais sur une section manquante, une erreur absurde ou la seule longueur.

## Matrice des défauts contrôlés

| Scénario | Critère | Intention strong | Défaut mixed | Défaut weak | Sections préservées |
|---|---|---|---|---|:---:|
| SCN-01 | `scn-01.quality.clarity` | hiérarchie de classement et champs explicités sans ambiguïté | classement utilisable mais ordre des champs seulement suggéré | catégorie générale sans procédure de classement explicite | OUI |
| SCN-01 | `scn-01.quality.organization-utility` | retrouvabilité et vérification rendues immédiatement opérationnelles | retrouvabilité assurée mais contrôle ultérieur peu guidé | rangement minimal sans règle de vérification ou de réutilisation | OUI |
| SCN-02 | `scn-02.quality.relevance` | ciblage conjoint de la notion, du niveau et de la tâche de calcul | ciblage du thème et du niveau avec précision méthodologique réduite | mot-clé large sans filtre de niveau ni de méthode | OUI |
| SCN-02 | `scn-02.quality.coverage` | notion, méthode, exemple et règles d'exclusion tous couverts | notion et méthode couvertes mais exemple laissé facultatif | mentions thématiques seules, sans méthode ni exemple exigés | OUI |
| SCN-03 | `scn-03.quality.clarity` | définitions contrastées, exemple interprété et synthèse articulée | définitions correctes mais contraste et synthèse moins développés | formulations générales qui nomment les finalités sans les expliquer | OUI |
| SCN-03 | `scn-03.quality.level-adaptation` | vocabulaire et raisonnement explicitement adaptés à Première STMG | vocabulaire accessible mais guidage disciplinaire limité | exemple générique et repères disciplinaires insuffisants | OUI |
| SCN-04 | `scn-04.quality.fidelity` | enchaînement HT, taux, taxe et TTC intégralement préservé | relation de calcul exacte mais décomposition intermédiaire abrégée | règle exacte mais trop générique pour restituer la note en détail | OUI |
| SCN-04 | `scn-04.quality.level-adaptation` | méthode, unités et vérification explicitables au niveau BTS CG | exemple exploitable mais sans contrôle comptable guidé | application abstraite sans repère de présentation comptable | OUI |
| SCN-05 | `scn-05.quality.difficulty-appropriateness` | deux calculs, comparaison et justification graduent la difficulté | deux calculs directs avec justification courte | choix demandé à partir d'un calcul peu guidé et faiblement approfondi | OUI |
| SCN-05 | `scn-05.quality.instruction-clarity` | données, formule attendue, étapes et justification sont explicites | données et résultat attendus sont clairs mais les étapes sont peu guidées | consigne générale qui ne précise ni méthode ni forme de justification | OUI |
| SCN-06 | `scn-06.quality.assessment-clarity` | consignes, données, unités et attendus de calcul sont explicites | calculs identifiés mais présentation attendue seulement partielle | questions compréhensibles avec exigences de réponse minimales | OUI |
| SCN-06 | `scn-06.quality.marking-scheme-coherence` | barème analytique aligné sur formule, application, résultat et unité | barème partiellement analytique qui regroupe certaines étapes | barème global aligné sur les questions mais peu discriminant | OUI |
| SCN-07 | `scn-07.quality.correction-quality` | confusion diagnostiquée et relation produits moins charges explicitée | correction exacte mais diagnostic et justification abrégés | rectification superficielle qui rappelle seulement le rôle des charges | OUI |
| SCN-07 | `scn-07.quality.remediation-clarity` | activité bornée avec classement, recalcul et explication finale | nouveau calcul demandé avec guidage général | invitation à revoir la notion sans tâche ni critère de réussite | OUI |
| SCN-08 | `scn-08.quality.distractor-quality` | trois erreurs plausibles, distinctes et liées à des confusions identifiables | distracteurs distincts mais plausibilité inégale | distracteurs formellement distincts dont deux sont peu convaincants | OUI |
| SCN-08 | `scn-08.quality.feedback-quality` | réponse correcte et erreur de chaque distracteur expliquées | bonne réponse expliquée avec un seul contraste détaillé | confirmation brève de la réponse sans analyse des distracteurs | OUI |

## Remédiation par scénario

- SCN-01 : structure mixed réparée; hiérarchie, retrouvabilité et vérification graduées.
- SCN-02 : ciblage et couverture séparés; faible sans niveau, méthode ni exemple requis.
- SCN-03 : distinction forte/intermédiaire conservée; intermédiaire/faible rendue visible.
- SCN-04 : fidélité du calcul et adaptation BTS CG différenciées sans inexactitude.
- SCN-05 : difficulté et guidage gradués par données, étapes et justification.
- SCN-06 : barème analytique, partiellement analytique puis global mais aligné.
- SCN-07 : correction et remédiation graduées d'opérationnelles à superficielles.
- SCN-08 : plausibilité des distracteurs et profondeur du feedback graduées.

## Gates statiques

- `v2.anchors-distinct`.
- `v2.tier-sections-distinct`.
- `v2.non-trivial-textual-distance`.
- `v2.controlled-defect-declared`.
- `v2.not-cosmetic-only`.
- `v2.required-sections-exact`.
- `v2.structurally-valid`.
- `v2.weak-not-more-detailed-than-strong`.
- `v2.safe-synthetic-content`.

Ces gates détectent les défauts de conception évidents mais ne remplacent pas la prévalidation humaine aveugle.
