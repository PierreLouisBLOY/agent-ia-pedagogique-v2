# Phase 12.17.1 — Inventaire des sources de règles métier

## Méthode

Une « source » désigne ici un cluster d'autorité ou d'implémentation, pas chaque fonction auxiliaire. Dix-huit clusters stables ont été catalogués. Les packages Domain vides ne sont pas comptés comme sources exécutables.

| Identifiant | Source | Localisation principale | Nature de règle |
| --- | --- | --- | --- |
| `BR-SRC-001` | Baselines canoniques | `docs/development/PHASE_*.md` et dossiers de phase | Décisions, non-objectifs, identités et invariants historiques. |
| `BR-SRC-002` | ADR | `architecture/adr/` (`67` ADR) | Frontières durables et décisions d'autorité. |
| `BR-SRC-003` | Resource Library Application | `backend/modules/resource_library/application/queries/get_resource.py` | READ-15, résultat nominal et `RES_NOT_FOUND`. |
| `BR-SRC-004` | Bridge inbound Application | `backend/adapters/inbound/application/resource_library.py` | Payload exact, use-case ID et projection C-12/C-13. |
| `BR-SRC-005` | Ports et DTO Resource | `backend/modules/resource_library/{ports,application/dto}` | Références et champs non vides, contrat OP-03/IP-03. |
| `BR-SRC-006` | Stores SQLite | `backend/adapters/outbound/persistence/sqlite.py` | Valeurs par défaut, statuts, concurrence et mapping des neuf stores. |
| `BR-SRC-007` | Migration documentaire | `database/migrations/001_document_sha256_check.sql` | Contrainte SHA-256 et conservation du schéma `document`. |
| `BR-SRC-008` | Autorisation des capabilities | `backend/agent_runtime/policy/` et `registry/access_matrix.py` | Allow/request/deny, délégation, owner et plafond de capability. |
| `BR-SRC-009` | Gates | `backend/agent_runtime/gates/` | Autorité, expiration, résolution et fail-closed. |
| `BR-SRC-010` | Sandbox | `backend/agent_runtime/sandbox/` | Classification de chemin et opérations autorisées. |
| `BR-SRC-011` | Isolation/sécurité du contenu | `backend/agent_runtime/security/` | Frontières instruction/donnée, signaux et exfiltration. |
| `BR-SRC-012` | Recovery | `backend/agent_runtime/recovery/` | Retry, budget, circuit breaker, idempotence, replay et snapshots. |
| `BR-SRC-013` | Planification et état runtime | `backend/agent_runtime/runtime/` | États terminaux, dépendances, prélaunch et transitions. |
| `BR-SRC-014` | Configuration fournisseur | `backend/infrastructure/config/` | Schémas fermés, limites, routes et références de credentials. |
| `BR-SRC-015` | Generation Guard | `backend/agent_runtime/agents/generation/` | Claims, réparations et refus de génération. |
| `BR-SRC-016` | Review Security | `backend/agent_runtime/agents/review/` | Locators, signaux, disposition et matérialisation de review. |
| `BR-SRC-017` | Evidence/Retrieval | `backend/agent_runtime/agents/evidence/` | Couverture, expansion, canaux et sécurité de preuve. |
| `BR-SRC-018` | Calibration V2–V5.2.4 | `tests/calibration/pedagogical/` (`50` fichiers) | Anchors, matrices, budgets, parser, score et pairwise. |

## Indicateurs de dispersion

- `172` classes d'enum dans `89` fichiers backend; aucun nom de classe enum strictement dupliqué n'a été trouvé.
- `156` fonctions privées de validation détectées; `16` noms sont définis plusieurs fois, soit `50` définitions dans ces groupes.
- `39` fichiers backend ont un chemin associé à policy/policies/gate.
- `6` fichiers non-`__init__` portent la configuration fournisseur/SQLite.
- La seule règle métier Application concrète sous `backend/modules` est actuellement la slice Resource Library.

## Hiérarchie observée

Les ADR et baselines documentaires définissent l'intention. Les contrats et policies du runtime ferment l'autorité technique. Application possède le seul résultat métier concrètement matérialisé pour READ-15; les adapters traduisent vers SQLite ou les SDK fournisseurs. Les helpers de calibration V2–V5.2.4 sont des outils d'évaluation sous `tests/` et ne doivent pas être assimilés silencieusement à des règles runtime.

Cette hiérarchie est inventoriée mais n'est pas encore jugée suffisante : la coexistence de règles documentaires, helpers de test et validations runtime est marquée `CANDIDATE` pour l'audit 12.17.3.
