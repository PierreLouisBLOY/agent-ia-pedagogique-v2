# Phase 12.17.3 — Catalogue des sources de règles métier

## Méthode et granularité

L'audit couvre les règles stables et les occurrences d'autorité observables dans le dépôt au commit `6d0d66380757d7502fd967cd0246c5b6ff91d5f8`. Une règle brute représente une obligation, une interdiction, une transition ou une exception vérifiable; les simples gardes de type répétées à l'intérieur d'un même constructeur ne sont pas décomposées artificiellement.

Aucune fusion n'est appliquée dans le registre brut. Les formulations proches conservent des IDs distincts et sont reliées par `duplicate_group` ou `overlap_cluster`.

## Recensement

| Source | Volume observé | Autorité et usage |
| --- | ---: | --- |
| ADR acceptés | 67 | Décisions architecturales durables des Phases 12.2–12.16. |
| Documents top-level `docs/development` | 149 | Baselines, contrats et clôtures versionnées. |
| Dossiers de phase documentaires | 39 | Preuves, manifests et handoffs, surtout 12.16–12.17. |
| Fichiers Python backend non-`__init__` | 221 | Contrats, policies, runtime et adapters exécutables. |
| Implémentations concrètes sous `backend/modules` | 5 | Toutes appartiennent à Resource Library / READ-15. |
| Implémentations API HTTP sous `backend/adapters/inbound/api` | 0 | Surface `/api/v2` non matérialisée. |
| Helpers de calibration | 50 fichiers Python | Tooling/test versionné, jamais autorité runtime. |
| Tests Python | 412 | Preuves explicites ou structurelles. |
| Migration SQL locale | 1 | Contrainte documentaire SHA-256; le DDL initial reste externe. |
| Corpus canoniques Phase 1/2 présents | 0 | Preuve canonique externe requise. |
| TODO/FIXME/XXX exécutables | 0 | Les deux occurrences textuelles sont documentaires, non autoritatives. |

## Hiérarchie d'autorité appliquée

1. décisions propriétaire et handoffs finaux explicitement canoniques;
2. ADR acceptés et clôtures de phase;
3. baselines/contrats de développement de la phase la plus récente;
4. contrats Domain/Application et policies runtime exécutables;
5. adapters comme traduction, jamais comme nouvelle autorité métier;
6. tests comme preuve;
7. commentaires et noms comme indices uniquement.

Un document historique n'est pas supprimé : il est classé `LEGACY/HISTORICAL` lorsqu'un document plus récent le supersède explicitement.

## Clusters de sources inventoriés

| Source ID | Zone | Règles couvertes |
| --- | --- | --- |
| `SRC-01` | `README.md`, `AGENTS.md` | Non-héritage, réutilisation auditée, priorité canonique, hygiène Git. |
| `SRC-02` | ADR 001–010 et docs runtime 12.3–12.10 | Contrats, versioning, workflows, permissions et routage. |
| `SRC-03` | Resource Library Domain/Application/inbound | READ-15, payload, résultat et erreur métier. |
| `SRC-04` | Adapters SQLite, migration 001, composition | Seed, migrations, transactions, stores et mapping. |
| `SRC-05` | Policy/registry/tool/gate/sandbox | Séparation d'autorité et fail-closed. |
| `SRC-06` | Recovery/runtime state | Effets, replay, budget, snapshots, circuit breaker. |
| `SRC-07` | Security | Trust, isolation, exfiltration et multi-agent. |
| `SRC-08` | Observability | Minimisation, propagation et isolation des sinks. |
| `SRC-09` | Evidence/Generation/Review | Responsabilités agentiques séparées et sorties sans autorité. |
| `SRC-10` | Evaluation harness | Évaluation offline distincte du runtime et de la promotion. |
| `SRC-11` | Golden corpus 12.15 | Scénarios synthétiques, assertions et workflows. |
| `SRC-12` | Calibration 12.16 et clôture | Strong-only, contrôles négatifs, live borné, seuil absent. |
| `SRC-13` | API projetée / modules scaffoldés | Contrats exposables et implémentations absentes. |
| `SRC-14` | Schéma canonique Phase 3 externe | 98 tables signalées; aucune inférence de DDL. |
| `SRC-15` | Corpus métier consolidé Phases 1/2 externe | Source demandée mais absente du dépôt. |
| `SRC-16` | Tests unit/intégration/architecture | Mapping de preuve des règles. |
| `SRC-17` | Manifests et handoffs | Identités, exceptions et états finaux. |
| `SRC-18` | Commentaires/TODO | Indices seulement; aucune autorité autonome trouvée. |

## Limites fermées

- Le schéma SQLite des 98 tables n'est pas reconstitué depuis les requêtes.
- L'absence des corpus Phase 1/2 est signalée, pas compensée par une invention.
- Les adapters ne sont pas promus au rang de Domain owner.
- Les règles de calibration sont séparées des règles de délivrabilité runtime.
- Aucun fichier source n'est modifié par cet audit.
