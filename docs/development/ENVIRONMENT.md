# Environnement de developpement

La baseline de Projet V2 est Python 3.12 exclusivement (`>=3.12,<3.13`). Le projet utilise `venv` et `pip`; aucun gestionnaire d'environnement supplementaire n'est requis.

## Windows PowerShell

Verifier que Python 3.12 est installe, puis executer :

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Si `python.exe` 3.12 est disponible directement, il peut remplacer `py -3.12` pour la creation du venv.

## Linux et macOS

```bash
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Validation locale

Depuis le venv active et la racine du depot :

```text
python --version
python -m pip install -r requirements-dev.txt
python -m compileall backend
python -m pytest -q
python -m ruff check .
python -m mypy backend
```

Les seules dependances directes de developpement sont `pytest`, `ruff` et `mypy`, epinglees dans `requirements-dev.txt`. La seule dependance runtime directe est le SDK Python officiel `openai`, borne a la version majeure calibree dans `pyproject.toml`.

Ne placer aucun secret dans un fichier suivi par Git. Les fichiers `.env*`, bases runtime, logs, exports et artefacts d'execution sont ignores et doivent rester hors du source tree.
