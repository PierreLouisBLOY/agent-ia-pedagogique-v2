# Projet V2 — Handoff final 12.17.7

```text
PHASE_12_17_07_PRIORITIZED_RATIONALIZATION_PLAN = PASS
BASELINE_HEAD = e2c43184a272491371b73131170db488cf3157d6
SOURCE_FINDINGS_TOTAL = 148
CANONICAL_FINDINGS_TOTAL = 30
DUPLICATES_OR_OVERLAPS_CONSOLIDATED = 118
OPEN_P0 = 0
OPEN_P1 = 1
OPEN_P2 = 5
OPEN_P3 = 3
CLOSED = 12
HISTORICAL_FINDINGS_COUNT = 4
LOCAL_ONLY_FINDINGS_COUNT = 1
DEFERRED_FINDINGS_COUNT = 4
P1_EXACT_FINDING = REPO-001 / CF-REPO-001
P1_DISPOSITION = OWNER_DECISION_REQUIRED_THEN_FIX_IN_12_17_8_B01
OWNER_DECISIONS_REQUIRED_COUNT = 2
MUST_FIX_BEFORE_12_18_COUNT = 8
OBSERVABILITY_REMEDIATION_ITEMS_COUNT = 12
SQLITE_HARDENING_ITEMS_COUNT = 7
DEPENDENCY_HYGIENE_ITEMS_COUNT = 5
GITIGNORE_GAPS_PLANNED_COUNT = 4
ORIGINAL_126_ITEMS_DISPOSITIONED = 126/126
PHASE_12_17_05C_EVIDENCE_ITEMS_DISPOSITIONED = 11/11
12_17_8_BATCH_COUNT = 7
FINAL_GLOBAL_GATES_COUNT = 16
CODE_OR_RULES_MODIFIED = 0
SQLITE_WRITES = 0
PROVIDER_CALLS = 0
STAGING_COMMIT_PUSH = NONE/NONE/NONE
12_17_8_ENTRY_GATE = BLOCKED_OWNER_DECISION
NEXT_RECOMMENDED_SUBSTEP = 12.17.7A_OWNER_DECISION_RESOLUTION
12_17_8_STARTED = FALSE
```

## Résultat

Les 148 occurrences sources sont couvertes exactement une fois et regroupées en 30 causes canoniques. Le seul P1 ouvert est la provenance de fichiers non suivis. Sa remédiation future porte, sans drift, sur une allowlist de 165 chemins : 126 hérités, 11 preuves 12.17.5C, 15 preuves 12.17.6 et les 13 présents artefacts 12.17.7.

Huit findings doivent être fermés avant 12.18 : provenance, observabilité, contrat HTTP loopback, frontière filesystem, durcissement SQLite, lock reproductible, déterminisme des temporaires et quatre familles `.gitignore`. LEGACY-001 et DOC-001 sont inclus dans B05 mais restent non bloquants pris isolément.

La dette mypy `15/10`, l'attribution historique des sidecars, l'écart B01 et la documentation historique dupliquée sont explicitement historiques. `ContextOrigin`, CAP-R02, CAP-A01 et CAP-A02 restent différés; aucun placeholder ni sémantique de stockage n'est inventé.

Deux décisions propriétaires sont nécessaires avant 12.17.8 : traitement des cinq preuves contenant des chemins privés, et destination/rétention de l'observabilité. Les options et recommandations sont préparées dans `03_P1_DECISION_ANALYSIS.md`, `04_MINIMUM_OBSERVABILITY_PLAN.md` et `11_12_17_8_ENTRY_GATE.md`.

## Invariants respectés

- aucune remédiation, modification code/config/SQLite ou changement de règle ;
- aucune base, sidecar, sortie runtime ou secret ajouté ;
- aucun appel ou credential fournisseur ;
- aucun staging, commit, push, merge ou suppression ;
- frontières Phases 6/11 et séparation génération/validation/évaluation/promotion inchangées ;
- 12.17.8 n'a pas commencé.
