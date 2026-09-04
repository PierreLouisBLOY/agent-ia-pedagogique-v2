# Phase 12.17.7A — Binding des sources de décision

## Identités d'entrée

```text
PHASE_12_17_07_PRIORITIZED_RATIONALIZATION_PLAN = PASS
12_17_8_ENTRY_GATE = BLOCKED_OWNER_DECISION
BASELINE_COMMIT = e2c43184a272491371b73131170db488cf3157d6
PHASE_12_17_07_MANIFEST_SHA256 = 937644fb779b6b860e7d677a3b17c1065feabbb7723e48017fc0b74a1893db8b
DECISION_COUNT = 2
```

## Manifest de binding dédié

Les deux décisions dépendent de plusieurs documents. Le présent fichier est l'autorité agrégée : son SHA-256 devient `OWNER_DECISION_SOURCE_SHA256`. Il ne contient volontairement pas son propre hash afin d'éviter une identité circulaire.

| SHA-256 | Source liée | Rôle |
|---|---|---|
| `303b784122d98f6fbd6e0d67bed5f8d45ec7c93e67f15d20617cc4c63538fb72` | `docs/development/phase_12_17_07_prioritized_rationalization_plan/03_P1_DECISION_ANALYSIS.md` | options, impacts et remédiation REPO-001 |
| `20f840570d8a4e84c0467df9607c13e345ce3a24e2857256f41b21c0536e438f` | `docs/development/phase_12_17_07_prioritized_rationalization_plan/09_12_17_8_BATCH_EXECUTION_PLAN.md` | lots B01/B03, tests, rollback et gates |
| `c199e15a84cbb2e7804efa98f5ee040b9b31c6dd5a7d58cc70945adf56f7badb` | `docs/development/phase_12_17_07_prioritized_rationalization_plan/11_12_17_8_ENTRY_GATE.md` | vocabulaire exact des quatre options et blocage |
| `d51884e1f194cd775a2ae32ea2732b9f38880d4c83778502f3315506871b0f0e` | `docs/development/phase_12_17_07_prioritized_rationalization_plan/12_FINAL_HANDOFF.md` | statut, counts et invariants |
| `03c13b1bfd557f1d8803e4379f43317104f52af519f920055442579fa17e7693` | `docs/development/phase_12_17_07_prioritized_rationalization_plan/02_CANONICAL_FINDINGS_REGISTER.json` | CF-REPO-001, CF-OBS-001 et critères d'acceptation |

## Vocabulaire de décision exact

```text
REPO_EVIDENCE_DECISION = OPTION_A_MINIMIZE_FIVE_AND_CONSOLIDATE_165
REPO_EVIDENCE_DECISION = OPTION_B_BYTE_EXACT_CONSOLIDATE_165

OBSERVABILITY_DECISION = OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S
OBSERVABILITY_DECISION = OBS_B_NATIVE_OS_FACILITY_REQUIRES_DETAILED_DESIGN
```

Une seule valeur par famille peut apparaître dans l'attestation propriétaire.

## Rebind cardinalité B01

Le suffixe `165` des deux options REPO est le vocabulaire exact figé à la fin de 12.17.7. La création obligatoire des sept artefacts 12.17.7A augmente mécaniquement l'inventaire futur, sans drift de contenu antérieur :

```text
PRE_PACKET_UNTRACKED_COUNT = 165
OWNER_PACKET_NEW_ARTIFACT_COUNT = 7
POST_PACKET_EXPECTED_UNTRACKED_COUNT = 172
B01_EFFECTIVE_ALLOWLIST_COUNT = 172
```

L'option choisit donc la stratégie figée par son nom exact; le futur rebind d'entrée B01 doit approuver une allowlist de 172 chemins si aucun autre drift n'intervient. Tout autre total bloque B01. Ce paquet ne stage ni ne modifie aucun de ces éléments antérieurs.

## Invariants du binding

- aucune option n'est pré-approuvée ;
- aucune décision n'est appliquée ;
- aucune suppression, minimisation, rotation de log ou modification de configuration n'est effectuée ;
- aucun accès SQLite, fournisseur, credential, staging, commit ou push.
