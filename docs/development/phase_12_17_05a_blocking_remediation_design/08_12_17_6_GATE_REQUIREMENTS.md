# Phase 12.17.6 — Exigences d'entrée après remédiation

12.17.6 n'est pas commencée. Sa gate reste bloquée tant que toutes les preuves suivantes ne sont pas réunies.

## Identités et décisions

- baseline et seed correspondent aux identités approuvées ;
- `DM-01`, `DM-02`, `DM-03` sont sélectionnées et attestées ;
- le registre propriétaire est hashé et sans champ en attente ;
- toute option reportée maintient explicitement le périmètre concerné bloqué.

## Migration et schéma

- `001` est inchangée et son checksum historique est conservé ;
- le runner supporte une chaîne ordonnée et allowlistée ;
- la stratégie approuvée restaure les cinq invariants sans perdre le CHECK SHA-256 ;
- les parcours runtime neuf, runtime `001`, runtime complet et rollback sont testés ;
- le ledger, le nombre de lignes, les foreign keys et les index sont cohérents ;
- `UNEXPECTED_SCHEMA_DIFFERENCES = 0` pour le périmètre approuvé.

## Contrats métier et API

- `resource_ref` possède une règle Domain/Application approuvée, propagée et testée ;
- les valeurs persistées existantes sont compatibles ou disposent d'une remédiation approuvée ;
- `ACTIVE/CANONICAL` possède une sémantique approuvée et une projection API non ambiguë, ou le champ reste explicitement hors périmètre ;
- aucun contrat Domain/Application ne dépend de types HTTP, ORM ou SDK fournisseur ;
- les capacités `CAP-R02`, `CAP-A01` et `CAP-A02` ne sont déclarées implémentées qu'avec preuves réelles ;
- READ-15 est ré-audité avant toute implémentation d'endpoint.

## Qualité et sécurité

- les cinq findings bloquants sont fermés par des preuves exécutées, pas seulement par le présent design ;
- tests, lint et typecheck applicables sont PASS ;
- audit de secrets PASS ;
- aucune base, sauvegarde, sidecar ou sortie runtime n'entre dans Git ;
- diff et état Git sont revus ;
- aucun appel fournisseur n'est nécessaire ni autorisé par cette gate.

## Verdict courant

```text
PHASE_12_17_6_STARTED = FALSE
PHASE_12_17_6_ENTRY_GATE = BLOCKED
BLOCKING_REASON = OWNER_DECISIONS_AND_12_17_05B_EXECUTION_REQUIRED
```
