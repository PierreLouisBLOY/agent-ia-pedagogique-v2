# Phase 12.17.4E-B03 — Mapping request/response

## Requête

La configuration résolue porte un code modèle opaque, `max_tokens`, le timeout,
le pricing et, si activé, le couple exact `thinking=adaptive` / `effort=low`.
`retry_count` doit être zéro et `retain_raw_response` doit être faux.

Une requête contient exactement un message user. Son JSON sépare :

- `calibration_call` : version, call ref, criterion ref, kind et références de
  projection ordonnées ;
- `pedagogical_projection` : objet JSON minimisé injecté pour cet appel.

Aucun expected result, tier livrable, décision owner ou seuil de release n'est
ajouté. Le schéma de sortie vient exclusivement de
`calibration_tooling.contracts.parser.active_output_schema`.

## Réponse et usage

La frontière client retourne seulement les blocs texte, un stop reason fermé,
les compteurs d'usage et le nombre de blocs thinking. Aucun contenu thinking
n'est accepté ou conservé dans les types actifs.

- `end_turn` et `stop_sequence` : complets si un seul bloc texte non vide ;
- `max_tokens` : incomplet, donc `RESPONSE_TRUNCATED` dans le parser B02 ;
- refusal, tool use, pause ou unknown : `RESPONSE_INVALID` ;
- zéro ou plusieurs blocs texte complets : `RESPONSE_INVALID`.

Le coût est calculé séparément sur les tokens input non cachés, cache creation,
cache read et output. Il est arrondi par excès au micro-dollar pour ne jamais
sous-compter face au budget B02.

Les champs `input_json`, contenu du message, schéma et blocs de sortie ont
`repr=False`. Le texte brut n'est transmis qu'éphémèrement au parser actif.
