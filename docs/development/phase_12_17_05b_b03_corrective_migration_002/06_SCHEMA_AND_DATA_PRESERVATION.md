# Phase 12.17.5B-B03 — Préservation du schéma et des données

## Schéma cible

```text
SIZE_BYTES_NEGATIVE_REJECTED = TRUE
DOCUMENT_TYPE_DEFAULT = 'OTHER'
LANGUAGE_CODE_DEFAULT = 'fr'
DOCUMENT_STATUS_DEFAULT = 'ACTIVE'
CREATED_AT_DEFAULT = CURRENT_TIMESTAMP
SHA256_CHECK_PRESERVED = TRUE
EXPECTED_INDEXES = 2/2
DOCUMENT_TRIGGERS_EXPECTED_OBSERVED = 0/0
FOREIGN_KEY_CHECK = 0 violations
INTEGRITY_CHECK = ok
QUICK_CHECK = ok
```

## Données

- fixture avec deux documents : `2/2` identifiants préservés ;
- référence entrante synthétique : `1/1` préservée et valide ;
- copie temporaire du seed réel : `15/15` identifiants préservés ;
- nombre de lignes avant/après fourni par le runner : identique ;
- aucun titre, contenu ou payload pédagogique n'est écrit dans les preuves.

```text
ROW_PRESERVATION = PASS
PRIMARY_KEY_PRESERVATION = PASS
PEDAGOGICAL_CONTENT_EXPORTED = FALSE
```
