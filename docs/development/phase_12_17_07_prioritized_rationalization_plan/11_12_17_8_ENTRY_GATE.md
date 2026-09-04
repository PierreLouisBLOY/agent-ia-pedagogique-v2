# Phase 12.17.8 — Gate d'entrée

## Vérification de 12.17.7

```text
PHASE_12_17_06_SECURITY_OBSERVABILITY_HYGIENE_AUDIT = PASS
12_17_7_ENTRY_GATE = READY
HEAD = e2c43184a272491371b73131170db488cf3157d6
PHASE_12_17_06_MANIFEST_SHA256 = 23f6f6ce1cfabbfe7c9aa24ccafdd04a500737a83b0cd0ff6218844b3219049e
SOURCE_FINDINGS_COVERAGE = 148/148
CANONICAL_FINDINGS = 30
PLAN_BATCHES = 7
FINAL_GATES = 16
PLAN_COMPLETE = TRUE
```

## Décisions propriétaires bloquantes

Deux décisions affectent matériellement l'implémentation et ne sont pas inférables :

1. `OWNER_REPOSITORY_PROVENANCE_DISPOSITION` :
   - `OPTION_A_MINIMIZE_FIVE_AND_CONSOLIDATE_165` — recommandée ;
   - `OPTION_B_BYTE_EXACT_CONSOLIDATE_165`.
2. `OWNER_OBSERVABILITY_DESTINATION_POLICY` :
   - `OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S` — recommandée ;
   - `OBS_B_NATIVE_OS_FACILITY_REQUIRES_DETAILED_DESIGN`.

La première bloque B01 et donc toute la séquence. La seconde bloque B03; comme le plan impose une exécution ordonnée et une baseline propriétaire unique, elle est demandée avant l'ouverture globale de 12.17.8.

## Forme d'attestation attendue

```text
OWNER_12_17_8_ENTRY_DECISIONS = APPROVED
BASELINE_COMMIT = e2c43184a272491371b73131170db488cf3157d6
PHASE_12_17_07_MANIFEST_SHA256 = <sha256 du manifest produit>
OWNER_REPOSITORY_PROVENANCE_DISPOSITION = <OPTION_A...|OPTION_B...>
OWNER_OBSERVABILITY_DESTINATION_POLICY = <OBS_A...|OBS_B...>
OWNER_NAME_OR_ROLE = <role>
OWNER_ATTESTATION_TIMESTAMP = <ISO-8601 avec fuseau>
```

Une approbation de plan seule ne constitue ni une autorisation de suppression, ni une autorisation de push/merge, ni une autorisation fournisseur, ni une autorisation d'écriture SQLite utilisateur/seed.

`12_17_8_ENTRY_GATE = BLOCKED_OWNER_DECISION`

Prochaine sous-étape recommandée : `12.17.7A_OWNER_DECISION_RESOLUTION`, puis rebind du manifest exact avant B01. Ne pas commencer 12.17.8.
