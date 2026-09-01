# Phase 12.16-G2-V5.2.1 — État de la gate live

## Configuration gelée

- Observations logiques : `5`.
- Carry-forward : `2`.
- Nouveaux appels : `3`.
- Provider futur : `ANTHROPIC_ONLY`.
- Plafond : `0.156800 USD`.
- Appels OpenAI : `0`.

Après réussite du commit et des contrôles post-commit, la gate d'autorisation live
est prête à recevoir une décision distincte. Elle demeure fermée dans ce lot.

Une future autorisation devra citer le SHA complet du commit de gel et le manifeste
du présent paquet. Elle devra conserver les deux carry-forward sans appel ni
retransmission et limiter l'exécution aux trois appels Anthropic allowlistés, sans
retry, rerun, fanout ou dépassement de plafond.

```text
LIVE_MINI_PILOT_AUTHORIZATION_GATE = READY_AFTER_COMMIT
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
```
