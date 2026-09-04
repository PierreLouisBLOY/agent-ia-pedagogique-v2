# Phase 12.17.5 — Audit CAP-R02 / CAP-A01 / CAP-A02

```text
CAP_R02_STATUS = HANDOFF_DEFINED_NOT_IMPLEMENTED
CAP_A01_STATUS = HANDOFF_DEFINED_NOT_IMPLEMENTED
CAP_A02_STATUS = HANDOFF_DEFINED_NOT_IMPLEMENTED
DELIVERY_ORDER = CAP-R02 -> CAP-A01 -> CAP-A02
```

## CAP-R02 — `application.read_production`

- owner : `backend.modules.work_orchestration.application` ;
- nature : query read-only ;
- entrée prévue : `production_ref`, `version_ref` logiques ;
- sortie prévue : vue Production typée et minimisée ;
- invariants : aucun fallback READ-15, aucun SQL/repository inbound, outcome
  transport-neutral ;
- persistance : port outbound de lecture Production et read model à matérialiser ;
- transitions : aucune, lecture seule ;
- tests actuels : métadonnées de registre et doubles E2E uniquement ; aucun use
  case ou port Production concret ;
- API : non autorisée dans le premier slice Resource.

## CAP-A01 — `application.run_deterministic_validation`

- owner : `backend.modules.validation_control.application` ;
- nature : commande déterministe, provider-free ;
- entrée prévue : `production_ref` ;
- sortie prévue : `ApplicationOutcome` avec résultat de validation opaque ;
- invariants : aucun pouvoir de promotion, aucune réinterprétation par le routeur ;
- persistance : règles Domain et contrat inbound à matérialiser ;
- transitions : produit un résultat de validation, sans transition de promotion ;
- tests actuels : scénarios/doubles E2E, pas de commande Application concrète ;
- API : non autorisée dans le premier slice Resource.

## CAP-A02 — `application.request_promotion`

- owner : `backend.modules.lifecycle_promotion.application` ;
- nature : commande à effet derrière une Gate préexistante ;
- entrée prévue : `production_ref`, clé d'idempotence hors payload et fait Gate
  trusted ;
- sortie prévue : outcome avec références d'opération et d'effet ;
- invariants : no self-approval, reconciliation avant replay, aucun retry
  automatique ;
- persistance : port promotion et effect ledger à matérialiser ;
- transitions : promotion uniquement après décision Gate valide ;
- tests actuels : politiques de Gate/idempotence génériques et doubles E2E, pas
  de commande owner concrète ;
- API : non autorisée dans le premier slice Resource.

Ces statuts sont des écarts d'implémentation attendus (`P2`), pas des
implémentations implicites déduites du registre de capabilities.
