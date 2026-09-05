# État de l'environnement avant résolution

```text
OS = Windows 11 10.0.26200
ARCHITECTURE = AMD64
PYTHON = CPython 3.12.14
PYTHON_ABI = cp312
PIP = 25.0.1
DEPENDENCY_TOOL = venv + pip
PRE_LOCK_COUNT = 0
```

Avant B05, `pyproject.toml` déclarait `openai>=3.5,<4` au runtime et
`anthropic>=1.2,<2` dans l'extra `calibration`. `requirements-dev.txt` épinglait
`pytest==9.1.1`, `ruff==0.16.4` et `mypy==2.3.1`. Aucun fichier setup, constraints,
Pipfile, Poetry ou lock n'était présent.

```text
PYPROJECT_SHA256 = d3aaf2cc2abd2ad35a1112c3bebc998ffbe0925943adcaad46018c7282fcacbc
REQUIREMENTS_DEV_SHA256 = a41e6dd0b460173f10812c1cebaf65d013ceac9c6893ebb242a5796ad7461123
DIRECT_DEPENDENCY_COUNT_PRE = 5
DIRECT_DEPENDENCY_COUNT_POST = 5
SOURCE_BOUND_CHANGE_COUNT = 0
```

Les deux noms legacy SQLite étaient encore acceptés et les alias publics de tests
pointaient vers l'ancien nom de seed. Aucun chemin local privé n'était codé comme
default produit.
