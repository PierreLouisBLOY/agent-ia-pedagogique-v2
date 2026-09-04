# Phase 12.17.4E-B01 — Gate d'entrée du lot B02

## Verdict

`B02_ENTRY_GATE = READY`

La gate autorise uniquement la préparation ultérieure du lot B02 défini dans
le plan approuvé. Elle ne démarre pas B02 et ne constitue pas une autorisation
d'appel fournisseur, d'accès SQLite ou de modification historique.

## Entrées obligatoires de B02

- baseline d'origine approuvée :
  `6d0d66380757d7502fd967cd0246c5b6ff91d5f8` ;
- approbation propriétaire 12.17.4 : PASS ;
- ADR : `ADR-P12-068`, accepté ;
- décision : `ACTIVE_RUNTIME != HISTORICAL_CALIBRATION_EVIDENCE` ;
- freeze historique : 40 entrées immuables, `READ_ONLY` ;
- dérives préexistantes : 7, documentées, réparation rétroactive interdite ;
- preuve PRE/POST : 40/40 identiques ;
- manifeste B01 : doit rester valide lors de l'entrée effective en B02.

## Scope exact de B02

Le prochain lot exact est :

`12.17.4E-B02 — Contrats et runner unique (RC-03, partie RC-05)`

Il couvre un package provider-neutral, des modèles discriminés, la policy
durable, le budget et un runner offline sans adapter réel. Ses invariants sont
zéro réseau, zéro autorité métier, aucun import depuis `tests` et zéro
modification des 40 fichiers historiques figés.

`B02_STARTED = FALSE`
