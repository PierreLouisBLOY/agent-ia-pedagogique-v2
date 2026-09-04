# Phase 12.17.4 — Design de la trace legacy-review

## Décision OD-02

OD-02 Option A exige une trace canonique rétrospective sous
`docs/legacy-review/`. Cette trace répare l'emplacement documentaire manquant ;
elle ne transforme pas une adaptation passée en approbation passée.

## Arbre prévu

```text
docs/legacy-review/
  README.md
  phase_7_sqlite_runtime_reuse.md
```

`README.md` devient l'index des revues conformes futures. Le second fichier est
le seul rattrapage rétrospectif demandé par la preuve disponible.

## Contenu obligatoire de la trace Phase 7

```text
REVIEW_KIND = RETROSPECTIVE_TRACE
RETROACTIVE_APPROVAL = FALSE
PAST_APPROVAL_EVIDENCE = NOT_ASSERTED
SOURCE_PHASE = PHASE_7
RECONCILED_IN = PHASE_12_17_4
```

Le document doit :

1. citer `README.md` et sa règle de non-héritage V1 ;
2. citer
   `docs/development/PHASE_12_15_C0_SQLITE_RUNTIME_INTEGRATION_BASELINE.md`
   et `PHASE_12_15_LIVRABLE_COMPLET_CANONIQUE_FINAL.md` ;
3. reprendre uniquement les faits déjà publiés : migration 001 issue du commit
   historique `98d8464...`, implémentation `deb751d...`, contract kits
   `a57b95f...`, blob Git `38b369d...`, SHA-256 migration
   `5b4c603d...` ;
4. distinguer la copie octet-identique de migration et l'adaptation aux packages
   outbound V2 ;
5. expliquer la justification V2 : seed immuable, runtime dérivée, migrations
   uniquement sur la copie ;
6. inventorier les validations déjà attestées par Phase 12.15, avec liens vers
   leurs preuves, sans annoncer un nouveau PASS ;
7. déclarer explicitement que la trace est créée après les faits et ne prouve
   ni la date, ni l'acteur, ni la décision d'une approbation contemporaine ;
8. devenir la référence obligatoire de toute future affirmation sur cette
   réutilisation.

## Formulation interdite

Le document ne dira pas « approuvé en Phase 7 », « conforme depuis l'origine »
ou « revue antérieure retrouvée » sans pièce qui le prouve. Il ne réécrira pas
les commits, le README ou les baselines 12.15.

## Gate future

- les deux fichiers existent et sont liés entre eux ;
- chaque identifiant cité correspond à une source suivie ;
- `RETROACTIVE_APPROVAL = FALSE` est présent ;
- aucune source V1 n'est copiée dans le document ;
- un test documentaire vérifie la présence, les liens et les marqueurs ;
- le diff ne contient ni code, ni binaire, ni donnée runtime dans ce batch.

La matérialisation appartient au batch `B09` de l'exécution future, pas à la
présente gate de design.
