# Phase 12.16-G2-V5.2 — Préparation de la gate live

## Gouvernance liée au gel

```text
OWNER_V5_2_MINI_PILOT_APPROVAL = APPROVED
APPROVED_V5_2_MINI_PILOT_CEILING_USD = 0.156800
PEDAGOGICAL_TRANSFER_AUTHORIZED_FOR_V5_2_MINI_PILOT = TRUE
AUTHORIZED_LOGICAL_OBSERVATION_COUNT = 5
AUTHORIZED_CARRY_FORWARD_COUNT = 2
AUTHORIZED_NEW_CALL_COUNT = 3
AUTHORIZED_PROVIDER = ANTHROPIC_ONLY
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
```

## Sémantique fail-closed

Après réussite d'un futur commit correctif et de ses contrôles post-commit, la gate
d'autorisation live pourra devenir `READY`, mais restera fermée. Une future
autorisation live devra citer le SHA
complet du commit de gel et l'identité de ce manifeste, en plus des hashes parser,
scorer, matrice, pricing, gate, scope, trois call-specs et trois projections.

Les deux carry-forward Strong et Mixed doivent être réutilisés sans appel ni
retransmission. Trois nouveaux appels Anthropic au maximum sont possibles après
autorisation live distincte. Tout appel OpenAI, quatrième appel, retry, rerun,
fanout, dérive de payload ou dépassement de `0.156800 USD` doit fermer la gate.

```text
LIVE_MINI_PILOT_AUTHORIZATION_GATE = NOT_READY
BASELINE_GIT_FREEZE = NO_GO_VALIDATION
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
```
