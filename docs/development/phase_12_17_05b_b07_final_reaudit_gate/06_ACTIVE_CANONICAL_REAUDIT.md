# Phase 12.17.5B-B07 — Ré-audit ACTIVE/CANONICAL

Le modèle B06 sépare `ResourceAvailabilityStatus` et
`ResourceCanonicalityStatus`. `ACTIVE` se traduit en disponibilité prouvée et
canonicalité `UNKNOWN`; `CANONICAL` se traduit en disponibilité `UNKNOWN` et
canonicalité prouvée. Aucune implication croisée n'est codée.

Le mapper legacy conserve les deux valeurs mais refuse les états que la colonne
unique ne peut représenter sans perte. Les 1 399 lignes `ACTIVE` ne reçoivent
aucun classement de canonicalité. Aucun backfill et aucune migration de statut
n'ont été autorisés ou exécutés.

READ-15 et OP-12 publient seulement `availability_status`; ils n'exposent ni
`identity_status` ambigu, ni canonicalité inventée.

```text
ACTIVE_CANONICAL_BLOCKER = CLOSED
AVAILABILITY_CANONICALITY_SEPARATE = TRUE
ACTIVE_IMPLIES_CANONICAL = FALSE_NOT_INFERRED
CANONICAL_IMPLIES_ACTIVE = NOT_PROVEN
UNKNOWN_CANONICALITY_REPRESENTABLE = TRUE
ACTIVE_CANONICAL_BACKFILL = FALSE
ACTIVE_CANONICAL_MIGRATION = FALSE
CONTEXT_ORIGIN = UNKNOWN_NON_BLOCKING
```
