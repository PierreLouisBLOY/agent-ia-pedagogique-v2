# Phase 12.17.5B-B06 — Inventaire `ACTIVE` / `CANONICAL`

Le comptage ci-dessous porte sur les neuf fichiers actifs du slice Resource :
Domain, port, DTO, query, inbound, stores/read-models SQLite et mapper partagé.
Il s'agit d'occurrences de source, pas de lignes de données.

| Token | Avant B06 | Après B06 | Classification après B06 |
|---|---:|---:|---|
| `ACTIVE` | 2 | 8 | disponibilité Domain et mapping legacy explicite |
| `CANONICAL` | 2 | 7 | canonicalité Domain et mapping legacy explicite |
| `ResourceIdentityStatus` | 10 | 0 | ancien modèle ambigu supprimé du slice actif |
| `identity_status` | 20 | 3 | nom de colonne physique aux seules frontières outbound |
| `availability_status` | 0 | 13 | contrat non ambigu Domain/Application/projection |
| `canonicality_status` | 0 | 4 | dimension Domain, volontairement non publiée |
| `UNKNOWN` | 0 | 10 | absence de preuve représentée explicitement |

Classification des autres occurrences du dépôt :

- `notion.identity_status = CANONICAL` appartient au bounded context
  Knowledge/Recherche et n'est pas une sémantique Resource ;
- `canonical_title` est un libellé de ressource et non une canonicalité ;
- `application.read_canonical_resource` nomme le use case canonique READ-15 et
  non un état d'autorité de l'entité ;
- les occurrences de calibration, workflow et documents sont sans rapport ;
- les anciens dossiers de preuve sont historiques et ne sont pas réécrits.

```text
ACTIVE_SOURCE_OCCURRENCES_BEFORE_AFTER = 2 -> 8
CANONICAL_SOURCE_OCCURRENCES_BEFORE_AFTER = 2 -> 7
SEMANTIC_CONFLICTS_BEFORE_AFTER = 1 -> 0
DUPLICATE_ACTIVE_RESOURCE_SEMANTIC_MODELS_BEFORE_AFTER = 1 -> 0
LEGACY_PHYSICAL_MAPPING_LIMITATIONS = 1
```
