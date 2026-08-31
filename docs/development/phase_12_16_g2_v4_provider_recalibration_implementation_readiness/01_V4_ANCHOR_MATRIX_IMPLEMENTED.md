# 12.16-G2-V4 — Matrice et protocole V4 implémentés

## Résultat

```text
V4_ANCHOR_MATRIX = PASS
PLAN_VERSION = 12.16-g2-v4-plan-v1
MATRIX_SHA256 = f159f200bf45d9df631007dd742e6ea9cc44a3e487ed76180f92c1392cd6245e
TOTAL_CALLS = 102
OPENAI_CALLS = 20
ANTHROPIC_CALLS = 82
```

- Les 24 IDs opaques de `V4_CALIBRATION_ANCHORS` sont couverts exactement.
- Les 48 scores initiaux et les 16 répétitions strong utilisent les autorités V4.
- Les tiers sont résolus par le mapping explicite `(scenario_code, tier) -> anchor`, jamais par suffixe d'ID.
- Les 18 scores d'outputs comprennent les 12 primaires historiques et les 6 fallbacks nécessaires à SCN-03, SCN-06 et SCN-07.
- `call_matrix_sha256()` inclut la version et le checksum du corpus V4 ainsi que l'identifiant et le checksum du snapshot pricing.
- Le protocole G1 historique est conservé ; le chemin V4 utilise exclusivement `V4_CALIBRATION_CRITERION_ITEMS` et `build_v4_blind_scorer_observation()`.

Fichiers principaux : `call_plan.py`, `protocol.py` et leurs tests unitaires. Aucun anchor V4 n'a été modifié.
