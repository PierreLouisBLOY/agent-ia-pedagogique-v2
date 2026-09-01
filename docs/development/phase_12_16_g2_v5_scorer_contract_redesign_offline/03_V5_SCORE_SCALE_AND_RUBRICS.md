# Phase 12.16-G2-V5 — Échelle et rubriques

## Échelle ordinale 0–4

| Niveau | Descripteur observable | Normalisation exacte |
|---:|---|---:|
| 0 | Aucun contrôle satisfait, contradiction majeure ou résultat inutilisable | 0 |
| 1 | Un contrôle satisfait; dimension très insuffisante | 1/4 |
| 2 | Deux contrôles satisfaits; dimension partiellement satisfaisante | 1/2 |
| 3 | Trois contrôles satisfaits; dimension satisfaisante avec défaut borné | 3/4 |
| 4 | Quatre contrôles satisfaits; dimension très satisfaisante et exploitable | 1 |

Les niveaux intermédiaires ne dépendent pas d'une appréciation libre : ils correspondent à un nombre explicite de contrôles étayés. Une contradiction matérielle est la seule règle d'override et force 0.

## Rubriques par critère

Chaque ligne résume les quatre contrôles. Leur texte intégral et leurs identifiants versionnés résident dans `scorer_contract_v5.py`.

| Critère | Mesure | Ne mesure pas | Contrôles 1–4 |
|---|---|---|---|
| `scn-01.quality.clarity` | Hiérarchie et procédure explicites | Valeur de recherche/réutilisation | hiérarchie thème/notion; champs distincts; procédure exécutable; absence d'ambiguïté |
| `scn-01.quality.organization-utility` | Recherche, vérification et réutilisation | Lisibilité rédactionnelle seule | recherche thème/notion; titre/niveau visibles; statut de vérification; préparation de la réutilisation |
| `scn-02.quality.relevance` | Ciblage exact de la recherche | Exhaustivité après ciblage | thème; niveau; méthode de calcul; exclusions hors cible |
| `scn-02.quality.coverage` | Couverture utile | Pertinence thématique seule | notion; méthode; exemple; règles d'exclusion |
| `scn-03.quality.clarity` | Explication contrastée des finalités | Adaptation au niveau scolaire | définition économique; définition sociale; exemple interprété; synthèse articulée |
| `scn-03.quality.level-adaptation` | Accessibilité Première STMG | Exhaustivité conceptuelle seule | vocabulaire; contexte disciplinaire; méthode guidée; absence de jargon bloquant |
| `scn-04.quality.fidelity` | Préservation de la chaîne HT/TVA/TTC | Facilité pédagogique seule | HT; taux/formule; TVA calculée; TTC vérifié |
| `scn-04.quality.level-adaptation` | Méthode présentable au BTS CG | Exactitude factuelle seule | étapes; unités; exemple complet; contrôle final |
| `scn-05.quality.difficulty-appropriateness` | Progression de difficulté | Formulation des consignes | deux calculs; formule; comparaison; justification |
| `scn-05.quality.instruction-clarity` | Consignes opératoires | Difficulté de l'exercice | données; formule; étapes; justification attendue |
| `scn-06.quality.assessment-clarity` | Attendus explicites de l'évaluation | Répartition des points | forme de réponse; données; unités; calcul/vérification |
| `scn-06.quality.marking-scheme-coherence` | Alignement questions/barème | Lisibilité des questions seule | points par question; formule; application; résultat/unité/vérification |
| `scn-07.quality.correction-quality` | Diagnostic et correction | Activité de remédiation | confusion identifiée; cause; formule; lien à la source |
| `scn-07.quality.remediation-clarity` | Activité corrective bornée | Exactitude de la correction seule | tâche bornée; classement; recalcul; explication/critère de réussite |
| `scn-08.quality.distractor-quality` | Plausibilité diagnostique des options | Feedback après réponse | une réponse correcte; trois distracteurs; plausibilité; erreurs distinctes |
| `scn-08.quality.feedback-quality` | Explication de la réponse et des erreurs | Plausibilité des options seule | bonne réponse; chaque distracteur; lien au critère; feedback borné |

## Isolation des dimensions

Le champ `not_measured` est fourni au juge avec la rubrique. Une différence portant uniquement sur cette dimension ne peut produire ni evidence positive, ni préférence pairwise. Les deux critères de chaque scénario restent donc complémentaires sans être agrégés silencieusement.

## Couverture des niveaux

Pour chacun des 16 critères, le corpus synthétique instancie :

- un cas absent niveau 0 ;
- un cas contradictoire niveau 0 ;
- un cas Weak niveau 1 ;
- un cas Mixed niveau 2 ;
- un cas satisfaisant niveau 3 ;
- un cas Strong niveau 4.

Total : `96` fixtures. Les niveaux 1, 2 et 3 sont atteints `16` fois chacun.

## Anchors historiques

Les 24 anchors V4 ne sont pas modifiés. Le contrat construit 48 observations aveugles, une par couple anchor/critère. Le corpus conserve le hash :

`9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034`

Les 16 triplets ont des projections textuelles distinctes. Cette vérification prouve la compatibilité structurelle et le blinding, pas leur classement sémantique par un modèle réel. Aucun score provider n'est fabriqué offline.
