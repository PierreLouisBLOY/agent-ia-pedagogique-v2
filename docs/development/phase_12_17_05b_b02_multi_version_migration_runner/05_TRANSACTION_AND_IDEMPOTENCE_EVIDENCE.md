# Phase 12.17.5B-B02 — Preuves de transaction et d'idempotence

## Sémantique d'exécution

- les ressources de toute la séquence sont chargées et authentifiées avant l'initialisation du ledger ;
- chaque migration manquante s'exécute dans sa transaction SQLite dédiée ;
- le ledger est écrit dans la même transaction que la migration ;
- une migration déjà présente avec le même checksum est ignorée ;
- un checksum différent produit `MIGRATION_CHECKSUM_MISMATCH: <version>` ;
- tout échec annule la migration fautive et empêche l'exécution des versions suivantes ;
- les versions validées avant l'échec restent tracées et ne sont pas rejouées.

## Preuves ciblées

| Cas | Résultat |
|---|---|
| ordre d'entrée non trié, exécution `001`, puis `002` | PASS |
| rejeu identique, historique stable | PASS |
| checksum de ressource incorrect avant écriture du ledger | PASS |
| checksum historique incorrect | PASS |
| trou dans l'historique | PASS |
| version historique inconnue | PASS |
| migration non applicable | PASS |
| erreur au milieu d'une séquence, rollback et absence de la suivante | PASS |

```text
IDEMPOTENCE = PASS
CHECKSUM_FAIL_CLOSED = PASS
ROLLBACK_FAULTING_MIGRATION = PASS
STOP_BEFORE_LATER_MIGRATION = PASS
```
