# Phase 12.16-G2-V4.3 — Cause racine et recommandation V5

## Cause racine

`PRIMARY_ROOT_CAUSE = SCORER_CONTRACT_UNDERSPECIFIED_FOR_PEDAGOGICAL_DISCRIMINATION`

Le Scorer reçoit un identifiant de critère sans définition opérationnelle, un candidat isolé, des contraintes générales et un schéma de score sans barème sémantique ni rationale. Cette combinaison ne lui donne pas les informations nécessaires pour distinguer de façon reproductible des niveaux proches ou des défauts contrôlés. La saturation `47/48` aux extrêmes est la manifestation mesurée de ce contrat sous-spécifié.

`SECONDARY_ROOT_CAUSES = [POST_HOC_PAIRWISE_FROM_INDEPENDENT_SATURATED_SCORES, TRINARY_METRIC_VS_V4_PRIMARY_GATE_MISMATCH, NEGATIVE_CONTROL_PROXIMITY_AND_DEFECT_LEXICAL_LEAKAGE, RATIONALE_AUDITABILITY_GAP]`

- `POST_HOC_PAIRWISE_FROM_INDEPENDENT_SATURATED_SCORES` : le « pairwise » compare deux scores absolus après coup ; il n'expose jamais les deux outputs ensemble au juge.
- `TRINARY_METRIC_VS_V4_PRIMARY_GATE_MISMATCH` : `Strong > Mixed > Weak` est plus strict que la gate V4 `Strong > each negative`; Mixed/Weak est officiellement secondaire et non bloquant.
- `NEGATIVE_CONTROL_PROXIMITY_AND_DEFECT_LEXICAL_LEAKAGE` : certains négatifs sont presque équivalents, notamment SCN-08, tandis que plusieurs Mixed nomment explicitement leur propre défaut avec « sans » ou « aucune ».
- `RATIONALE_AUDITABILITY_GAP` : le schéma interdit toute justification ou preuve localisée, empêchant l'explication directe des décisions.

`CONFIDENCE = HIGH`

La confiance est haute pour la cause contractuelle, le pairwise post-hoc, la saturation et le désalignement de métrique, tous directement observables dans le code et les artefacts. Elle est moyenne pour l'explication psycholinguistique de chaque inversion, car aucune rationale provider n'a été enregistrée.

## Ce qui n'est pas la cause racine

- aucun échec transport dans les scores étudiés ;
- aucun retry ou rerun ;
- aucun arrondi flottant ;
- aucune erreur parser observée ;
- aucune collision de source ou de rôle ;
- aucune agrégation moyenne avant la décision de tie.

## Recommandation V5 minimale

### 1. Définir le critère dans l'observation

Ajouter un descripteur fermé et versionné par critère :

- définition opérationnelle ;
- éléments obligatoires et défauts discriminants ;
- evidence locators autorisés ;
- cas `INCONCLUSIVE` ;
- relation explicite avec les contraintes de référence.

Le descripteur reste provider-neutral et appartient au contrat d'évaluation, pas au transport Anthropic.

### 2. Définir l'échelle

Remplacer l'échelle implicite par des niveaux fermés et décrits, par exemple cinq points normalisés `0`, `1/4`, `1/2`, `3/4`, `1`, chacun avec un sens pédagogique. Le choix exact doit être versionné et prévalidé humainement ; le but n'est pas d'augmenter arbitrairement la granularité, mais de rendre les transitions interprétables.

Ajouter au schéma de sortie :

- un `rationale_code` fermé ;
- un ou plusieurs `evidence_locator` bornés ;
- éventuellement un `confidence` fermé.

Éviter une justification libre longue. Une preuve courte et structurée suffit à l'audit et limite les transferts.

### 3. Rendre le pairwise réellement comparatif

Pour les outputs primary/fallback, transmettre dans un même call deux candidats aveugles A/B en ordre déterministement permuté. Retourner `A`, `B`, `TIE` ou `INCONCLUSIVE`, plus rationale code et evidence locators. Autoriser `TIE` seulement si aucune différence matérielle n'est trouvée selon le critère défini.

Si des scores absolus sont conservés, leur égalité ne doit plus constituer à elle seule un verdict pairwise : elle doit déclencher une adjudication comparative distincte.

### 4. Aligner les métriques avec la politique V4

Séparer explicitement :

- primaire : `Strong > Mixed` et `Strong > Weak` pour chaque critère ;
- secondaire : relation Mixed/Weak, uniquement diagnostique ;
- pairwise outputs : préférence directe A/B/TIE, séparée des scores absolus.

Conserver la monotonie trinaire dans le rapport si utile, mais ne pas la présenter comme la gate propriétaire primaire.

### 5. Réviser seulement les anchors ambigus

Ne pas réécrire silencieusement le corpus. Soumettre à prévalidation humaine ciblée :

- SCN-08 Mixed/Weak distractor-quality, trop proches ;
- SCN-04 Mixed/Weak fidelity, où l'absence d'assertions vérifiables avantage potentiellement Weak ;
- SCN-01 et SCN-06, où les formulations auto-dépréciatives peuvent révéler le tier.

Chaque modification doit être versionnée V5 et conserver l'aveuglement tier/provider/model.

## Tests offline V5 proposés

1. Le contrat sérialisé contient définition du critère, niveaux d'échelle et règles `INCONCLUSIVE`.
2. Le schéma rejette score hors échelle, rationale code inconnu, evidence locator absent et clés supplémentaires.
3. Le parser préserve exactement les rationnels et les preuves structurées.
4. Aucun tier, score attendu, provider ou modèle producteur ne fuit dans les observations.
5. La permutation A/B est déterministe, vérifiable et sans biais de rôle.
6. Le tie handler exige l'égalité comparative explicite, pas seulement deux scores absolus égaux.
7. Les identités scénario/critère/source/rôle restent bijectives.
8. Les métriques primaire et secondaire sont calculées séparément.
9. Les fixtures contractuelles couvrent une différence matérielle, une équivalence réelle et un cas inconclusif.
10. Un snapshot offline du paquet V5 et de son manifest est reproductible byte-for-byte.

## Critères d'entrée avant tout nouveau live

Ces critères sont des gardes de préparation, pas un seuil de release :

- contrat V5 et corpus V5 versionnés et hashés ;
- revue humaine aveugle confirmant `Strong > each negative` sur les 16 critères ;
- cas Mixed/Weak documentés comme diagnostic seulement ;
- six cas pairwise de référence avec verdict humain et différences substantielles documentées ;
- tous les tests offline ci-dessus PASS ;
- analyse de transfert, matrice d'appels, pricing et plafond distinctement approuvés ;
- autorisation live explicite nouvelle, sans réutiliser l'autorisation V4.2 consommée.

## Décision

Une V5 minimale est recommandée. Elle doit modifier le contrat de scoring et les métriques avant de modifier le provider ou de lancer un nouveau live. Aucun seuil de release n'est adopté et aucune exécution live n'est autorisée par cette recommandation.
