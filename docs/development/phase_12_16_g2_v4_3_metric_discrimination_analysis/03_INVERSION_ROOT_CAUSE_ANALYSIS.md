# Phase 12.16-G2-V4.3 — Analyse des cinq inversions

## Limite de preuve commune

Les cinq inversions sont des relations `Mixed < Weak`. Les sorties brutes correspondantes ne contiennent aucune justification : le schéma impose exactement `status`, `score_numerator` et `score_denominator`, avec `additionalProperties = false`. Les champs « justification » ci-dessous distinguent donc :

- `FAIT` : contenu, identité, score ou code observé localement ;
- `INFERENCE` : mécanisme causal plausible, non déclaré par le Scorer.

Les réponses 0/1 ont toutes le SHA-256 `3d2e4cb76ed3d5f10eabd369f19933404a5900df95674eaa2bc96c67b815ba3d`; les réponses 1/1 ont toutes le SHA-256 `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b`; la réponse 1/2 a le SHA-256 `a16287401cc87863d23dc170b76cf2983ccae1909374d2a3b6af8226642f6053`. Ces hashes identiques reflètent des payloads de score identiques, pas une collision d'identité d'appel.

## 1. SCN-01 — clarté

- Critère : `scn-01.quality.clarity`.
- Triplet : `1, 0, 1`.
- Mixed : `cal.v4.scn-01.a865078efdc4`, appel `cal.score.anchor.scn-01.mixed.clarity.r1`, score 0.
- Weak : `cal.v4.scn-01.e20186484ff6`, appel `cal.score.anchor.scn-01.weak.clarity.r1`, score 1.
- Différence réelle : Mixed est plus complet mais expose explicitement l'absence de hiérarchie, de champ de niveau et de règle d'usage du statut. Weak est plus court et lisible, mais omet notion, niveau, statut et vérification.
- Justification scorer : `NON_ENREGISTREE_PAR_LE_CONTRAT`.
- Cause probable, inférence : le mot « clarté » n'est pas défini opérationnellement. Le Scorer a pu valoriser la brièveté de Weak et sanctionner les formulations auto-dépréciatives de Mixed, sans relier la clarté à l'exploitabilité pédagogique attendue.
- Classification : `CRITERE + PROMPT + AMBIGUITE`, avec contribution possible de la construction de l'anchor.

## 2. SCN-04 — fidélité

- Critère : `scn-04.quality.fidelity`.
- Triplet : `1, 0, 1`.
- Mixed : `cal.v4.scn-04.e6fe3db01fed`, appel `cal.score.anchor.scn-04.mixed.fidelity.r1`, score 0.
- Weak : `cal.v4.scn-04.04da74ca536e`, appel `cal.score.anchor.scn-04.weak.fidelity.r1`, score 1.
- Différence réelle : Mixed restitue le TTC exact de 300 mais signale l'absence de TVA intermédiaire et de contrôle. Weak reste générique, n'explicite ni formule ni calcul séparé, et ne fournit aucun résultat numérique contrôlable.
- Justification scorer : `NON_ENREGISTREE_PAR_LE_CONTRAT`.
- Cause probable, inférence : « fidélité » n'est accompagnée d'aucune définition ni référence détaillée. Weak énonce peu de faits réfutables, tandis que Mixed rend son défaut explicite ; le signal lexical de défaut peut dominer la fidélité factuelle.
- Classification : `CRITERE + PROMPT + ANCHOR/AMBIGUITE`.

## 3. SCN-06 — clarté de l'évaluation

