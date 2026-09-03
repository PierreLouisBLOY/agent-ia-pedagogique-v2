# Phase 12.17.4E-B07 — Tests ciblés

```text
B07_DIRECT_TESTS = 22/22 PASS
CUMULATIVE_B01_B07_TARGETED = 146 PASS, 18 SKIP
ARCHITECTURE_FINAL = 42/42 PASS
FAILED = 0
```

Les tests B07 simulent Windows, Linux/XDG, le fallback HOME et macOS. Ils
couvrent également les valeurs vides ou relatives, les conflits new/legacy,
les valeurs identiques compatibles, les collisions seed/runtime, l'identité
physique via hardlink, la non-divulgation des chemins et la composition par
mapping injecté.

Les 18 skips sont déclarés, pas convertis en PASS : 17 appartiennent à
`test_sqlite_runtime_real_gate.py` et un à
`test_sqlite_resource_application_e2e_real_gate.py`. Leur seed conditionnel
n'était pas configuré, conformément au scope B07. La validation réelle est
réservée à B08.

La suite globale de `ENVIRONMENT.md` reste la gate finale après les neuf
batches ; elle n'est pas anticipée par B07.
