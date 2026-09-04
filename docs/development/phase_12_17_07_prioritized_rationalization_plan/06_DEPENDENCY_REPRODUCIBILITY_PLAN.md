# Phase 12.17.7 — Reproductibilité des dépendances

## Décision technique

```text
LOCKFILE_REQUIRED_BEFORE_12_18 = TRUE
DEPENDENCY_HYGIENE_ITEMS_COUNT = 5
TARGET_BATCH = 12.17.8-B05
LOCKFILE_CREATED_NOW = FALSE
```

Le dépôt cible Python `>=3.12,<3.13` et un poste local Windows. Le format retenu est un ensemble de requirements textuels résolus et hashés, consommables par `python -m pip install --require-hashes`. La génération utilise les commandes natives `pip download`/`pip hash` dans un environnement propre; aucun nouvel outil ou package runtime n'est requis.

## Cinq items de remédiation

| # | Item | Plan exact | Test/acceptation |
|---:|---|---|---|
| 1 | Séparer les ensembles | Produire `requirements/lock/runtime-py312-win.txt`, `calibration-py312-win.txt` et `dev-py312-win.txt`; calibration inclut runtime, dev inclut runtime et outils de validation, sans faire d'Anthropic une dépendance du produit. | matrice d'appartenance; aucun package fournisseur inattendu dans runtime |
| 2 | Résoudre et hasher | Depuis un venv propre Python 3.12, résoudre les versions exactes, télécharger uniquement les artefacts compatibles, enregistrer au moins un SHA-256 par exigence et les métadonnées Python/plateforme/pip utilisées. | chaque ligne installable porte version exacte et hash; absence de VCS/URL flottante |
| 3 | Conserver les bornes sources | Garder `pyproject.toml` comme intention sémantique (`openai>=3.5,<4`, extra `anthropic>=1.2,<2`) et les pins des outils dev; le lock est une résolution, pas une nouvelle autorité métier. | guard vérifie que le lock satisfait les bornes et que les extras restent distincts |
| 4 | Prouver l'installation reproductible | Installer chacun des trois ensembles dans un venv neuf avec `--require-hashes --no-deps`; comparer `pip freeze` normalisé au lock et exécuter un import smoke test. | deux installations propres donnent le même ensemble exact; hash invalide échoue |
| 5 | Détecter le drift | Ajouter un test/commande CI qui reconstruit un rapport de résolution et échoue si `pyproject.toml`, les inputs dev ou un lock divergent; documenter la procédure de mise à jour/revue. | modification de borne sans régénération échoue; lock inchangé passe offline avec wheelhouse de test |

Les hashes peuvent varier par artefact de plateforme; chaque lock doit déclarer explicitement sa cible. Un sdist non audité ou un package sans artefact hashé pour la cible échoue fermé et requiert une exception documentée, jamais une installation sans hashes.

## Documentation/configuration associées dans B05

- corriger `docs/development/ENVIRONMENT.md` pour distinguer runtime OpenAI, extra de calibration Anthropic et outils dev/test ;
- trancher la fenêtre d'alias SQLite selon le contrat de dépréciation déjà annoncé : noms V2 canoniques, alias legacy rejetés avec un code d'aide fermé après la période de compatibilité ;
- ne modifier aucune route fournisseur, modèle, credential ou valeur live.

## Exception documentée

Si une installation reproductible hashée est techniquement impossible pour un artefact nécessaire, B05 doit s'arrêter. La gate finale n'accepte une exception que si elle nomme l'artefact, la raison, la cible, la mesure compensatoire et l'approbation propriétaire. Aucune exception générique n'est permise.

`DEPENDENCY_REPRODUCIBILITY_TARGET = PASS_OR_EXACT_OWNER_ACCEPTED_EXCEPTION`
