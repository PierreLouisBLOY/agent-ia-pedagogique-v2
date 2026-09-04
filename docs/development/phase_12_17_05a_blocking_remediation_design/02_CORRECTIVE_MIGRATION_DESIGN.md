# Phase 12.17.5A — Design de migration corrective

## Décision attendue

Ce document décrit la recommandation associée à `DM-01`. Il ne crée ni n'exécute de migration.

### Option A — Migration `002` immuable et runner ordonné — recommandée

Conserver `001` bit pour bit, généraliser le runner pour appliquer un catalogue approuvé et ordonné, puis ajouter une migration corrective `002` qui reconstruit `document` avec l'union exacte :

- du schéma canonique initial ;
- de la contrainte SHA-256 introduite par `001`.

Confiance : **élevée**. Cette option préserve le ledger, répare les runtimes déjà migrés et donne le même résultat à un runtime neuf (`001`, puis `002`).

### Option B — Nouveau seed versionné et reprovisionnement contrôlé

Créer ultérieurement un nouveau seed canonique et reprovisionner atomiquement les runtimes, sans modifier l'ancien seed ni `001`. Cette option est plus large, impose une stratégie explicite de conservation des données runtime et ne résout pas à elle seule la compatibilité des runtimes déjà provisionnés.

Confiance : **moyenne**. Elle peut devenir pertinente lors d'un changement de génération de seed, mais elle est disproportionnée pour les cinq invariants perdus.

### Option C — Reporter

Ne pas corriger immédiatement et garder la persistence/API bloquée. Cette option évite une modification technique mais conserve une divergence de schéma connue et ne permet pas d'ouvrir 12.17.6.

Confiance : **élevée** sur l'effet bloquant.

## Forme conceptuelle de `002`

Le SQL ci-dessous est un design à transcrire et faire approuver dans 12.17.5B. Il ne constitue pas un artefact exécutable de ce lot.

```sql
PRAGMA foreign_keys = OFF;

BEGIN IMMEDIATE;

CREATE TABLE document__p12_17_05b_new (
    id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL DEFAULT 'OTHER',
    title TEXT NOT NULL,
    file_name TEXT,
    mime_type TEXT,
    publication_date TEXT,
    accessed_at TEXT,
    url TEXT,
    size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
    sha256 TEXT CHECK (
        sha256 IS NULL OR (
            length(sha256) = 64
            AND sha256 NOT GLOB '*[^0-9A-Fa-f]*'
        )
    ),
    storage_uri TEXT,
    language_code TEXT NOT NULL DEFAULT 'fr',
    license_code TEXT,
    document_status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO document__p12_17_05b_new (
    id, document_type, title, file_name, mime_type, publication_date,
    accessed_at, url, size_bytes, sha256, storage_uri, language_code,
    license_code, document_status, created_at
)
SELECT
    id, document_type, title, file_name, mime_type, publication_date,
    accessed_at, url, size_bytes, sha256, storage_uri, language_code,
    license_code, document_status, created_at
FROM document;

DROP TABLE document;
ALTER TABLE document__p12_17_05b_new RENAME TO document;
CREATE INDEX idx_document_sha256 ON document(sha256);
CREATE INDEX idx_document_url ON document(url);

COMMIT;
PRAGMA foreign_keys = ON;
```

Le DDL final devra être dérivé mécaniquement du seed canonique vérifié et de la postcondition `001`; toute différence supplémentaire doit faire échouer la revue.

## Évolution préalable du runner

Le futur lot 12.17.5B doit :

1. remplacer la version globale par un catalogue explicite `version -> chemin -> checksum -> postconditions` ;
2. trier les versions avec une règle déterministe et refuser doublons, trous ou versions inconnues ;
3. charger la version depuis l'entrée du catalogue, jamais depuis un nom de fichier non approuvé ;
4. valider tous les enregistrements du ledger avant application ;
5. appliquer transactionnellement les migrations manquantes dans l'ordre ;
6. conserver les postconditions de `001` et ajouter les cinq postconditions de `002` ;
7. publier dans le rapport la séquence exacte appliquée ou réutilisée.

## Matrice de validation future

| Cas | État initial | Résultat attendu |
|---|---|---|
| Runtime neuf | copie exacte du seed | application `001`, puis `002` |
| Runtime existant | ledger `001` valide | application de `002` seule |
| Runtime complet | ledger `001`,`002` valides | aucune écriture |
| Checksum inconnu | ledger ou artefact divergent | arrêt fail-closed |
| Version manquante/inconnue | chaîne non continue | arrêt fail-closed |
| Échec SQL/postcondition | transaction en cours | rollback, pas de ledger `002` |

Pour chaque cas de succès : nombre de lignes inchangé, `PRAGMA foreign_key_check` vide, index attendus présents, contrainte SHA conservée et cinq invariants restaurés. Une sauvegarde récupérable du runtime devra précéder toute application réelle.

## Périmètre de la migration

La future `002` ne doit contenir que la restauration des cinq invariants de `document`. Toute évolution issue de `DM-02` ou `DM-03` exige son propre design et, si nécessaire, une migration distincte. Cela évite de mélanger correction de régression et évolution métier.
