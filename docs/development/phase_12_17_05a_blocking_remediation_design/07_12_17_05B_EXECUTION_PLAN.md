# Phase 12.17.5B — Plan d'exécution proposé

## Précondition absolue

12.17.5B ne peut commencer qu'après sélection et attestation des trois décisions `DM-01`, `DM-02` et `DM-03`, liées au commit de baseline et au registre de décisions exacts. Ce document est un plan; aucune étape n'est exécutée dans 12.17.5A.

## Lots atomiques proposés

### B1 — Attestation propriétaire et gel des identités

- enregistrer les choix `DM-01`, `DM-02`, `DM-03` ;
- recalculer et geler les SHA-256 du registre et des sources concernées ;
- vérifier que la baseline et le seed correspondent aux identités approuvées ;
- arrêter fail-closed au moindre écart.

Livrable : attestation sans modification de code. Commit documentaire séparé si demandé.

### B2 — Runner de migrations multi-versions

- introduire un catalogue ordonné et allowlisté ;
- préserver strictement l'identité et le checksum de `001` ;
- valider l'intégralité du ledger ;
- appliquer seulement les versions manquantes dans l'ordre ;
- rendre les postconditions spécifiques à chaque version ;
- ajouter les tests d'ordre, de checksum, de trou, de version inconnue, d'idempotence et de rollback.

Livrable : code runner + tests, sans nouveau SQL métier dans le même commit.

### B3 — Migration corrective `002`

Uniquement si `DM-01/A` est approuvée :

- créer le SQL exact depuis le DDL canonique ;
- restaurer le CHECK `size_bytes` et les quatre defaults ;
- préserver la contrainte SHA-256 de `001` et les deux index ;
- ajouter les postconditions DDL complètes.

Livrable : migration + tests ciblés dans un commit distinct.

### B4 — Validation réelle de la chaîne et récupération

Sur copies temporaires uniquement :

- seed -> `001` -> `002` ;
- runtime avec ledger `001` -> `002` ;
- runtime déjà complet -> aucune écriture ;
- scénario d'échec -> rollback et restauration vérifiée ;
- nombre de lignes, foreign keys, index, contraintes, defaults, ledger et checksums vérifiés.

Ni seed ni runtime utilisateur ne doivent être modifiés. Les bases temporaires, backups et sidecars restent hors Git.

### B5 — Contrat `resource_ref`

Selon `DM-02` :

- implémenter la règle dans le bounded context propriétaire ;
- propager via les use cases Application et les mappings autorisés ;
- tester bornes, alphabet, compatibilité des formes existantes et entrées hostiles ;
- refaire une vérification read-only exhaustive avant activation.

Livrable : règle + tests. Aucun endpoint n'est créé dans ce lot.

### B6 — Sémantique `ACTIVE/CANONICAL`

Selon `DM-03` seulement :

- formaliser l'invariant et les transitions ;
- adapter Domain, Application et persistence sans coupler les contrats à SQLite/HTTP ;
- si un changement de schéma est requis, concevoir et approuver une migration distincte de `002` ;
- ne réaliser aucun backfill sans règle propriétaire et preuve de correspondance ;
- mettre à jour la projection READ-15 préparatoire.

Livrable : changements conditionnels + tests. Si `DM-03/D` est choisi, l'exposition reste bloquée et ce lot documente seulement le maintien du blocage.

### B7 — Ré-audit et décision de gate

- rejouer l'audit schéma seed/runtime ;
- vérifier les 56 liens de traçabilité ;
- recalculer l'alignement READ-15 et la complétude du handoff API ;
- exécuter les tests, lint et typecheck documentés dans `ENVIRONMENT.md` ;
- vérifier diff, secrets et absence d'artefacts runtime ;
- produire les preuves permettant à la gate 12.17.6 de décider.

## Séquencement

```text
B1 -> B2 -> B3 -> B4 -> B5 -> B6 -> B7
```

`B3/B4` sont conditionnés à `DM-01/A`. `B5` est conditionné au choix `DM-02`. `B6` est conditionné au choix `DM-03`. Aucun lot conditionnel ne peut interpréter le silence du propriétaire comme une approbation.

## Discipline de livraison

- petits commits séparant runner, migration, contrats et documentation ;
- pas de merge sans revue explicite ;
- pas de dépendance ou framework nouveau ;
- ADR uniquement si l'implémentation retenue dévie des frontières architecturales validées ;
- toute preuve PASS correspond à une commande réellement exécutée.

```text
PROPOSED_12_17_05B_BATCHES = 7
12_17_05B_ENTRY_GATE = BLOCKED_OWNER_DECISIONS
```
