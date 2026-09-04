# Phase 12.17.5A — Root cause de la migration 001

## Portée et méthode

Cette analyse est strictement hors ligne et en lecture seule. Elle compare le DDL du seed canonique, le SQL de la migration `001` et le schéma du runtime après migration. Aucune base SQLite n'a été modifiée.

## Reproduction du défaut

La migration `001` ajoute correctement une contrainte de forme sur `document.sha256`, mais SQLite impose ici une reconstruction de table. Le script crée une table de remplacement, recopie les lignes, supprime l'ancienne table puis renomme la nouvelle.

Le DDL de remplacement ne reprend pas cinq invariants présents dans le seed :

| Invariant du seed | Après `001` | Impact |
|---|---|---|
| `size_bytes CHECK (size_bytes IS NULL OR size_bytes >= 0)` | absent | une taille négative devient persistable |
| `document_type DEFAULT 'OTHER'` | absent | les insertions omettant le champ échouent ou changent de comportement |
| `language_code DEFAULT 'fr'` | absent | même régression de valeur par défaut |
| `document_status DEFAULT 'ACTIVE'` | absent | même régression de valeur par défaut |
| `created_at DEFAULT CURRENT_TIMESTAMP` | absent | même régression de valeur par défaut |

Le mécanisme causal exact est donc un **DDL de remplacement incomplet** dans la reconstruction de `document`, et non la contrainte SHA-256 elle-même, la copie des données ou un écart du seed.

## État observé

- Seed canonique vérifié : SHA-256 `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`.
- Runtime vérifié : migration `001` inscrite dans `_runtime_migration_ledger` avec le checksum `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102`.
- La contrainte SHA-256 attendue est présente dans le runtime.
- Les cinq invariants ci-dessus sont absents du runtime.
- Les empreintes du seed, du runtime et de leurs sidecars éventuels sont restées identiques avant et après l'inspection read-only.

## Pourquoi `001` ne doit pas être réécrite

La migration `001` est déjà appliquée et enregistrée avec son checksum. Modifier son contenu casserait l'identité immuable du ledger, empêcherait de distinguer les runtimes historiques et rendrait les preuves de migration non reproductibles. La correction doit donc porter un nouvel identifiant de migration.

## Limite supplémentaire du runner

Le runner actuel n'est pas un runner multi-migrations :

- `MIGRATION_VERSION` est fixé à `001` ;
- le catalogue approuvé ne contient que `001` ;
- `MigrationArtifact.load()` affecte cette version fixe au fichier chargé ;
- `provision_runtime()` reçoit un unique chemin de migration ;
- la postcondition SHA est spécifique à `001`.

Ajouter seulement un fichier SQL `002` serait insuffisant : il serait chargé comme `001` et échouerait sur le checksum ou le ledger. La future exécution 12.17.5B doit d'abord introduire un catalogue ordonné et des postconditions par version, sans modifier l'artefact `001`.

## Conclusion

`DMAPI-001` et `DMAPI-002` sont reproduits. Leur remédiation technique est nécessaire et doit être versionnée. La gate 12.17.6 reste bloquée jusqu'à l'approbation propriétaire de `DM-01`, puis l'implémentation et la validation d'une chaîne `001 -> 002` dans un lot ultérieur.
