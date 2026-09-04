# Phase 12.17.6 — Périmètre et baseline

## Verdict d'entrée

`PHASE_12_17_05C = PASS`

`12_17_6_ENTRY_GATE = READY`

`HEAD = e2c43184a272491371b73131170db488cf3157d6`

Les bindings exigés sont confirmés : parent `576d6bd6dcf5082740c4192842b7c87ccbc1f246`, manifest 12.17.5C `eec96d69a697d7a3c9d298ab66ac71ca8c6a8eb9334418ca49709e3c82076fcb`, suite globale antérieure `4816 passed, 3 skipped, 0 failed`, seed `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`, appels fournisseur `0`.

Le ZIP d'instructions contrôlé a le SHA-256 `dc1a9165f4720b2d9d8297549da15ca32a1909af4e27d59169e303190b8c67ae`; ses six entrées correspondent à son manifest, dont le SHA-256 est `e74cab22ca827c03b551e5d45aa6ed27959603746190093d3f3dde5e82c9fd32`.

## Worktree observé avant production du présent paquet

- fichiers stagés : `0` ;
- fichiers suivis modifiés : `0` ;
- fichiers non suivis : `137` ;
- éléments hors scope historiques annoncés : `126` ;
- éléments hors scope historiques observés et classifiés : `126` ;
- preuves 12.17.5C non commitées, exclues du registre des 126 : `11`.

La réconciliation `126 + 11 = 137` est exacte. Les 126 entrées sont détaillées dans `08_REPOSITORY_HYGIENE_126_ITEMS.json`.

## Méthode et limites

Audit statique des surfaces, recherches ciblées, inventaire Git et des racines ignorées, lecture des contrats et adaptateurs, scan de formes de credentials sans affichage de valeur, puis 409 tests ciblés. Aucun lookup CVE web n'a été effectué. Aucun fichier utilisateur, aucune base et aucun fournisseur n'ont été modifiés ou appelés.

Contrôles ciblés : `409 passed in 62.53s`. Les tests ont utilisé le répertoire temporaire du système, hors dépôt.

## Invariants de sortie

- `CODE_OR_RULES_MODIFIED = 0`
- `SQLITE_WRITES = 0`
- `PROVIDER_CALLS = 0`
- `STAGED = NONE`
- `COMMIT = NONE`
- `PUSH = NONE`
