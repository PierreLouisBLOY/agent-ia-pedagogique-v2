# ADR-P12-059 — Stratégie de sélection providers et modèles

## Statut

Accepté pour la Phase 12.16-C, faits vérifiés au 2026-08-28.

## Contexte

La fondation provider-neutral de 12.16-B décrit des profils et routes sans
sélectionner de fournisseur. D/E ont besoin de candidats explicites pour
Generation, Correction, Review et EvaluationScoring, mais aucune calibration
sur le corpus pédagogique n'a encore été exécutée. Le scorer doit limiter les
biais de self-judge sans multiplier inutilement les familles d'adaptateurs.

## Décision

1. Generation utilise comme candidats `gpt-5.6-terra` primary et
   `gpt-5.6-sol` fallback.
2. Correction utilise `gpt-5.6-sol` primary et `gpt-5.6-terra` fallback dans un
   profil distinct, tout en conservant `GenerationPort/CAP-G03`.
3. Review utilise `gpt-5.6-sol` primary et `gpt-5.6-terra` fallback dans des
   profils propres à Review.
4. EvaluationScoring utilise `claude-sonnet-5` primary afin d'obtenir une
   indépendance cross-provider. `gpt-5.6-sol` est seulement un fallback dégradé
   dont les résultats doivent être identifiés et séparés.
5. L'implémentation initiale est `MULTI_PROVIDER_FROM_START`, bornée à OpenAI
   et Anthropic. Google Gemini et Mistral ne sont pas implémentés en D/E.
6. Google Gemini Developer API est écarté du chemin initial tant que la
   compatibilité avec les conditions d'âge et le public réel n'est pas établie.
7. Mistral Medium 3.5 reste l'alternative provider indépendante avec option
   d'inférence UE. Mistral Small 4 reste une baseline open-weight distincte,
   sans installation ni promesse de coût nul.
8. Les profils utilisent un ID de release explicite ou officiellement pinned.
   Les aliases mobiles `gpt-5.6`, `gemini-flash-latest`, `-latest` et `-major`
   ne sont pas retenus pour le routage production.
9. La sélection est un ensemble de candidats de calibration, pas une preuve de
   qualité pédagogique. G/H doivent mesurer qualité française/STMG/BTS,
   conformité schema, répétabilité, biais, tokens, latence et coût avant
   promotion.
10. Les facts provider sont revalidés avant D au-delà de 30 jours, avant K1 si
    prix ou lifecycle ont changé, et immédiatement lors d'une notification de
    dépréciation ou modification de conditions.
11. Le transport et toute dépendance SDK/HTTP sont décidés dans D/E après revue
    explicite. C n'installe rien et ne modifie aucune frontière B.
12. Les embeddings restent différés à 12.16-F et ne deviennent pas un workload
    ou une route en C.

## Conséquences

Deux adaptateurs outbound au maximum sont attendus sur l'horizon D/E : OpenAI
pour Generation, Correction et Review, Anthropic pour EvaluationScoring. Cette
complexité supplémentaire est acceptée pour la séparation du judge. La
configuration provider-neutral, les ports, Recovery, l'observabilité et le
harness restent inchangés en C.

Un fallback du scorer vers OpenAI préserve la disponibilité technique mais ne
préserve pas l'indépendance ; aucune comparaison de scores ne peut ignorer ce
changement de provenance. Toute promotion de Luna, Gemini, Mistral ou d'un
modèle ultérieur exige une mise à jour sourcée de la matrice et les calibrations
applicables.

Les prix, quotas et limites de contexte consignés dans la baseline C sont des
faits volatils datés, pas des invariants architecturaux de cet ADR.
