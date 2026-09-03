# Revues de réutilisation legacy V2

Ce répertoire est l'index canonique des revues de réutilisation d'un actif
antérieur dans Projet V2. Il applique la règle de non-héritage de
[`README.md`](../../README.md) : aucune source V1 n'est reprise implicitement.

## Revues enregistrées

- [Réutilisation du runtime SQLite Phase 7](phase_7_sqlite_runtime_reuse.md) —
  trace rétrospective créée en Phase 12.17.4E-B09.

## Convention obligatoire pour toute future réutilisation

La décision et sa trace doivent exister avant l'intégration. Une revue contient
au minimum :

1. la source exacte et sa provenance ;
2. la justification V2 ;
3. la portée reprise et la portée exclue ;
4. les risques identifiés ;
5. la décision explicite prise avant réutilisation ;
6. les tests et preuves d'acceptation ;
7. le statut de supersession ;
8. les hashes ou identités de provenance pertinents.

Une trace produite après les faits doit porter sans ambiguïté les marqueurs
suivants et ne peut jamais tenir lieu d'approbation contemporaine :

```text
RETROSPECTIVE_DOCUMENTATION = TRUE
RETROACTIVE_APPROVAL = FALSE
```
