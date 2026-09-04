# Phase 12.17.5A-OD — Binding du registre décisionnel

## Identités vérifiées

```text
BASELINE_COMMIT = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
OWNER_DECISION_REGISTER_PATH = docs/development/phase_12_17_05a_blocking_remediation_design/05_OWNER_DECISION_REGISTER.json
OWNER_DECISION_REGISTER_SHA256 = f987ce8a601275630bf2ec0298eb2c868d38411b3fad88d6e44082e3102551d1
OWNER_DECISION_COUNT = 3
BLOCKING_FINDINGS_COUNT = 5
BLOCKERS_REQUIRING_OWNER_DECISION_COUNT = 4
```

Le commit courant correspond exactement au commit de référence. Le registre JSON est valide et porte les trois décisions `DM-01`, `DM-02` et `DM-03`, toutes encore à `AWAITING_OWNER` avec `owner_selection = null`.

## Objet du binding

Une future attestation propriétaire n'est valable que si elle reprend simultanément :

- le commit de baseline ci-dessus ;
- le SHA-256 exact du registre ;
- une option explicite et existante pour chacune des trois décisions ;
- l'identité ou le rôle de l'owner ;
- un timestamp d'attestation.

Toute modification du registre ou tout changement de baseline invalide ce paquet et impose un nouveau calcul de binding. Les recommandations documentées ne préremplissent aucune sélection.

## Preuve de gate

```text
PHASE_12_17_05A_BLOCKING_REMEDIATION_DESIGN = PASS
OWNER_DECISIONS_RESOLVED = 0/3
12_17_05B_ENTRY_GATE = BLOCKED_OWNER_DECISIONS
```
