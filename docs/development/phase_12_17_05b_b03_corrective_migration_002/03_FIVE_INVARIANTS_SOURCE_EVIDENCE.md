# Phase 12.17.5B-B03 — Source des cinq invariants

Le seed canonique a été ouvert en `mode=ro` uniquement pour lire `sqlite_master`, les PRAGMA de schéma et les compteurs structurels. Aucun contenu pédagogique n'a été lu ou exporté.

| Invariant | DDL/default du seed | Après `001` | Cible `002` |
|---|---|---|---|
| taille non négative | `CHECK (size_bytes IS NULL OR size_bytes >= 0)` | absent | expression exacte restaurée |
| type documentaire | `DEFAULT 'OTHER'` | absent | valeur exacte restaurée |
| langue | `DEFAULT 'fr'` | absent | valeur exacte restaurée |
| statut | `DEFAULT 'ACTIVE'` | absent | valeur exacte restaurée |
| création | `DEFAULT CURRENT_TIMESTAMP` | absent | expression exacte restaurée |

L'union cible conserve également le CHECK SHA-256 de `001` : longueur `64` et alphabet hexadécimal insensible à la casse. Les objets seed de `document` observés sont la PK texte et les index `idx_document_sha256` et `idx_document_url`; aucune FK sortante ni aucun trigger propre à la table ne sont présents.

```text
FIVE_INVARIANTS_EXTRACTED = 5/5
VALUES_INVENTED = 0
SOURCE = CANONICAL_SEED_DDL_READ_ONLY_AND_12_17_05A_EVIDENCE
```
