# Phase 12.17.4E-B03 — Implémentations Anthropic historiques

## Inventaire opérationnel

Deux implémentations provider opérationnelles restent mal placées et protégées :

| Rôle | Chemin historique | SHA-256 B01 | Modification B03 |
|---|---|---|---|
| transport | `tests/providers/anthropic/transport.py` | `15ecf4b27ac8840dc503201864614a304917d3d43132b159da6a520044787b5b` | NONE |
| scorer | `tests/providers/anthropic/scorer.py` | `3be22f3a4ee19a3e2095f52f459b30d0b204a7e37437b2e5b33ab0ee03a76119` | NONE |

Les contrats et le mapping historiques du même dossier restent eux aussi dans
le registre B01 et n'ont pas été modifiés.

## Stratégie

B03 n'effectue ni déplacement, ni copie octet-à-octet, ni réexport. Le nouvel
adapter applique seulement les invariants durables : sortie structurée stricte,
blind scoring, adaptive thinking explicite à effort low lorsque configuré,
borne de sortie explicite, zéro retry, erreurs fermées et absence de contenu de
raisonnement conservé.

```text
HISTORICAL_ANTHROPIC_IMPLEMENTATIONS = 2
HISTORICAL_ANTHROPIC_FILES_MODIFIED = 0
ACTIVE_IMPORTS_TO_HISTORICAL_ANTHROPIC = 0
```
