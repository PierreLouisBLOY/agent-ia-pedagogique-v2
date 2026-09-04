# Phase 12.17.6 — Dépendances et configuration

## Inventaire

- Python : `>=3.12,<3.13`.
- Runtime direct : `openai>=3.5,<4`.
- Extra calibration : `anthropic>=1.2,<2`.
- Développement : `pytest==9.1.1`, `ruff==0.16.4`, `mypy==2.3.1`.
- Aucun framework serveur.
- Aucun lockfile ni fichier de hashes de dépendances.
- Aucun subprocess, `shell=True`, `eval`, `exec` dynamique, pickle dangereux ou YAML loader permissif dans le runtime.

Les SDK fournisseurs sont réellement utilisés : OpenAI dans les adaptateurs backend et Anthropic dans la couche client de calibration/test injectée. Les dépendances sont bornées par version majeure, mais une installation nouvelle n'est pas byte-for-byte reproductible. La documentation `ENVIRONMENT.md` mentionne seulement OpenAI comme dépendance runtime directe et ne documente pas l'extra Anthropic de calibration.

La configuration des chemins est portable et injectée, sans découverte disque globale. Les alias `PEDAGOGICAL_CANONICAL_SEED_PATH` et `PEDAGOGICAL_RUNTIME_DATABASE_PATH` sont encore actifs alors que le commentaire les annonce « jusqu'à B08 » ; leur coexistence avec les noms V2 reste fail-closed en cas de conflit.

Aucune recherche CVE web n'a été menée conformément au périmètre.

`DEPENDENCY_HYGIENE = PARTIAL`
