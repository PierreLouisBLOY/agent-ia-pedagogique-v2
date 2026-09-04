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

## Observabilite locale minimale

L'observabilite operationnelle utilise exclusivement la racine locale privee injectee par `PROJET_V2_DATA_DIR`. Le journal actif est `logs/observability.ndjson`, sous cette racine et obligatoirement hors du depot. La politique canonique `OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S` impose une rotation a 5 MiB, cinq fichiers au maximum, une retention de 14 jours et un flush synchrone borne a deux secondes lors de l'arret.

Les evenements suivent un schema ferme et ne doivent contenir ni secret, credential, token, chemin personnel, payload complet, prompt brut, reponse fournisseur brute, contenu pedagogique, message d'exception ni stack trace. Une panne du sink degrade uniquement son etat de sante et ne doit pas interrompre le flux metier. Les tests doivent injecter une racine sous le repertoire temporaire du systeme ; ils ne doivent jamais ecrire dans le depot, la base seed canonique ou la base runtime utilisateur.
