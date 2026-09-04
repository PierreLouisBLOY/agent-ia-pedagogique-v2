# Phase 12.17.5B — Gel du plan d'exécution à sept lots

## Séquence canonique

| Batch | Canonical title | Root findings/changes | Owner decisions used | SQLite write? | Commit policy |
|---|---|---|---|---|---|
| B01 | Attestation propriétaire et gel des identités | précondition de gouvernance pour `DMAPI-001/002/003/004/009`; aucune clôture technique | `DM-01`, `DM-02`, `DM-03` | non | documentation séparée seulement si demandée |
| B02 | Runner de migrations multi-versions | prérequis technique de `DMAPI-001/002/009`; catalogue, ordre, ledger et postconditions | `DM-01/A` | non sur seed/runtime utilisateur; DB temporaires de tests possibles | code runner + tests, sans SQL `002`, commit séparé recommandé |
| B03 | Migration corrective `002` | restauration des cinq invariants de `document`; `DMAPI-001/002/009` | `DM-01/A` | seulement DB temporaires de tests | SQL `002` + tests ciblés, commit distinct |
| B04 | Validation réelle de la chaîne et récupération | preuve seed -> `001` -> `002`, runtime `001` -> `002`, replay et rollback | `DM-01/A` | oui, uniquement copies/runtime de test | preuves séparées; aucun binaire/sidecar dans Git |
| B05 | Contrat `resource_ref` | fermeture de `DMAPI-003` dans Domain/Application/persistence | `DM-02/A` | aucune migration; inspection data read-only possible | règle + tests; aucun endpoint |
| B06 | Sémantique `ACTIVE/CANONICAL` | fermeture conditionnelle de `DMAPI-004`; disponibilité séparée de canonicalité | `DM-03/B` | aucune sans design/approbation de migration distincte | concepts/mappings/tests séparés; migration distincte si requise |
| B07 | Ré-audit et décision de gate | ré-audit des 56 liens, READ-15, schéma et gate 12.17.6 | décisions appliquées en B02–B06 | lecture seule pour les preuves | artefacts de clôture; aucun endpoint anticipé |

```text
EXECUTION_BATCH_COUNT = 7
EXECUTION_BATCHES_RESOLVED = 7/7
EXECUTION_SEQUENCE = B01 -> B02 -> B03 -> B04 -> B05 -> B06 -> B07
EXECUTION_PLAN_AMBIGUITY = NONE
```

## Détails gelés par lot

### B01

- Scope : lier l'attestation, le registre, le commit et le seed; figer le plan.
- Hors scope : code, migration, contrat métier, API et provider.
- Fichiers : uniquement les artefacts du présent répertoire.
- Migration : aucune.
- Tests : bindings, hash seed, manifeste, qualité baseline et absence de drift.
- Gate suivante : B02 si toutes les identités et gates restent vertes.

### B02

- Scope : généraliser `backend/adapters/outbound/persistence/migrations.py` en runner ordonné allowlisté.
- Hors scope : fichier SQL `002`, `resource_ref`, `ACTIVE/CANONICAL`, API.
- Fichiers prévus : runner, tests unitaires/intégration et artefacts B02.
- Migration concernée : identité `001` conservée; aucune nouvelle migration créée.
- Tests : catalogue, ordre, checksums, versions inconnues/manquantes, runtime `001`, idempotence et rollback.
- Gate suivante : B03 si le runner accepte une future version sans relâcher l'allowlist.

### B03

- Scope : créer `database/migrations/002_restore_document_invariants.sql` et ses postconditions.
- Hors scope : données utilisateur, `resource_ref`, statuts ressource et API.
- Fichiers prévus : SQL `002`, catalogue/postconditions strictement nécessaires, tests et artefacts B03.
- Migration concernée : nouvelle `002`; `001` immuable.
- Tests : DDL exact, CHECK SHA conservé, cinq invariants restaurés, ligne/FK/index/replay.
- Gate suivante : B04 après tests ciblés PASS.

### B04

- Scope : valider les parcours réels sur copies temporaires et la récupération.
- Hors scope : modification du seed/runtime utilisateur et nouvelle règle métier.
- Fichiers prévus : artefacts de preuve uniquement; DB/backups/sidecars temporaires hors Git.
- Migrations concernées : `001`, `002` dans l'ordre autorisé.
- Tests : runtime neuf, runtime `001`, runtime complet, échec et rollback.
- Gate suivante : B05 après schéma/integrity/quick/FK/ledger PASS.

### B05

- Scope : implémenter `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` dans le bounded context ressource et le propager aux use cases/mappings.
- Hors scope : endpoint, migration data et statuts ressource.
- Fichiers prévus : Value Object/contrats ressource, mappings concernés, tests et artefacts B05.
- Migration : aucune attendue; compatibilité data vérifiée read-only.
- Tests : bornes 1/128/129, alphabet, caractères dangereux, références existantes.
- Gate suivante : B06 après absence de régression READ-15.

### B06

- Scope : séparer disponibilité et canonicalité selon `DM-03/B`.
- Hors scope : backfill inventé, `ContextOrigin` et mélange avec `002`.
- Fichiers prévus : Domain/Application/persistence et tests selon design approuvé; artefacts B06.
- Migration : identifiant et design distincts uniquement si une migration devient nécessaire et est approuvée.
- Tests : indépendance des dimensions, mappings, compatibilité des 1 399 `ACTIVE`, API handoff.
- Gate suivante : B07 après preuve de sémantique non ambiguë.

### B07

- Scope : ré-audit complet et recalcul de la gate 12.17.6.
- Hors scope : implémentation API ou nouveau comportement.
- Fichiers prévus : audit, traceability, findings, handoff et manifeste B07.
- Migration : aucune nouvelle; inspection read-only seulement.
- Tests : gates applicables de `ENVIRONMENT.md`, 56 liens, schéma, READ-15, diff et secrets.
- Gate suivante : 12.17.6 uniquement si tous les blockers sont fermés par preuve.

## Invariants transverses

Le seed reste immuable, `ContextOrigin` reste `UNKNOWN`, aucune migration de statut n'est implicite, aucun provider n'est appelé et aucun lot n'anticipe le suivant.
