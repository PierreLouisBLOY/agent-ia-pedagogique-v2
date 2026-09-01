# Phase 12.16-G2-V4.2 — Verdict final de calibration

`CALIBRATION_VERDICT = CALIBRATION_COMPLETE`

Ce verdict signifie que les 102 records logiques sont présents, structurés, traçables
et méthodologiquement exploitables. Il ne constitue pas une approbation de release ni
une preuve que le scorer discrimine strictement tous les niveaux.

## Métriques finales

- critères anchors : 16 ;
- strict monotonicity : 0/16 ;
- weak monotonicity : 11/16 ;
- paires inversées : 5 ;
- paires liées : 13 ;
- critères inconclusifs : 0 ;
- repeatability strong-anchor : 16/16 accords exacts ;
- spread maximum : 0 ;
- comparaisons pairwise de productions : 6 ;
- primary wins : 0 ;
- fallback wins : 0 ;
- ties : 6 ;
- pairwise inconclusifs : 0.

Les données sont complètes, mais l'absence de stricte monotonie, les inversions et les
égalités ne permettent pas d'adopter un seuil de release dans ce lot.

`RELEASE_THRESHOLD_ADOPTED = NONE`

Une décision propriétaire ultérieure peut traiter la qualité discriminante du corpus
ou du scorer. Aucun rerun n'est implicitement autorisé par ce verdict.
