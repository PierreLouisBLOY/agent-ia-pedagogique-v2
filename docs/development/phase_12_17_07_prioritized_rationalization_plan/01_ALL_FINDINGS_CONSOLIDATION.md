# Phase 12.17.7 — Consolidation exhaustive des findings

## Méthode

Le registre ci-dessous consolide les registres de findings, erreurs et résiduels de 12.17.1 à 12.17.6. Les registres de décisions propriétaires sont utilisés comme preuves de transition d'état, mais ne sont pas recomptés comme findings. Chaque ligne source est affectée à un seul finding canonique afin d'éviter tout double comptage.

```text
SOURCE_FINDINGS_TOTAL = 148
CANONICAL_FINDINGS_TOTAL = 30
DUPLICATES_OR_OVERLAPS_CONSOLIDATED = 118
SOURCE_COVERAGE = 148/148
UNMAPPED_SOURCE_FINDINGS = 0
```

États normalisés : `CLOSED`, `OPEN`, `HISTORICAL`, `LOCAL_ONLY`, `DEFERRED`. `SUPERSEDED_CLOSED` signifie que le constat source a été fermé ou remplacé par une preuve plus récente.

## Registre source → canonique

| Source | ID source | Description condensée | État actuel | Groupe doublon/overlap | ID canonique |
|---|---|---|---|---|---|
| 12.17.1 | TYP-001 | Le graphe mypy backend est propre mais le parcours historique expose 33 erreurs. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.1 | TYP-002 | Narrowing optionnel incomplet dans le scorer Anthropic historique. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.1 | TYP-003 | Cardinalité de tuple trop large dans quatre corpus versionnés. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.1 | TYP-004 | Collision de type dans `render_alignment_matrix`. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.1 | TYP-005 | Comparaisons sur budget `Decimal | None`. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.1 | TYP-006 | Valeur `object` hors union d'observation. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.1 | TYP-007 | Casts/ignore obsolètes dans les helpers historiques. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.1 | TYP-008 | Union de specs micro-canary/mini-pilot mal inférée. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.1 | BUS-001 | Modules métier majoritairement structurels. | DEFERRED | capability-ownership | CF-CAP-R02-DEFERRED-001 |
| 12.17.1 | BUS-002 | Autorité des règles répartie entre documents et code. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.1 | BUS-003 | Vocabulaires enum distribués. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.1 | BUS-004 | Groupes de validateurs homonymes. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.1 | ARC-001 | Aucun endpoint `/api/v2` concret. | OPEN | http-absent | CF-HTTP-001 |
| 12.17.1 | ARC-002 | Plusieurs générations de runners/parsers. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.1 | ARC-003 | Transport Anthropic opérationnel sous `tests/`. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.1 | ARC-004 | Deux implémentations pairwise complètes coexistent. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.1 | ARC-005 | Resource Library est le seul slice Application concret. | DEFERRED | capability-ownership | CF-CAP-R02-DEFERRED-001 |
| 12.17.1 | DAT-001 | DDL initial du seed externe au dépôt. | CLOSED | schema-authority | CF-SCHEMA-AUTHORITY-001 |
| 12.17.1 | DAT-002 | DDL technique créé hors migrations métier. | CLOSED | technical-ddl | CF-TECHNICAL-DDL-001 |
| 12.17.1 | DAT-003 | Stores génériques sans mapper métier hors Resource Library. | DEFERRED | capability-ownership | CF-CAP-R02-DEFERRED-001 |
| 12.17.1 | HYG-001 | Un JSON suivi sans LF final. | CLOSED | eof-normalization | CF-EOF-001 |
| 12.17.1 | HYG-002 | Sept Markdown avec exception EOL acceptée. | CLOSED | eof-normalization | CF-EOF-001 |
| 12.17.1 | HYG-003 | Deux documents byte-identiques. | HISTORICAL | historical-doc-duplication | CF-DOC-DUP-HIST-001 |
| 12.17.1 | HYG-004 | Accumulation locale d'artefacts et temporaires ignorés. | LOCAL_ONLY | temp-artifacts | CF-TEMP-LOCAL-001 |
| 12.17.1 | HYG-005 | Manifestes contrôlés sans anomalie. | CLOSED | false-positive | CF-FALSE-POSITIVE-001 |
| 12.17.1 | SEC-001 | Frontières SQL/fournisseur conformes. | CLOSED | false-positive | CF-FALSE-POSITIVE-001 |
| 12.17.2 | MYPY-001 | Cast `str` redondant dans le transport historique. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-002 | Route fournisseur optionnelle non narrowée. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-003 | Profil modèle optionnel non narrowé. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-004 | Profil fournisseur optionnel passé comme requis. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-005 | Profil modèle optionnel passé comme requis. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-006 | `type: ignore` inutilisé. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-007 | Tuple de tiers non fixé à trois éléments. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-008 | Tuple de tiers V2 non fixé à trois éléments. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-009 | Tuple de tiers V3 non fixé à trois éléments. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-010 | Variable locale inférée avec le mauvais type. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-011 | Accès `tier` issu de la collision précédente. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-012 | Accès fingerprint V2 issu de la collision précédente. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-013 | Accès fingerprint V3 issu de la collision précédente. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-014 | Accès label humain issu de la collision précédente. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-015 | Accès `reuse_allowed` issu de la collision précédente. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-016 | Accès `reason` issu de la collision précédente. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-017 | Tuple de tiers V4 non fixé à trois éléments. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-018 | Comparaison budget optionnel, branche 1. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-019 | Comparaison budget optionnel, branche 2. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-020 | Valeur d'observation trop large. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-021 | Comparaison budget V4.1, branche 1. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-022 | Comparaison budget V4.1, branche 2. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-023 | Réexport implicite de `AnchorTier`. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2 | MYPY-024 | Cast `str` redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-025 | Cast `Decimal` redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-026 | Cast `str` redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-027 | Cast `str` redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-028 | Cast `str` redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-029 | Cast `Decimal` redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-030 | Cast dictionnaire redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-031 | Cast dictionnaire redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-032 | Cast dictionnaire redondant. | CLOSED | typing-remediated | CF-TYPING-REMEDIATED-001 |
| 12.17.2 | MYPY-033 | Union de specs mal inférée. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-001 | Résiduel transport Anthropic. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-002 | Résiduel route fournisseur optionnelle. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-003 | Résiduel profil modèle optionnel. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-004 | Résiduel argument profil fournisseur. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-005 | Résiduel argument profil modèle. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-007 | Résiduel cardinalité corpus V1. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-008 | Résiduel cardinalité corpus V2. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-009 | Résiduel cardinalité corpus V3. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-017 | Résiduel cardinalité corpus V4. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-018 | Résiduel budget optionnel. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-019 | Résiduel budget optionnel. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-021 | Résiduel budget optionnel V4.1. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-022 | Résiduel budget optionnel V4.1. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-023 | Résiduel réexport implicite. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.2A | MYPY-033 | Résiduel union de specs. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.3 | BRF-001 | Source consolidée Phase 1/2 absente. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-002 | Trace `docs/legacy-review` absente. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-003 | Seul le slice READ-15 est concret. | DEFERRED | capability-ownership | CF-CAP-R02-DEFERRED-001 |
| 12.17.3 | BRF-004 | Endpoints `/api/v2` absents. | OPEN | http-absent | CF-HTTP-001 |
| 12.17.3 | BRF-005 | Neuf règles dépendaient du schéma externe. | CLOSED | schema-authority | CF-SCHEMA-AUTHORITY-001 |
| 12.17.3 | BRF-006 | Littéraux métier présents dans l'adaptateur. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-007 | Use cases propriétaires manquants pour plusieurs capacités. | DEFERRED | capability-ownership | CF-CAP-R02-DEFERRED-001 |
| 12.17.3 | BRF-008 | Règles de calibration versionnées à rationaliser. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.3 | BRF-009 | Deux groupes de doublons exacts. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-010 | Huit groupes de quasi-doublons. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-011 | Neuf clusters de chevauchement. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-012 | Validateurs homonymes à qualifier. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-013 | Vocabulaire enum distribué. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-014 | `version_ref` et `include` non implémentés. | OPEN | http-absent | CF-HTTP-001 |
| 12.17.3 | BRF-015 | Numérotation legacy incohérente. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-016 | Règles de calibration trop spécifiques. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.3 | BRF-017 | Index unique d'autorité absent. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-018 | Huit règles sans test explicite/structurel. | CLOSED | rule-authority | CF-BUSINESS-RULE-001 |
| 12.17.3 | BRF-019 | Aucun TODO exécutable réel. | CLOSED | false-positive | CF-FALSE-POSITIVE-001 |
| 12.17.3 | BRF-020 | Traçabilité data/API distribuée. | OPEN | http-absent | CF-HTTP-001 |
| 12.17.4 design | RAT-001 | Tooling Anthropic actif placé sous tests. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.4 design | RAT-002 | Dépendance active aux mécaniques historiques. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.4 design | RAT-003 | Sept hashes historiques supersédés. | HISTORICAL | historical-doc-duplication | CF-DOC-DUP-HIST-001 |
| 12.17.4 design | RAT-004 | Sept générations runner/parser. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.4 design | RAT-005 | Dette mypy résiduelle 15/10. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.4 design | SQLITE_SIDECAR_ATTRIBUTION_UNDETERMINED | Créateur historique WAL/SHM inconnu. | HISTORICAL | sidecar-attribution | CF-SIDECAR-HIST-001 |
| 12.17.4 design | RAT-007 | Chemin Desktop non portable. | CLOSED | sqlite-runtime-design | CF-SQLITE-DESIGN-001 |
| 12.17.4 design | RAT-008 | Besoin de migration de deux vocabulaires inconnu. | SUPERSEDED_CLOSED | active-canonical | CF-ACTIVE-CANONICAL-001 |
| 12.17.4 design | RAT-009 | Trace legacy requise absente. | CLOSED | sqlite-runtime-design | CF-SQLITE-DESIGN-001 |
| 12.17.4 design | RAT-010 | API `/api/v2` absente. | OPEN | http-absent | CF-HTTP-001 |
| 12.17.4 design | RAT-011 | ADR requis pour la nouvelle frontière. | CLOSED | calibration-rationalization | CF-CALIBRATION-ARCH-001 |
| 12.17.4 global | GATE-001 | Hash historique V1/V2 obsolète. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.4 global | GATE-002 | Hash historique V1/V2/V3 obsolète. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.4 global | GATE-003 | Hash prévalidation V2 obsolète. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.4 global | GATE-004 | Hash delta V3 obsolète. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.4 global | GATE-005 | Hash disposition V4 obsolète. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.4 global | GATE-006 | Hash unitaire corpus V2 obsolète. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.4 global | GATE-007 | Variable de seed canonique requise par la gate réelle. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.4 closure | RESOURCE_STATUS_ACTIVE_CANONICAL_UNKNOWN | Relation ACTIVE/CANONICAL inconnue. | SUPERSEDED_CLOSED | active-canonical | CF-ACTIVE-CANONICAL-001 |
| 12.17.4 closure | CONTEXT_ORIGIN_UNKNOWN | Sémantique d'origine du contexte inconnue. | DEFERRED | context-origin | CF-CONTEXT-DEFERRED-001 |
| 12.17.4 closure | HISTORICAL_MYPY_DEBT_15_10 | Dette mypy historique 15/10. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.4 closure | HISTORICAL_SEED_SIDECAR_CREATOR_UNKNOWN | Créateur historique des sidecars inconnu. | HISTORICAL | sidecar-attribution | CF-SIDECAR-HIST-001 |
| 12.17.4 closure | B01_NARRATIVE_VS_MACHINE_READABLE_FREEZE_GAP | Écart récit/freeze machine B01. | HISTORICAL | b01-freeze-gap | CF-B01-HIST-001 |
| 12.17.5 | DMAPI-001 | Migration 001 perd le CHECK de taille. | CLOSED | migration-invariants | CF-MIGRATION-001 |
| 12.17.5 | DMAPI-002 | Migration 001 perd quatre defaults. | CLOSED | migration-invariants | CF-MIGRATION-001 |
| 12.17.5 | DMAPI-003 | `resource_ref` non borné. | CLOSED | resource-ref | CF-RESOURCE-REF-001 |
| 12.17.5 | DMAPI-004 | ACTIVE/CANONICAL non résolu. | CLOSED | active-canonical | CF-ACTIVE-CANONICAL-001 |
| 12.17.5 | DMAPI-005 | `ContextOrigin` sans représentation persistée. | DEFERRED | context-origin | CF-CONTEXT-DEFERRED-001 |
| 12.17.5 | DMAPI-006 | CAP-R02 sans query concrète. | DEFERRED | capability-ownership | CF-CAP-R02-DEFERRED-001 |
| 12.17.5 | DMAPI-007 | CAP-A01 sans commande de validation concrète. | DEFERRED | capability-ownership | CF-CAP-A01-DEFERRED-001 |
| 12.17.5 | DMAPI-008 | CAP-A02 sans commande de promotion concrète. | DEFERRED | capability-ownership | CF-CAP-A02-DEFERRED-001 |
| 12.17.5 | DMAPI-009 | Tests de migration incomplets. | CLOSED | migration-invariants | CF-MIGRATION-001 |
| 12.17.5 | DMAPI-010 | Handoff API assigné à une phase audit-only. | OPEN | http-absent | CF-HTTP-001 |
| 12.17.5 | DMAPI-011 | Dette mypy historique 15/10. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.5 | DMAPI-012 | Créateur historique WAL/SHM inconnu. | HISTORICAL | sidecar-attribution | CF-SIDECAR-HIST-001 |
| 12.17.5 | DMAPI-013 | Écart historique B01 accepté. | HISTORICAL | b01-freeze-gap | CF-B01-HIST-001 |
| 12.17.5B | B07-GIT-GUARD-001 | Suite globale bloquée par du carry-forward non commité. | CLOSED | global-gate-remediation | CF-GIT-GLOBAL-GATE-001 |
| 12.17.5B | DMAPI-005 | `ContextOrigin` reste différé. | DEFERRED | context-origin | CF-CONTEXT-DEFERRED-001 |
| 12.17.5B | DMAPI-006 | CAP-R02 reste handoff-only. | DEFERRED | capability-ownership | CF-CAP-R02-DEFERRED-001 |
| 12.17.5B | DMAPI-007 | CAP-A01 reste handoff-only. | DEFERRED | capability-ownership | CF-CAP-A01-DEFERRED-001 |
| 12.17.5B | DMAPI-008 | CAP-A02 reste handoff-only. | DEFERRED | capability-ownership | CF-CAP-A02-DEFERRED-001 |
| 12.17.5B | DMAPI-011 | Dette mypy historique stable. | HISTORICAL | typing-historical | CF-MYPY-HIST-001 |
| 12.17.5B | DMAPI-012 | Créateur de sidecar historique inconnu. | HISTORICAL | sidecar-attribution | CF-SIDECAR-HIST-001 |
| 12.17.5B | DMAPI-013 | Écart B01 historique accepté. | HISTORICAL | b01-freeze-gap | CF-B01-HIST-001 |
| 12.17.6 | REPO-001 | 126 éléments historiques et 11 preuves 05C sont non suivis. | OPEN | repo-provenance | CF-REPO-001 |
| 12.17.6 | OBS-001 | Aucun sink persistant ni câblage lifecycle. | OPEN | observability-wiring | CF-OBS-001 |
| 12.17.6 | HTTP-001 | Contrat loopback futur non encodé. | OPEN | http-absent | CF-HTTP-001 |
| 12.17.6 | FILE-001 | Frontière filesystem concrète absente. | OPEN | filesystem-boundary | CF-FILE-001 |
| 12.17.6 | SQLITE-001 | Permissions/no-follow SQLite non durcis. | OPEN | sqlite-hardening | CF-SQLITE-HARDEN-001 |
| 12.17.6 | DEP-001 | Aucun lockfile ni hashes reproductibles. | OPEN | dependency-reproducibility | CF-DEPENDENCY-001 |
| 12.17.6 | TEMP-001 | Accumulation locale et scans contaminés. | LOCAL_ONLY | temp-artifacts | CF-TEMP-LOCAL-001 |
| 12.17.6 | GITIGNORE-001 | Quatre familles générées non ignorées. | OPEN | repository-hygiene | CF-GITIGNORE-001 |
| 12.17.6 | LEGACY-001 | Alias SQLite legacy toujours actifs. | OPEN | config-legacy | CF-LEGACY-001 |
| 12.17.6 | DOC-001 | Documentation Anthropic extra incomplète. | OPEN | dependency-doc | CF-DOC-001 |

## Résultat de déduplication

Les 118 lignes consolidées ne représentent pas 118 findings fermés : elles sont la différence arithmétique entre 148 occurrences sources et 30 causes canoniques. Les répétitions principales sont la dette mypy historique, les constats API absente, les capacités différées, les anomalies de migration déjà fermées et les preuves successives de mêmes états historiques.

Les huit décisions OD-01…OD-08 de 12.17.3C et les trois décisions DM-01…DM-03 de 12.17.5A sont toutes résolues et servent de preuves. Elles ne sont pas des findings supplémentaires.
