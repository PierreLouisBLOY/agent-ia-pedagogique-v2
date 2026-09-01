# Phase 12.16-G2-V5 — Contrat Scorer evidence-first

## Localisation et autorité

Le contrat est implémenté dans `tests/calibration/pedagogical/scorer_contract_v5.py`. Il appartient uniquement au harness de calibration offline. Il ne modifie ni `evaluation_harness`, ni les adaptateurs runtime, ni `tests/providers/anthropic`, ni les routes fournisseur.

## Entrée

Une `V5ScorerObservation` contient :

- `contract_version` ;
- un `observation_id` opaque ;
- le scénario, le niveau, la nature de tâche, les contraintes et sections attendues ;
- une rubrique V5 complète ;
- la projection candidate bornée à 2 500 caractères.

La rubrique contient :

- `criterion_ref` ;
- `measured_dimension` ;
- `not_measured` ;
- quatre `observable_checks` identifiés ;
- cinq `level_descriptors` ;
- la version d'échelle.

Les tiers Strong/Mixed/Weak, le provider, le modèle producteur et le score attendu ne sont jamais sérialisés.

## Instructions

Les instructions imposent l'ordre logique suivant :

1. examiner uniquement le critère fourni ;
2. lister les preuves observables des contrôles satisfaits ;
3. lister les contrôles manquants ou contradictoires ;
4. sélectionner le niveau 0–4 impliqué par ces preuves ;
5. donner confidence et rationale courte ;
6. ignorer les dimensions déclarées `not_measured` ;
7. ne prendre aucune décision runtime, release ou gate.

Le texte candidat reste explicitement de la donnée non fiable et ne peut donner d'instruction au juge.

## Sortie stricte

| Champ | Contrat |
|---|---|
| `status` | `SCORED` ou `INCONCLUSIVE` |
| `evidence` | 0 à 8 objets `check_id`, `locator`, `observation` |
| `defects` | 0 à 8 objets avec sévérité `MINOR`, `MAJOR` ou `CONTRADICTION` |
| `score_level` | entier 0–4, ou `null` si inconclusif |
| `confidence` | `LOW`, `MEDIUM`, `HIGH` |
| `rationale` | texte court, non vide, maximum 240 caractères |

Le schéma applique `additionalProperties = false` à chaque niveau.

## Invariants parser

- Chaque evidence doit référencer un contrôle de la rubrique.
- Un contrôle ne peut apparaître deux fois dans les evidence.
- Chaque contrôle non étayé doit être couvert par un défaut.
- Sans contradiction, `score_level` est exactement le nombre de contrôles étayés.
- Toute sévérité `CONTRADICTION` force le niveau 0.
- Un score incohérent avec les evidence est rejeté.
- `INCONCLUSIVE` exige `score_level = null` et `confidence = LOW`.
- Les identifiants, locators, observations et rationales sont bornés.

La normalisation éventuelle est exacte : `normalized_score = score_level / 4`, sous forme de `Fraction`. Aucun flottant ni arrondi ne participe au contrat.

## Evidence-first démontré

Le schéma expose ses propriétés dans l'ordre `status`, `evidence`, `defects`, `score_level`, `confidence`, `rationale`. L'ordre JSON n'est pas une autorité sémantique ; l'invariant fort est que le parser recalcule le niveau depuis les preuves et défauts avant d'accepter le score déclaré.

## Inconclusive et fail-closed

`INCONCLUSIVE` reste disponible quand les données bornées ne permettent pas l'évaluation contrôle par contrôle. Il n'est pas converti en zéro. Le module n'offre aucun transport. `assert_v5_live_execution_forbidden()` lève toujours `LIVE_EXECUTION_FORBIDDEN`, et la constante live reste fausse.

## Empreinte logique

Le hash canonique couvre :

- instructions Scorer ;
- schéma de sortie Scorer ;
- instructions pairwise ;
- schéma pairwise ;
- les 16 rubriques sérialisées.

`V5_CONTRACT_SHA256 = a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`
