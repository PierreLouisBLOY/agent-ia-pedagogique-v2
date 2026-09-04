# Phase 12.17.5B-B03 — Fresh, existing et replay

| Parcours | Résultat |
|---|---|
| fixture seed fraîche → `001` → `002` | PASS, `applied=(001,002)` |
| runtime temporaire déjà à `001` → `002` | PASS, `skipped=(001)`, `applied=(002)` |
| runtime complet `001+002` → replay | PASS, `applied=()`, `skipped=(001,002)` |
| copie temporaire du seed réel → `001` → `002` | PASS |

Le provisionnement existant accepte toujours le chemin historique de `001`; ce chemin construit maintenant le registre approuvé complet. Un registre explicite reste également supporté.

```text
FRESH_001_TO_002 = PASS
EXISTING_001_TO_002 = PASS
REPLAY_001_002 = NO_OP_PASS
LEDGER_ORDER = 001,002
```
