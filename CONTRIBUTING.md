# Contribuer a Projet V2

## Branches et lots

Partir d'une branche `main` propre et a jour. Utiliser une branche dediee et descriptive, par exemple `phase12/12-2-repository-baseline`. Un lot doit rester petit, coherent et limite a une decision ou un objectif valide.

Aucun choix issu de V1, aucun framework et aucune deviation de frontiere ne doivent etre introduits implicitement. Une deviation architecturale requiert un ADR explicite avant implementation.

## Qualite attendue

Installer l'environnement comme indique dans `docs/development/ENVIRONMENT.md`, puis executer avant toute demande de revue :

```text
python -m compileall backend
python -m pytest -q
python -m ruff check .
python -m mypy backend
```

Ne jamais masquer un echec ni annoncer un controle non execute comme reussi.

## Revue avant merge

Avant tout merge :

1. relire le diff complet et son `git diff --stat` ;
2. verifier que le lot ne depasse pas son perimetre ;
3. verifier l'absence de secret, base runtime, log, export ou artefact genere ;
4. confirmer que tests, lint et typecheck passent ;
5. faire relire les changements et les ADR eventuels.

Les donnees runtime et secrets restent hors du depot.
