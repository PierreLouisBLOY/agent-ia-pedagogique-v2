# ADR-P12-001 : baseline d'execution Python

- Statut : accepte
- Date : 2026-08-24
- Phase : 12.2

## Contexte

Projet V2 repart d'une base propre. La Phase 12.2 doit fournir un environnement de developpement minimal, reproductible et compatible avec la future implementation, sans choisir de framework ni de fournisseur.

## Decision

Le developpement utilise Python 3.12, borne par `requires-python = ">=3.12,<3.13"`.

Les environnements locaux reposent sur `venv` et l'installation sur `pip`. Les outils directs de developpement sont limites a `pytest`, `ruff` et `mypy`, avec des versions exactes dans `requirements-dev.txt`.

Aucune dependance runtime n'est declaree pendant la Phase 12.2. En particulier, aucun framework web ou agentique, provider LLM, ORM, vector store ou driver de base externe n'est retenu.

## Consequences

- Python 3.13 et les versions anterieures a 3.12 ne font pas partie de la baseline.
- Le bootstrap reste utilisable sur Windows, Linux et macOS avec les outils standards Python.
- Toute future dependance runtime exige une decision correspondant aux livrables canoniques.
- La persistance future pourra utiliser `sqlite3` de la bibliotheque standard, sans decision d'implementation dans cette phase.
