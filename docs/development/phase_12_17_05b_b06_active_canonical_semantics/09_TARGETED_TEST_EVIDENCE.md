# Phase 12.17.5B-B06 — Preuves de tests ciblés

| Sélection | Résultat |
|---|---:|
| sémantique, mapper, Application, READ-15 et architecture B06 | `60/60 PASS` |
| gates SQLite réelles Resource et runtime | `19/19 PASS` |
| sélection consolidée B02 à B06 | `111/111 PASS` |

La sélection consolidée couvre notamment : indépendance typée des dimensions,
`UNKNOWN` explicite, rejet des combinaisons non autorisées, round-trip des deux
valeurs legacy, refus des encodages avec perte, absence de canonicalité inventée
dans READ-15, OP-12, 1 399 lignes runtime, immutabilité du seed, chaîne de
migrations `001 -> 002`, recovery et contrat `ResourceRef`.

Le premier essai SQLite réel, lié à un alias `G:` inaccessible, est un écart
d'environnement clos. La commande finale explicitement liée au seed authentifié
est l'autorité de résultat.

```text
TARGETED_TESTS = 111/111 PASS
REAL_SQLITE_TESTS = 19/19 PASS
FAILED_PRODUCT_TESTS_FINAL = 0
PROVIDER_TEST_CALLS = 0
```
