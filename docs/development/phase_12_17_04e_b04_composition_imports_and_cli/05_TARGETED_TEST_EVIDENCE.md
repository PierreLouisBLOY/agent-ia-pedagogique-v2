# Phase 12.17.4E-B04 — Validations ciblées

La commande ciblée B02+B03+B04 a exécuté 80 tests : contrats et runner,
adapter Anthropic, composition, observabilité, CLI et guards d'architecture.

Les scénarios B04 vérifient notamment :

- composition complète avec un client fake injecté et exactement un appel ;
- provider désactivé par défaut ;
- dépendances et secret obligatoires si live est explicitement activé ;
- allowlist invalide et budget insuffisant bloqués avant le client ;
- ledger ambigu bloqué avant le client ;
- absence de retry si le sink de télémétrie échoue ;
- CLI strictement injecté et sortie technique bornée ;
- mapping de télémétrie sans contenu ni secret.

```text
TARGETED_TESTS = 80/80 PASS
ARCHITECTURE_GUARDS = 22/22 PASS
ACTIVE_MYPY = 0/39 PASS
BACKEND_MYPY = 0/659 PASS
HISTORICAL_MYPY = 15 errors / 10 files STABLE
RUFF_CHANGED = PASS
RUFF_GLOBAL = PASS
COMPILEALL_BACKEND_CALIBRATION_TOOLING = PASS
GIT_DIFF_CHECK = PASS
```

La suite globale n'est pas prescrite par B04 et n'a pas été exécutée. Aucun
test n'a utilisé le réseau, un provider réel, un credential résolu ou SQLite.
