# Phase 12.17.4 — Remédiation des tests de hash

`tests/support/historical_hash_freeze.py` centralise la vérification. Il lit le
freeze B01 lorsqu'il est disponible, exige `immutable = true`, vérifie le hash
courant et, pour les drifts connus, conserve la référence historique, l'origine
et `retroactive_repair = FORBIDDEN`.

Pour les chemins absents du JSON B01, le helper calcule la vérité depuis le blob
du commit propriétaire approuvé `6d0d663...` avec `git show`. Ce fallback rend
le test reproductible dans un checkout ne contenant pas les artefacts B01 non
suivis, sans substituer un nouveau littéral de hash.

Six tests ont remplacé leurs dictionnaires locaux obsolètes par ce helper.
`catalog.py`, `anchor_corpus_v3.py`, les 40 entrées B01 et leurs manifests sont
inchangés.

```text
HASH_FAILURES_BEFORE = 6
HASH_FAILURES_AFTER = 0
HASH_TARGETS = 6/6 PASS
HISTORICAL_SOURCE_FILES_MODIFIED = 0
```
