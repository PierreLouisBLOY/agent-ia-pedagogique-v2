# Environnement de developpement

La baseline de Projet V2 est Python 3.12 exclusivement (`>=3.12,<3.13`). Le projet utilise `venv` et `pip`; aucun gestionnaire d'environnement supplementaire n'est requis.

## Windows PowerShell

Verifier que Python 3.12 est installe, puis executer :

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes --no-deps -r requirements/lock/dev-py312-win.txt
python -m pip install --require-hashes --no-deps -r requirements/lock/calibration-py312-win.txt
```

Si `python.exe` 3.12 est disponible directement, il peut remplacer `py -3.12` pour la creation du venv.

## Linux et macOS

```bash
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
echo "Les locks actuels ciblent win_amd64 ; regenerer un lock approuve pour cette plateforme."
```

## Validation locale

Depuis le venv active et la racine du depot :

```text
python --version
python -m pip install --require-hashes --no-deps -r requirements/lock/dev-py312-win.txt
python -m pip install --require-hashes --no-deps -r requirements/lock/calibration-py312-win.txt
python -m compileall backend
python -m pytest -q
python -m ruff check .
python -m mypy backend
```

## Ensembles de dependances reproductibles

`pyproject.toml` reste l'autorite des bornes semantiques : le runtime depend directement de `openai>=3.5,<4`, et l'extra `calibration` ajoute exclusivement `anthropic>=1.2,<2`. `requirements-dev.txt` conserve les trois outils directs et epingles `pytest`, `ruff` et `mypy`.

Les resolutions Python 3.12 / Windows AMD64 sont versionnees separement :

- `requirements/lock/runtime-py312-win.txt` : runtime OpenAI et transitives ;
- `requirements/lock/calibration-py312-win.txt` : runtime plus extra Anthropic de calibration ;
- `requirements/lock/dev-py312-win.txt` : runtime plus outils de validation, sans Anthropic.

Chaque exigence est epinglee et porte le SHA-256 du wheel approuve. Installer un ensemble avec `--require-hashes --no-deps`; pour une validation sans reseau, ajouter `--no-index --find-links <wheelhouse-prive>`. Les locks refusent les sdists. Les wheels et environnements restent hors du depot. Une autre version Python, architecture ou plateforme exige une resolution et une revue distinctes.

Le SDK Anthropic n'est pas une dependance du produit. Installer le lock de calibration ne constitue ni une autorisation de credential ni une autorisation d'appel fournisseur.
Le lock dev seul suffit aux validations hors calibration ; la suite complete du depot exige l'installation successive des locks dev et calibration.

## Configuration SQLite V2

Les seuls noms de configuration acceptes sont `PROJET_V2_DATA_DIR`, `PROJET_V2_CANONICAL_DB` et `PROJET_V2_RUNTIME_DB`. Les anciens noms `PEDAGOGICAL_CANONICAL_SEED_PATH` et `PEDAGOGICAL_RUNTIME_DATABASE_PATH` sont retires : leur presence echoue avec le code ferme `LEGACY_SETTING_FORBIDDEN`, sans exposer leur valeur. Migrer la configuration locale vers les noms V2 ; aucun chemin local prive ne doit etre inscrit dans Git.

Ne placer aucun secret dans un fichier suivi par Git. Les fichiers `.env*`, bases runtime, logs, exports et artefacts d'execution sont ignores et doivent rester hors du source tree.

## Observabilite locale minimale

L'observabilite operationnelle utilise exclusivement la racine locale privee injectee par `PROJET_V2_DATA_DIR`. Le journal actif est `logs/observability.ndjson`, sous cette racine et obligatoirement hors du depot. La politique canonique `OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S` impose une rotation a 5 MiB, cinq fichiers au maximum, une retention de 14 jours et un flush synchrone borne a deux secondes lors de l'arret.

Les evenements suivent un schema ferme et ne doivent contenir ni secret, credential, token, chemin personnel, payload complet, prompt brut, reponse fournisseur brute, contenu pedagogique, message d'exception ni stack trace. Une panne du sink degrade uniquement son etat de sante et ne doit pas interrompre le flux metier. Les tests doivent injecter une racine sous le repertoire temporaire du systeme ; ils ne doivent jamais ecrire dans le depot, la base seed canonique ou la base runtime utilisateur.
