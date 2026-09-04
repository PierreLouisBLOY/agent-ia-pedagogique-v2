# DM-03 — Sémantique `ACTIVE` / `CANONICAL`

## Problème et preuves

Le Domain et la persistence reconnaissent deux valeurs distinctes, mais aucune source ne définit leur relation ou leurs transitions. Le seed et le runtime contiennent chacun 1 399 ressources `ACTIVE` et aucune `CANONICAL`. Le schéma a un default `ACTIVE` sans CHECK. Un test accepte techniquement `CANONICAL`, sans prouver sa signification.

Finding couvert : `DMAPI-004`.

## Options exactes du registre

### Option A

> Define ACTIVE and CANONICAL as exclusive states in one explicit lifecycle

- Règle canonique : machine d'état unique, dont transitions, autorité, réversibilité et effets de lecture doivent être définis.
- Source d'autorité : nouvelle décision owner; aucune donnée actuelle ne suffit.
- Domain/Application : invariant et transitions explicites dans le bounded context.
- SQLite/migration : **CONDITIONAL** selon les CHECK/defaults retenus; aucun backfill automatique.
- Backward compatibility : les 1 399 `ACTIVE` peuvent rester valides, mais le sens de `CANONICAL` change le contrat.
- API : publie un état exclusif documenté.
- Tests : transitions autorisées/interdites, persistence round-trip et projection API.
- Risque : suppose qu'une ressource canonique n'est plus active, ce qui n'est pas prouvé.

### Option B

> Separate availability lifecycle from canonicality and define independent authority and transitions

- Règle canonique : `ACTIVE` décrit disponibilité/cycle de vie; la canonicalité devient une dimension séparée avec autorité propre.
- Source d'autorité : décision owner puis contrat versionné; aucune canonicalité n'est inférée des données.
- Domain/Application : deux concepts et invariants distincts.
- SQLite/migration : **LIKELY_BUT_REQUIRES_SEPARATE_DESIGN** si une colonne est ajoutée; migration distincte de la corrective `002`.
- Backward compatibility : les 1 399 `ACTIVE` restent inchangées; aucun backfill `CANONICAL` inventé.
- API : champs non ambigus; le champ existant reste hors READ-15 jusqu'à définition de la projection.
- Tests : indépendance des axes, transitions, mappings, absence de backfill implicite et contrat API.
- Risque : changement de modèle plus large et besoin d'une nouvelle preuve de canonicalité.

### Option C

> Deprecate CANONICAL and retain ACTIVE as the persisted lifecycle state

- Règle canonique : `ACTIVE` reste l'état de cycle de vie; `CANONICAL` est déprécié puis retiré.
- Source d'autorité : décision owner justifiée par l'absence de données `CANONICAL`, sans conclure que le concept n'a jamais été prévu.
- Domain/Application : dépréciation puis retrait du literal et de ses branches.
- SQLite/migration : **CONDITIONAL** selon le retrait des contraintes ou données futures; aucune donnée actuelle à reclasser.
- Backward compatibility : risque pour des consommateurs ou données externes non inventoriés.
- API : `CANONICAL` absent du contrat futur.
- Tests : dépréciation, rejet/compatibilité versionnée et absence de référence restante.
- Risque : perte d'une intention métier encore non documentée.

### Option D

> Defer semantics and keep identity_status out of the public READ-15 contract

- Règle canonique : aucune nouvelle interprétation; modèle interne conservé temporairement.
- Source d'autorité : aucune.
- Domain/Application/SQLite : aucun changement; migration **FALSE**.
- Backward compatibility : maximale en interne.
- API : `identity_status` reste exclu et le périmètre concerné demeure bloqué.
- Tests : couverture actuelle seulement; aucune preuve de sémantique nouvelle.
- Risque : `DMAPI-004` reste ouvert et 12.17.6 ne peut pas être débloquée complètement.

## Recommandation Codex

```text
DM_03_RECOMMENDATION = OPTION_B
DM_03_CONFIDENCE = MEDIUM
```

Raison : disponibilité et canonicalité sont des dimensions conceptuellement indépendantes, et l'option B préserve toutes les données existantes sans inventer de canonicalité. La confiance reste moyenne car l'autorité et les transitions de la nouvelle dimension doivent encore être définies par l'owner.

`ContextOrigin` n'est pas couvert par `DM-03`. Aucune option n'est sélectionnée automatiquement.
