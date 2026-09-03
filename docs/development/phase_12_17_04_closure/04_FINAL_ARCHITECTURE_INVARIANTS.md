# Phase 12.17.4 — Invariants d'architecture finaux

| Invariant | Preuve | Verdict |
|---|---|---|
| runner/parser actif unique | B02, graph actif et guards | PASS |
| adapter Anthropic actif hors `tests/` | `calibration_tooling/adapters/anthropic` | PASS |
| imports actifs vers historique | 0 | PASS |
| imports actifs vers `tests/providers` | 0 | PASS |
| composition, CLI et configuration injectées | B04/B07 | PASS |
| provider désactivé par défaut | B04 | PASS |
| autorité Application préservée | B09 API handoff | PASS |
| SQL/repository direct interdit à l'inbound | B09 guards | PASS |
| génération, validation, scoring et promotion séparés | contrats actifs | PASS |
| graphe mypy actif | 0/42 | PASS |
| backend mypy | 0/671 | PASS |
| dette historique isolée | 15 erreurs / 10 fichiers | STABLE |

```text
PROVIDER_CALLS = 0
CREDENTIAL_RESOLUTIONS = 0
NEW_MYPY_DIAGNOSTICS = 0
FUNCTIONAL_CHANGES_IN_CLOSURE = 0
```

La valeur 42 est le compte réellement mesuré : 27 fichiers
`calibration_tooling`, 10 tests unitaires, 4 tests d'intégration et 1 guard
d'architecture. Le compte antérieur de 41 était documentaire seulement.
