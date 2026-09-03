# Phase 12.17.4 — Handoff d'entrée 12.17.5

```text
TARGET_PHASE = 12.17.5 — audit modèle de données / API
12_17_5_ENTRY_GATE = READY
12_17_5_STARTED = FALSE
```

Entrées validées à reprendre :

- runtime SQLite validée et distincte du seed canonique ;
- mappings SQLite B06 possédés par bounded context ;
- handoff B09 `HANDOFF_ONLY`, sans endpoint déjà implémenté ;
- ordre Application OD-03 : CAP-R02, CAP-A01, CAP-A02 ;
- OD-04 : premier scope HTTP limité à READ-15 Resource ;
- route proposée `GET /api/v2/resources/{resource_ref}` vers l'inbound
  Application Resource Library ;
- OD-07 : `version_ref` et `include` dépréciés pour READ-15 actif ;
- SQL et repositories directs interdits à la frontière inbound ;
- exécution locale navigateur, bind loopback par défaut, aucune dépendance
  runtime Google Drive et aucun exécutable Windows requis.

Les cinq findings de `06_OPEN_FINDINGS_REGISTER.json` sont des entrées
obligatoires de l'audit, pas des faits à inventer. En particulier, les valeurs
Resource ACTIVE/CANONICAL et `ContextOrigin` ne doivent pas être alignées ou
migrées avant preuve et décision propres à 12.17.5.

Ce document prépare uniquement l'entrée. Il n'implémente ni modèle de données,
ni endpoint, ni migration et ne commence pas 12.17.5.
