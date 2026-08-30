# Phase 12.16-G2-R3B-R4-R3-R1 — Baseline de reprise HTTP 503

## Résultat offline

- Statut : `PASS_CLOSED`.
- Classification : `HTTP_503_SERVER_ERROR`.
- Appels provider R1 : `0` ; coût provider R1 : `0.000000 USD`.
- Le record R3 échoué et tous les artefacts R2/R3 restent inchangés.

## Preuves gelées

- R2 ledger : `ef694ad8174a28079db030086d83d0ffb8d02d7aed598092961b821b3fdd2a31`.
- R2 summary : `ec88b72b616793bd4d215ec1f4a5e24a03b458691e1b00ce7491b4f6486d5948`.
- R2 raw : `a16287401cc87863d23dc170b76cf2983ccae1909374d2a3b6af8226642f6053`.
- R3 ledger : `bd4f9272730c225a7e1a309137cf937bcb0b8a9603446cc76c8d94871a029c99`.
- R3 summary : `c3052b33193bf6542cd96a2ff1706c8d210e297c736d1d3ffa101676c9405729`.
- R3 transfer manifest : `c8742f5e4a46215a34141e93b17b36a730c6ab6136b3c92ad3eba073be1e905a`.
- R3 raw ordered-list : `f39d83334eda6b0f87b4ecf363e9f432d818b298d55defa6c1076ec766a34c52`.

## Consolidation et soustraction

- Résultats homogènes réutilisables : `38` (`1 R2 + 37 R3`).
- Manifest réutilisable : `555486d2fe968d347e72ab378b4b0370dac48bb40921756993699f1fbf412566`.
- Slots : `76 - 38 = 38` ; union `76`.
- Split restant : `10 initial / 16 repeatability / 12 selected-output`.
- Transfert futur : `26 ANCHOR_SYNTHETIC / 12 AUTHORIZED_OUTPUT_PROJECTION`.
- Dépendances selected-output : `6/6` vérifiées par hash.

## Plan rationalisé

- Version : `12.16-g2-r4-r4-anthropic-recovery-completion-v1`.
- Checksum : `8cdc7c5b1ed6eaeb02606b2130db43d398bdbe51d99116d97014cb014e8b3526`.
- Calls : `38` ; canary puis `37` continuations.
- Canary : `remediation.r4-r3.http503.scn-07.b.correction-quality.canary.r1`.
- Policy : `claude-sonnet-5 / adaptive / low / 2048 / retry 0`.
- Un échec technique du canary bloque les calls 2–38 avant provider.
- Tout échec technique ultérieur suspend avant l'appel suivant.
- Maximum sans marge : `1.386240 USD`.
- Plafond demandé : `1.732800 USD`.

## Gouvernance

- Le futur runner doit vérifier le statut public Anthropic avant credential/canary.
- Les nouvelles autorisations liées au checksum sont obligatoires.
- ADR supplémentaire : `NO`; ADR-P12-063 et ADR-P12-064 s'appliquent.
- Revue humaine finale toujours requise.