- Critère : `scn-06.quality.assessment-clarity`.
- Triplet : `1, 0, 1`.
- Mixed : `cal.v4.scn-06.a74ef2a40cb1`, appel `cal.score.anchor.scn-06.mixed.assessment-clarity.r1`, score 0.
- Weak : `cal.v4.scn-06.74ba8e9a9af4`, appel `cal.score.anchor.scn-06.weak.assessment-clarity.r1`, score 1.
- Différence réelle : Mixed fournit des données numériques et deux questions résolubles, mais déclare qu'aucune forme de calcul, unité ou justification n'est attendue. Weak formule des instructions directes et un découpage par question, mais ne fournit ni montant ni taux concrets.
- Justification scorer : `NON_ENREGISTREE_PAR_LE_CONTRAT`.
- Cause probable, inférence : le Scorer peut assimiler une consigne courte et impérative à une consigne claire, sans tester la résolubilité à partir des données. Les formulations « sans » de Mixed exposent au contraire le défaut contrôlé.
- Classification : `CRITERE + PROMPT + ANCHOR/AMBIGUITE`.

## 4. SCN-06 — cohérence du barème

- Critère : `scn-06.quality.marking-scheme-coherence`.
- Triplet : `1, 0, 1/2`.
- Mixed : `cal.v4.scn-06.a74ef2a40cb1`, appel `cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1`, score 0.
- Weak : `cal.v4.scn-06.74ba8e9a9af4`, appel `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1`, score 1/2.
- Différence réelle : Mixed attribue six points globalement sans répartition. Weak attribue trois points à chaque question, mais sans décomposition fiable par formule, application, résultat et unité.
- Justification scorer : `NON_ENREGISTREE_PAR_LE_CONTRAT`.
- Cause probable, inférence : cette inversion est la plus explicable par le contenu. Weak possède effectivement un minimum de structure de barème absent de Mixed. Elle illustre aussi un désalignement entre l'ordre trinaire attendu par la métrique et la politique V4, où les deux tiers négatifs sont des contrôles non livrables et leur ordre est diagnostic seulement.
- Classification : `ANCHOR + TARGET_METRIC_SEMANTICS`; aucune preuve de défaut parser.

## 5. SCN-08 — qualité des distracteurs

- Critère : `scn-08.quality.distractor-quality`.
- Triplet : `1, 0, 1`.
- Mixed : `cal.v4.scn-08.b533a212bb9c`, appel `cal.score.anchor.scn-08.mixed.distractor-quality.r1`, score 0.
- Weak : `cal.v4.scn-08.3aa05440e303`, appel `cal.score.anchor.scn-08.weak.distractor-quality.r1`, score 1.
- Différence réelle : les deux candidats ont la même question, la même bonne réponse et les mêmes distracteurs B/C. Seul D varie entre « chiffre d'affaires diminué des charges » et « charges diminuées du chiffre d'affaires ». Le feedback est presque équivalent et déclare les distracteurs incorrects sans diagnostic individualisé.
- Justification scorer : `NON_ENREGISTREE_PAR_LE_CONTRAT`.
- Cause probable, inférence : les anchors Mixed et Weak sont trop proches pour soutenir un ordre stable, et le contrat ne définit pas ce qui rend un distracteur plausible ou diagnostique. Le saut 0 vers 1 malgré cette proximité montre une instabilité sémantique que le payload sans rationale empêche d'expliquer.
- Classification : `ANCHOR + CRITERE + PROMPT + AMBIGUITE`.

## Causes exclues ou non étayées

- Parser : aucune erreur observée ; les payloads sont valides et les 48 scores sont conclusifs.
- Arrondi : aucun ; `NormalizedScore` et `Fraction` utilisent des rationnels exacts.
- Agrégation : les inversions existent déjà dans les scores unitaires avant agrégation.
- Collision d'identité : les call IDs, anchor IDs et criterion refs sont distincts et correctement reliés. La déduplication de stockage par hash du payload n'altère pas les identités ledger.
- Défaillance transport : aucune dans les observations analysées.

## Conclusion

Quatre inversions sur cinq sont fortement compatibles avec un manque de définition des critères et un effet de signal lexical des défauts explicités. L'inversion de cohérence du barème SCN-06 est en outre cohérente avec le contenu réellement plus structuré de Weak et révèle que `Mixed > Weak` est une cible métrique inadéquate pour la sémantique V4 non bloquante. Faute de rationale enregistré, la causalité observationnelle détaillée reste de confiance moyenne.
