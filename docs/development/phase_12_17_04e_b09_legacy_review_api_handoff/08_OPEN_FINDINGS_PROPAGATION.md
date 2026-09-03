# Phase 12.17.4E-B09 — Propagation des findings ouverts

```text
RESOURCE_ACTIVE_CANONICAL = UNKNOWN
CONTEXT_ORIGIN = UNKNOWN
HISTORICAL_SIDECAR_CREATOR = UNKNOWN
SEED_SIDECARS_PREEXISTING_AND_UNCHANGED = TRUE
HISTORICAL_MYPY = 15 errors/10 files
```

Les deux inconnues de vocabulaire restent hors migration et hors réécriture.
Le cycle B08 a fermé l'attribution opérationnelle PRE/POST sans identifier
rétroactivement le créateur des sidecars seed préexistants. La dette mypy
historique reste isolée et reproductible.

L'écart de hash de `catalog.py` dans un ancien test 12.16 était antérieur. La
remediation globale a établi que `catalog.py` et `anchor_corpus_v3.py` sont
absents des 40 entrées du JSON B01, contrairement au récit d'entrée du bundle.
Leurs identités courantes sont donc liées au commit propriétaire approuvé
`6d0d663...`, sans réécriture du freeze. Les assertions obsolètes sont fermées ;
les inconnues métier et la dette mypy ci-dessus restent ouvertes.
