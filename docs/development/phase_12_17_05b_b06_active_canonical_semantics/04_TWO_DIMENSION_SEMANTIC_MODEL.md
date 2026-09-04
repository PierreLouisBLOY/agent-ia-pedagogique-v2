# Phase 12.17.5B-B06 — Modèle sémantique à deux dimensions

`ResourceAvailabilityStatus` possède `UNKNOWN` et `ACTIVE`.
`ResourceCanonicalityStatus` possède `UNKNOWN` et `CANONICAL`. Le Value Object
`ResourceSemanticState` transporte les deux dimensions sans les assimiler.

Les seules observations autorisées par les preuves actuelles sont :

| Disponibilité | Canonicalité | Statut |
|---|---|---|
| `ACTIVE` | `UNKNOWN` | prouvée par les 1 399 lignes existantes |
| `UNKNOWN` | `CANONICAL` | support explicite de la valeur legacy, sans inférence d'activité |
| `UNKNOWN` | `UNKNOWN` | représentable en mémoire, non persistable dans la colonne legacy |
| `ACTIVE` | `CANONICAL` | bloquée : combinaison non autorisée par une règle propriétaire |

Aucune valeur `INACTIVE`, `UNAVAILABLE` ou `NON_CANONICAL` n'est créée, faute
de vocabulaire approuvé. `UNKNOWN` n'est jamais encodé comme `False`. Aucune
transition de disponibilité ou de canonicalité n'est introduite : son autorité,
ses préconditions et sa réversibilité ne sont pas définies par les preuves.

L'implication `canonical => active` n'est ni encodée ni déduite. Une valeur
legacy `CANONICAL` devient donc `UNKNOWN/CANONICAL`, et non
`ACTIVE/CANONICAL`.

```text
AVAILABILITY_MODEL_STATUS = COMPLETE_FOR_APPROVED_EVIDENCE
CANONICALITY_MODEL_STATUS = COMPLETE_FOR_APPROVED_EVIDENCE
UNKNOWN_REPRESENTABLE = TRUE
FALSE_USED_AS_UNKNOWN = FALSE
CANONICAL_IMPLIES_ACTIVE = NOT_PROVEN
AUTHORIZED_TRANSITIONS = NONE
UNPROVEN_COMBINATIONS_ACCEPTED = FALSE
```
