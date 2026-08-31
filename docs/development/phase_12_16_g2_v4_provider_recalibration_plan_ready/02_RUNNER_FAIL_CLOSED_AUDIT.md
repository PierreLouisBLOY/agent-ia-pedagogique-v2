# Phase 12.16-G2-V4 — Audit fail-closed du runner

L'audit du runner est statique. Le runner live et ses factories n'ont pas été invoqués.

## Protections présentes

| Protection | État |
|---|---|
| Checksum de matrice | Présente |
| Présence des deux credentials | Présente |
| Flag live explicite | Présente |
| Chemin de sorties brutes et `.gitignore` | Présente |
| Plafond approuvé | Présente |
| Ledger atomique | Présente |
| Identité et ordre des appels | Présente |
| Redaction des rapports | Présente |

## Protections absentes ou incomplètes

### 1. Baseline V4

`ENTRY_BASELINE_MISMATCH` est déclaré, mais `_validate_live_gates` ne compare ni le HEAD V4, ni le checksum du formulaire corrigé, ni le corpus V4, ni la clôture corrective. `V4_BASELINE_GUARD_BINDING = FAIL`.

### 2. Pricing

La matrice chiffre `claude-sonnet-5` à `3.00 / 0.30 / 15.00 USD/Mtok` (input/cache/output), tandis que le runner utilise `2.00 / 0.20 / 10.00`. Les plafonds calculés divergent :

```text
CALL_PLAN_MAXIMUM_WITH_MARGIN_USD = 4.096440
RUNNER_REVALIDATED_CEILING_USD = 3.093240
PRICING_CONSISTENCY_GUARD = FAIL
```

Le runner vérifie seulement que son propre calcul ne dépasse pas le plafond approuvé. Il ne compare pas sa table à celle de la matrice.

### 3. Canary

`SystemicCanaryBreaker` existe, mais le code ne l'instancie jamais. `LiveCalibrationRunner.run()` parcourt directement la matrice. `CANARY_BREAKER_RUNNER_INTEGRATION = FAIL`.

### 4. Métriques V4

Le rapport conserve le HEAD historique `413a61ad...`, indique `human_anchor_review = NOT_COMPLETED` et `_pairwise_quality()` renvoie toujours une collection vide. `V4_METRICS_AND_REPORT_BINDING = FAIL`.

## Décision

```text
RUNNER_EXISTING_SAFETY_CONTROLS = PARTIAL
IMPLEMENTATION_LIVE_READINESS = NO_GO
OFFLINE_AUDIT_PROVIDER_CALLS = 0
```

Le bundle reçu documente correctement le besoin de ces contrôles, mais il ne doit pas être interprété comme preuve que le runner les implémente déjà.
