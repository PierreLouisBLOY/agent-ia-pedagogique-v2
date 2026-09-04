# Phase 12.17.5A-OD — Statut séparé de `ContextOrigin`

## État

```text
CONTEXT_ORIGIN = UNKNOWN
EVIDENCE_LEVEL = INSUFFICIENT
OWNER_DECISION_REQUIRED = FALSE
MIGRATION_AUTHORIZED = FALSE
```

## Justification

Le modèle Application ne dispose que d'une valeur technique `RUNTIME`; le mapper la valide puis renvoie actuellement `None`. Aucune colonne persistante ni source canonique ne permet de déduire une origine de contexte. Le paquet décisionnel n'apporte aucune preuve nouvelle.

`ContextOrigin` reste donc indépendant de `DM-03`. Il n'est pas inclus dans l'attestation demandée et ne peut provoquer ni colonne, ni backfill, ni migration dans 12.17.5B. Une évolution future requerra une preuve canonique ou une décision propriétaire dédiée dans un lot séparé.
