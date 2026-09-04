# DM-01 — Stratégie de correction de la migration `001`

## Problème

La reconstruction de `document` par `001` conserve l'ajout du CHECK SHA-256, mais omet exactement cinq invariants du seed : le CHECK non négatif de `size_bytes` et les defaults de `document_type`, `language_code`, `document_status` et `created_at`. `001` est déjà appliquée, journalisée et liée à un checksum; sa réécriture rétroactive est interdite.

Findings couverts : `DMAPI-001`, `DMAPI-002`. `DMAPI-009` dépend de l'implémentation retenue pour compléter les tests.

## Options exactes du registre

### Option A

> Keep 001 immutable, generalize the ordered migration runner, then add corrective migration 002

- Migration : **TRUE**; nouvelle `002`, après support d'un catalogue ordonné.
- Seed/runtime : seed inchangé; runtime neuf `001 -> 002`; runtime déjà en `001` applique seulement `002`.
- Code : généralisation ciblée du runner et postconditions par version.
- API : aucun endpoint direct; l'alignement physique débloque le ré-audit READ-15.
- Tests : ordre, checksums, versions inconnues/manquantes, runtime neuf/existant/complet, DDL complet, lignes, foreign keys, index, idempotence et rollback.
- Recovery : backup récupérable avant application; transaction et absence d'entrée `002` au ledger si échec.
- Risque : erreur dans le DDL de rebuild ou le séquencement; réduit par dérivation mécanique du seed, catalogue allowlisté et tests sur copies.

### Option B

> Create a newly versioned canonical seed and use an explicitly approved runtime reprovisioning strategy

- Migration : **CONDITIONAL_FOR_EXISTING_RUNTIMES**.
- Seed/runtime : nouvel artefact de seed; l'ancien seed et `001` restent immuables. La conservation des données des runtimes existants doit être décidée explicitement.
- Code : gestion de version de seed et reprovisionnement atomique plus larges.
- API : indirect; la gate reste bloquée jusqu'à équivalence démontrée.
- Tests : migration/conservation des données, bascule atomique, compatibilité et restauration.
- Recovery : retour à la version précédente du seed/runtime avec preuve d'intégrité.
- Risque : périmètre disproportionné et perte de données runtime si la stratégie est incomplète.

### Option C

> Defer remediation and keep persistence and phase 12.17.6 blocked

- Migration : **FALSE**.
- Seed/runtime : aucun changement, divergence connue conservée.
- Code/API : persistence et READ-15 restent bloqués.
- Tests : aucune clôture possible pour les tests manquants de préservation.
- Recovery : sans objet.
- Risque : maintien du P0 et impossibilité d'ouvrir 12.17.6.

## Recommandation Codex

```text
DM_01_RECOMMENDATION = OPTION_A
DM_01_CONFIDENCE = HIGH
```

Raison : l'option A est la seule qui répare à la fois les runtimes neufs et existants tout en préservant le seed, le checksum, le ledger et l'historique immuable de `001`. Le SQL `002` doit restaurer uniquement les cinq invariants et préserver le CHECK SHA-256; toute évolution `resource_ref` ou `ACTIVE/CANONICAL` doit rester séparée.

Cette recommandation n'est pas une approbation. L'owner doit sélectionner explicitement `OPTION_A`, `OPTION_B` ou `OPTION_C`.
