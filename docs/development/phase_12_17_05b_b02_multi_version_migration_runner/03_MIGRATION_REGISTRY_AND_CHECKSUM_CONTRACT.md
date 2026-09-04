# Phase 12.17.5B-B02 — Contrat du registre et des checksums

## Identité d'une migration

Chaque `MigrationSpec` porte explicitement :

- une version numérique sur trois chiffres ;
- un nom stable ;
- un ordre entier ;
- une ressource locale ;
- son SHA-256 attendu ;
- son applicabilité ;
- une postcondition optionnelle.

## Invariants fail-closed

Le registre :

1. n'est jamais vide ;
2. trie les spécifications par ordre explicite ;
3. refuse les versions ou ordres dupliqués ;
4. refuse tout identifiant ou checksum mal formé ;
5. impose des ordres contigus à partir de `1` ;
6. impose des versions contiguës à partir de `001` ;
7. authentifie toutes les ressources avant la première écriture de ledger.

Le runner :

1. rejette toute version de ledger absente du registre ;
2. rejette tout checksum de ledger différent de la ressource enregistrée ;
3. exige que l'historique observé soit un préfixe ordonné du registre ;
4. vérifie la postcondition d'une version déjà appliquée ;
5. refuse une version manquante marquée non applicable ;
6. applique seulement les versions manquantes et retourne séparément `applied` et `skipped`.

```text
PRODUCTION_REGISTRY_VERSION_COUNT = 1
PRODUCTION_REGISTRY_VERSIONS = 001
REGISTERED_002 = FALSE
FAIL_CLOSED = TRUE
```
