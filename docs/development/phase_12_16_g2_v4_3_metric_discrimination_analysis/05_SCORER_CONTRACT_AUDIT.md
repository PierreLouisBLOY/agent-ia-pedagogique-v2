# Phase 12.16-G2-V4.3 — Audit du contrat Scorer

## Résumé

Le transport, le parser, la normalisation et le tie handling sont déterministes et exacts. La faiblesse discriminante est en amont : le contrat donne au modèle un identifiant de critère, un candidat isolé et des contraintes générales, mais aucune définition opérationnelle, aucun barème interprétable, aucun exemple étalonné, aucun contexte comparatif et aucun champ de justification.

## Chaîne auditée

| Élément | Fichier | SHA-256 | Constat |
|---|---|---|---|
| Mapping/prompt | `tests/providers/anthropic/mapping.py` | `970da3e243b7241b858c5ad3d33a01bdb30815b753008a208790b0d9b2e9a633` | Prompt générique, schéma fermé à trois champs. |
| Scorer/parser | `tests/providers/anthropic/scorer.py` | `3be22f3a4ee19a3e2095f52f459b30d0b204a7e37437b2e5b33ab0ee03a76119` | Parser strict, rationnel exact, aucune rationale. |
| Contrats transport | `tests/providers/anthropic/contracts.py` | `668fa89013fe053201dd971060cd8a1036378f8f863085a8e80ac5baef4e90f8` | Modèle, thinking et télémétrie bornés. |
| Transport | `tests/providers/anthropic/transport.py` | `15ecf4b27ac8840dc503201864614a304917d3d43132b159da6a520044787b5b` | Sortie structurée, retries à zéro. |
| Projection observation | `tests/calibration/pedagogical/protocol.py` | `13c52073886016a564d36a5a942ce8c8bd21615530b222910375b713669a69e3` | Sept champs, critère transmis comme simple ref opaque. |
| Métriques | `tests/calibration/pedagogical/metrics.py` | `fd58c668eb32d259f40f05a374db5a952b1d11eaa72f767966888ed2825720a8` | Comparaisons exactes, adjacent-only pour l'ordre, post-hoc pour le pairwise. |
| Corpus V4 | `tests/calibration/pedagogical/anchor_corpus_v4.py` | `b0a86640502db4ab1d0b623e50faffa45178d9e93b0a24976df3312d460662be` | Tiers opaques au Scorer ; ordre Mixed/Weak secondaire selon la politique. |
| Review V4.2 | `tests/calibration/pedagogical/review_contract_v4_2.py` | `60cc9e407fe1010f089ee38a7ef06719e15fc4ad84e6f3c7c568fa66859aaba5` | Contrat OpenAI distinct ; ses findings ne servent pas de rubric au Scorer Anthropic. |

Les hashes sont des constats de l'état analysé, pas une nouvelle baseline.

## Prompt

Le system prompt demande de scorer « one bounded synthetic pedagogical calibration observation », d'utiliser `INCONCLUSIVE` si les données sont insuffisantes et de retourner le schéma exact. Il ne précise pas :

- le sens opérationnel de chaque critère ;
- les preuves positives et négatives attendues ;
- l'interprétation de 0, d'un score intermédiaire et de 1 ;
- la granularité autorisée ;
- la relation entre respect des sections, contraintes de référence et critère ;
- la manière de comparer des candidats ;
- la justification minimale à fournir.

Le garde-fou « do not infer a missing criterion » ne résout pas le problème : le champ `criterion` contient un identifiant, mais pas sa définition.

## Rubriques et critères

`EvaluationScoringCriterionSpec` contient une `criterion_ref`, une `scorer_ref`, des `observation_refs` et un poids. Il n'expose aucun descripteur sémantique. Les rubriques canoniques listent donc des refs comme `scn-06.quality.marking-scheme-coherence`, mais le Scorer doit deviner leur interprétation.

L'observation ajoute les contraintes de référence et les sections exigées, ce qui protège le périmètre mais ne définit pas les niveaux de qualité. Les labels tier et scores attendus sont correctement masqués ; cet aveuglement n'est pas en cause.

## Échelle

Le schéma accepte deux entiers non négatifs. `NormalizedScore` impose ensuite un rationnel exact dans `[0,1]`, sans limiter les dénominateurs. Aucune échelle sémantique n'est communiquée au Scorer. En pratique, les sorties observées n'utilisent que `0/1`, `1/2` et `1/1`, avec 47 extrêmes sur 48.

Conclusion : l'échelle technique est exacte mais l'échelle pédagogique est absente.

## Examples et anchors

Chaque call d'anchor transmet un seul candidat opaque. Aucun exemple scoré, descripteur de niveau, anchor de référence ou triplet comparatif n'est visible. Pour les selected outputs, primary et fallback sont également envoyés dans des calls séparés. Il n'existe donc aucun étalonnage intra-call.

## Parser et schéma de sortie

- Clés exigées exactement : `status`, `score_numerator`, `score_denominator`.
- `additionalProperties = false`.
- `INCONCLUSIVE` exige deux composantes nulles.
- `SCORED` exige deux entiers formant un `NormalizedScore` valide.
- Toute clé de rationale, evidence ou confidence serait rejetée.

Le parser est fail-closed et n'explique pas les inversions. En revanche, le schéma crée un déficit d'auditabilité : aucune cause individuelle ne peut être reconstruite depuis les sorties.

## Arrondis, normalisation et agrégation

- Arrondis : aucun.
- Normalisation : réduction exacte par PGCD.
- Ordre des anchors : comparaison par `Fraction` de deux paires adjacentes `S-M` et `M-W`.
- Monotonie stricte : les deux paires doivent être strictement décroissantes.
- Ties anchors : comptage exact des égalités adjacentes.
- Selected-output : comparaison directe de deux scores unitaires exacts après regroupement par scénario/critère/rôle.
- Qualité agrégée : la moyenne par modèle est informative ; elle ne décide pas les six ties.

Il n'existe aucune preuve d'un bug d'arrondi, de normalisation ou d'agrégation.

## Sémantique de gate

Le corpus V4 déclare :

- primary gate : Strong strictement préféré à chacun des deux négatifs ;
- secondary diagnostic : ordre Mixed/Weak non bloquant.

La métrique `strict_monotonicity_count` exige néanmoins `Strong > Mixed > Weak`. Elle mesure donc une cible plus forte que la gate primaire. Ce choix ne crée pas les scores, mais il transforme toute égalité ou inversion entre négatifs en échec de monotonie et explique en partie le `0/16`.

## Verdict d'audit

| Domaine | Verdict |
|---|---|
| Transport/retry | Conforme ; aucune influence observée sur la discrimination |
| Parser | Conforme et fail-closed, mais non auditable faute de rationale |
| Arrondi/normalisation | Conforme ; exact rationnel |
| Identités/agrégation | Conforme |
| Prompt/rubric | Insuffisant pour une discrimination pédagogique reproductible |
| Échelle | Non définie sémantiquement ; saturation extrême observée |
| Pairwise | Post-hoc, pas comparatif ; perd les nuances |
| Gate semantics | Monotonie trinaire plus stricte que la politique V4 primaire |
