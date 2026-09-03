# Phase 12.17.4 — Analyse des causes racines

La reproduction avant modification donne exactement `6 + 1` : six assertions
de hashes figées avant la remédiation de typing 12.17.2A, puis une gate réelle
qui ne consultait que l'ancien nom de variable du seed.

Les contenus historiques étaient corrects. Les tests comparaient néanmoins
`catalog.py` à `53da2068...` au lieu du courant approuvé `32339ade...`, et
`anchor_corpus_v3.py` à `cf904573...` au lieu de `95e6a253...`. Aucun ancien
hash n'a été restauré.

Écart du bundle B01 : `03_HISTORICAL_HASH_FREEZE.json` contient bien 40
entrées, mais ni `catalog.py` ni `anchor_corpus_v3.py`. Les affirmations du
bundle de remediation selon lesquelles ces deux chemins sont couverts par le
freeze ne correspondent donc pas au fichier machine-readable. La résolution
fail-closed utilise B01 pour tout chemin présent et le commit propriétaire
approuvé `6d0d66380757d7502fd967cd0246c5b6ff91d5f8` comme preuve byte-exacte
pour les chemins omis. B01 n'est ni réécrit ni complété rétroactivement.

La gate seed utilisait `PEDAGOGICAL_CANONICAL_SEED_PATH` directement alors que
B07/B08 ont introduit le loader de configuration et l'alias canonique
`PROJET_V2_CANONICAL_DB`. Son guard compagnon exigeait aussi le symbole legacy ;
il a été aligné sur le contrat du loader sans introduire de skip.
