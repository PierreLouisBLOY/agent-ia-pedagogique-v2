# Phase 12.17.4E-B09 — Handoff des owners Application

```text
APPLICATION_OWNER_ORDER = CAP-R02 -> CAP-A01 -> CAP-A02
APPLICATION_OWNERS_IMPLEMENTED_IN_B09 = 0/3
HANDOFF_STATUS = READY_FOR_ORDERED_MATERIALIZATION
```

| Capacité | Owner Application | Nature | Entrée minimale à matérialiser | Sortie | Contraintes principales |
|---|---|---|---|---|---|
| `CAP-R02` / `application.read_production` | `work_orchestration.application` | query read-only | `production_ref`, `version_ref` logiques | vue Production typée et minimisée | port outbound typé, aucun fallback READ-15, aucun SQL inbound |
| `CAP-A01` / `application.run_deterministic_validation` | `validation_control.application` | commande déterministe | `production_ref` logique | `ApplicationOutcome.validation_result` opaque | sans provider, pas d'autorité de promotion |
| `CAP-A02` / `application.request_promotion` | `lifecycle_promotion.application` | commande à effet derrière Gate | `production_ref`, clé d'idempotence hors payload et fait Gate trusted | outcome avec références operation/effect | Gate préexistante, ledger, réconciliation avant replay, aucun retry automatique |

Les DTO et codes d'erreur nouveaux restent à fermer dans chaque batch owner ;
B09 n'en crée aucun. Les familles d'erreur exigées sont validation fermée,
not-found/subject absent et failure Application ; CAP-A02 ajoute gate,
idempotence et conflit d'effet. Les tests obligatoires sont listés dans
[`API_HANDOFF.json`](API_HANDOFF.json).

Le registre et le routeur demeurent des métadonnées/dispatch. Ils ne deviennent
pas owners métier. Les agents continuent d'entrer exclusivement par une
frontière inbound Application.
