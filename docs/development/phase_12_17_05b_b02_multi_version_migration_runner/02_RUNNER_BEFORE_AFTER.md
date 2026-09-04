# Phase 12.17.5B-B02 — Runner avant/après

| Dimension | Avant B02 | Après B02 |
|---|---|---|
| source de migration | chemin unique allowlisté | chemin historique ou registre explicite |
| versions supportées par le contrat | `001` uniquement | séquence ordonnée `001..N` |
| identité | allowlist globale de `001` | version, nom, ordre, ressource, checksum, applicabilité et postcondition |
| historique | vérification de `001` | historique connu, checksums conformes et préfixe sans trou |
| exécution | application/rejeu de `001` | application des seules versions manquantes dans l'ordre |
| résultat | booléen d'application | tuples explicites `applied` et `skipped` |
| échec | rollback de la migration | rollback de la migration fautive et arrêt avant toute version suivante |
| migration `001` | SHA canonique | strictement inchangée |

## Empreintes

```text
RUNNER_SHA256_BEFORE = 3f5bd782358efbf86b8f29f6eb25a34e1171b49a1ff9362933effba6b59c4182
RUNNER_SHA256_AFTER = c7aac0c2eb9b9e9d94925f9e2170878335373fabb13c297c67f663a2e1d744e2
SQLITE_COMPOSITION_SHA256_AFTER = 1483ceff7efd901217bc281e231b5d10cfa154956170c41863ee21fd14c44571
MIGRATION_001_SHA256_BEFORE = 5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
MIGRATION_001_SHA256_AFTER = 5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
MIGRATION_002_PRESENT = FALSE
```

La surface de compatibilité existante reste disponible : un appel avec le chemin canonique de `001` construit le registre approuvé à une entrée. Un appel futur peut injecter un `MigrationRegistry` complet sans coupler la composition à une migration concrète.
