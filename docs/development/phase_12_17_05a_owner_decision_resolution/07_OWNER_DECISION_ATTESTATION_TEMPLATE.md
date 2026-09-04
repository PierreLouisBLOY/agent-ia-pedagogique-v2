# Phase 12.17.5A-OD — Attestation propriétaire vierge

Copier le bloc ci-dessous et remplacer chaque placeholder. Les recommandations ne sont volontairement pas préremplies.

```text
OWNER_DECISION_RESOLUTION_12_17_05A = APPROVED
BASELINE_COMMIT = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
OWNER_DECISION_REGISTER_SHA256 = f987ce8a601275630bf2ec0298eb2c868d38411b3fad88d6e44082e3102551d1

DM-01 = <OPTION_A|OPTION_B|OPTION_C>
DM-02 = <OPTION_A|OPTION_B|OPTION_C|OPTION_D>
DM-03 = <OPTION_A|OPTION_B|OPTION_C|OPTION_D>

OWNER_NAME_OR_ROLE = PROJECT_OWNER
OWNER_ATTESTATION = APPROVED
OWNER_ATTESTATION_TIMESTAMP = <ISO-8601 timestamp with timezone>
```

Une attestation incomplète, liée à une autre baseline/un autre SHA, ou utilisant une option absente du registre doit être rejetée fail-closed. Son application relèvera d'une sous-étape ultérieure; le présent paquet ne modifie pas le registre.
