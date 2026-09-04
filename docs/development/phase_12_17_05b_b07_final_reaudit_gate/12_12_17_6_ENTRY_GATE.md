# Phase 12.17.5B-B07 — Décision de gate 12.17.6

Les cinq blockers initiaux sont fermés, READ-15 est aligné, le handoff API et
la couverture des 28 contrôles atteignent 100 %, et les ciblages métier sont
verts. Toutefois, la validation globale exigée par le plan B07 conserve un
échec.

Le blocker exact est `B07-GIT-GUARD-001` : huit chemins B05/B06 approuvés sont
comparés à l'ancien `HEAD` par un guard historique. La résolution requiert une
décision explicite hors de l'autorité de B07 : soit autoriser la consolidation
exacte B02→B07, soit approuver un redesign versionné du guard. La suite globale
doit ensuite être rejouée.

```text
PHASE_12_17_05B_EXECUTION = INCOMPLETE
PHASE_12_17_05 = BLOCKED
12_17_6_ENTRY_GATE = BLOCKED
BLOCKING_FINDINGS_COUNT = 1
EXACT_BLOCKER = B07-GIT-GUARD-001
NEXT_RECOMMENDED_SUBSTEP = OWNER_AUTHORIZED_CONSOLIDATION_OR_VERSIONED_GUARD_REDESIGN
12_17_6_STARTED = FALSE
```
