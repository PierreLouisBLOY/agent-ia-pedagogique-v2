# Phase 12.17.2 — Audit de placement architectural

## Classification des quinze fichiers

| Groupe | Fichiers | Production | Rôle réel | Recommandation |
| --- | ---: | --- | --- | --- |
| Provider Anthropic sous `tests/providers` | 2 | Non importé | Transport SDK et scorer utilisés par la calibration live | `MISPLACED_CANDIDATE`; décider en 12.17.4 entre tooling provider dédié et preuve historique. |
| Corpus/catalog/protocol | 5 | Non importé | Données, contraintes et projection de calibration | Conserver sous tooling/test tant que les identités historiques sont actives. |
| Call plans/review/repair | 4 | Non importé | Matrices, budgets et repair tranche versionnés | Rationalisation candidate; aucun déplacement isolé. |
| Intégration/pilotes/gate V5 | 4 | Non importé | Assemblage et décisions de pilotes V5 | Séparer à terme moteur actif et fixtures/versioning, sous 12.17.4. |

Nombre de fichiers fortement candidats à un mauvais placement : `2`.

## Tests vs tooling

Les quinze fichiers ne sont pas du runtime métier. Ils sont toutefois plus riches que des tests ordinaires : plusieurs construisent des matrices, calculent des budgets, composent des transports, parsèrent des réponses et ont servi à des appels live autorisés. Le bon axe de rationalisation est donc probablement :

```text
fixtures et preuves versionnées immuables
        séparées de
moteur de calibration réutilisable et provider tooling
```

Déplacer l'ensemble dans `backend` serait incorrect : cela introduirait un provider/calibration dans le runtime produit et contredirait l'absence de changement de route. Une destination de tooling séparée, possiblement sous `evaluation_harness`, doit être décidée en 12.17.4.

## Symptômes architecturaux

- `C02` : interface provider concrète dans le support test.
- `C03` : contrat de cardinalité répliqué dans quatre générations de corpus/catalogue.
- `C05` : budget guard dupliqué dans deux plans.
- `C07` : type canonique importé via un re-export implicite historique.
- `C08` : compatibilité micro-canary/mini-pilot exprimée par branches et types distincts.

Aucun fichier n'est déplacé dans ce lot.
