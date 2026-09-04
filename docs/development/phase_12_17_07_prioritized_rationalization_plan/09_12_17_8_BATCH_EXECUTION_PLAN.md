# Phase 12.17.7 — Plan d'exécution 12.17.8

```text
12_17_8_BATCH_COUNT = 7
ORDER = B01 -> (B02, B04, B05, B06) ; B02 -> B03 ; ALL -> B07
PROVIDER_CALLS_ALL_BATCHES = 0
CANONICAL_OR_USER_SQLITE_WRITES_ALL_BATCHES = 0
```

Sept lots constituent le minimum cohérent : la provenance doit être stabilisée avant toute modification; les frontières de fichiers/SQLite partagent la même primitive locale; l'observabilité dépend de cette primitive; le contrat HTTP reste distinct de l'implémentation; dépendances/config/docs forment un même changement d'environnement; Git ignore/temp forment un même changement d'hygiène; la clôture est transverse.

## 12.17.8-B01 — Consolidation de provenance

- **Findings** : CF-REPO-001.
- **Cause** : 137 preuves antérieures, puis les 15 artefacts 12.17.6 et les 13 artefacts 12.17.7, ne sont pas liés à un commit canonique.
- **Files** : allowlist attendue de 165 chemins; cinq preuves privées listées dans `03_P1_DECISION_ANALYSIS.md`; manifestes transitivement affectés si Option A.
- **Implementation** : appliquer exactement l'option owner A ou B, revalider/rebinder les manifestes, produire matrice de provenance/staging.
- **Tests** : exactitude allowlist, manifestes, scan secrets/binaires/DB, équivalence de minimisation, guards historiques, `git diff --cached --check`.
- **SQLite access/write** : aucun accès / aucune écriture.
- **Provider calls** : 0.
- **Owner approval** : OUI, Option A ou B et allowlist exacte.
- **Commit policy** : un commit documentaire/provenance; staging littéral; aucun push.
- **Rollback** : `git revert <commit-B01>` après revue; ne jamais réécrire l'historique.
- **Entry gate** : HEAD exact, worktree sans tracked/staged drift, total attendu exact, décision owner attestée.
- **Exit gate** : fichiers approuvés suivis, manifestes verts, aucun fichier hors allowlist, P1 fermé.

## 12.17.8-B02 — Frontière locale fichiers et SQLite

- **Findings** : CF-FILE-001, CF-SQLITE-HARDEN-001.
- **Cause** : absence d'adaptateur filesystem concret et de primitive uniforme permissions/no-follow.
- **Files planifiés** : `backend/agent_runtime/sandbox/ports.py` seulement si le contrat doit être précisé; nouveau helper sous `backend/infrastructure/filesystem/`; nouvel adaptateur sous `backend/adapters/outbound/filesystem/`; `backend/adapters/outbound/persistence/migrations.py`; `backend/adapters/outbound/persistence/sqlite.py`; `backend/adapters/outbound/semantic/index.py`; factories SQLite; tests unitaires/intégration/architecture dédiés.
- **Implementation** : helper de chemin physique/permissions; adapter sandbox local; sept contrôles SQLite de `05_SQLITE_SECURITY_HARDENING_PLAN.md`; aucun type filesystem/SQLite dans Domain/Application.
- **Tests** : traversal, extension/MIME/taille, symlink/junction, race simulée, publication atomique, permissions, seed/runtime collisions, backup/restore, WAL/SHM, temp hors repo.
- **SQLite access/write** : fixtures/copies temporaires uniquement; lecture stricte du seed autorisée pour preuve; 0 écriture seed ou DB utilisateur.
- **Provider calls** : 0.
- **Owner approval** : non, après approbation globale du plan; aucun changement de sémantique métier.
- **Commit policy** : un commit atomique code+tests+preuve B02.
- **Rollback** : revert du commit; fixtures supprimables par le framework de test uniquement.
- **Entry gate** : B01 PASS; ADR existants relus; seed hash de référence connu.
- **Exit gate** : CF-FILE et CF-SQLITE-HARDEN fermés; seed PRE=POST; tests ciblés/architecture/mypy verts.

## 12.17.8-B03 — Observabilité minimale locale

- **Findings** : CF-OBS-001.
- **Cause** : contrats existants sans destination ni lifecycle wiring.
- **Files planifiés** : `backend/infrastructure/observability/`; composition roots existants/à matérialiser sans serveur; `calibration_tooling/observability/`; tests unitaires/intégration/architecture; documentation de configuration.
- **Implementation** : implémenter l'option OBS-A recommandée ou le design approuvé de OBS-B; câbler les 12 signaux sans dépendance métier au sink; rotation/rétention et flush borné.
- **Tests** : matrice complète de `04_MINIMUM_OBSERVABILITY_PLAN.md`, privacy classifier, sink failure isolation, rotation, rétention, shutdown.
- **SQLite access/write** : fixtures temporaires seulement pour événements; 0 seed/user write.
- **Provider calls** : 0, transports fake uniquement.
- **Owner approval** : OUI, destination/rotation/rétention/flush.
- **Commit policy** : un commit atomique code+config+tests+preuve B03.
- **Rollback** : revert du commit; aucun log de test conservé dans le dépôt.
- **Entry gate** : B02 PASS et décision observabilité attestée.
- **Exit gate** : 12/12 signaux couverts, exclusions sensibles prouvées, sink local sain/failure-isolated, CF-OBS fermé.

## 12.17.8-B04 — Contrat HTTP local-browser fail-closed

- **Findings** : CF-HTTP-001.
- **Cause** : l'absence actuelle de serveur laisse la cible loopback non encodée.
- **Files planifiés** : `backend/adapters/inbound/api/__init__.py` ou nouveau module de contrat pur sous cette frontière; `backend/infrastructure/config/` pour DTO de bind sans framework; tests architecture/sécurité; documentation du handoff API.
- **Implementation** : contrat loopback-only, port explicite, origins exactes, debug/docs off, host policy, cookies/CSRF fermés selon absence d'état, erreurs closes; aucun endpoint ni serveur.
- **Tests** : refus `0.0.0.0`, `::`, hostname non-loopback, wildcard CORS, credentials cross-origin, debug/docs; acceptation `127.0.0.1`/`::1` sous policy exacte; absence de framework et d'exposition fournisseur.
- **SQLite access/write** : aucun / aucune.
- **Provider calls** : 0.
- **Owner approval** : non; cible `LOCAL_BROWSER / LOOPBACK_ONLY_BY_DEFAULT` déjà canonique.
- **Commit policy** : un commit contrat+tests+preuve B04.
- **Rollback** : revert du commit.
- **Entry gate** : B01 PASS, aucune implémentation HTTP concurrente.
- **Exit gate** : contrat et guards verts, serveur/routes toujours absents, CF-HTTP fermé pour la préparation 12.18.

## 12.17.8-B05 — Dépendances, environnement et alias de configuration

- **Findings** : CF-DEPENDENCY-001, CF-DOC-001, CF-LEGACY-001.
- **Cause** : résolutions non hashées, documentation en retard et fenêtre d'alias B08 non close.
- **Files planifiés** : `requirements/lock/*.txt` nouveaux; `pyproject.toml` seulement si métadonnée de lock nécessaire; `requirements-dev.txt`; `docs/development/ENVIRONMENT.md`; `backend/infrastructure/config/loaders/sqlite.py`; tests de configuration et de reproductibilité.
- **Implementation** : cinq items de `06_DEPENDENCY_REPRODUCIBILITY_PLAN.md`; documenter les trois ensembles; rendre les noms V2 canoniques et appliquer la dépréciation legacy avec erreur fermée.
- **Tests** : hash-required clean installs, lock drift, imports, mypy/ruff/pytest applicables, loader V2/legacy/conflict.
- **SQLite access/write** : aucun / aucune.
- **Provider calls** : 0; imports/smoke tests ne construisent aucun client live.
- **Owner approval** : non au-delà de l'approbation du plan; toute exception de lock exige toutefois une approbation distincte.
- **Commit policy** : un commit environnement+locks+config+docs+tests.
- **Rollback** : revert du commit et recréation d'un venv propre; aucun downgrade automatique d'un environnement utilisateur.
- **Entry gate** : B01 PASS, réseau de résolution explicitement autorisé au moment de l'exécution ou wheelhouse approuvée disponible.
- **Exit gate** : installation reproductible PASS ou exception exacte approuvée; docs cohérentes; alias legacy sans ambiguïté.

## 12.17.8-B06 — `.gitignore`, tests déterministes et rétention locale

- **Findings** : CF-TEMP-LOCAL-001, CF-GITIGNORE-001.
- **Cause** : quatre familles adjacentes non ignorées et scans de dépôt non isolés des racines locales.
- **Files planifiés** : `.gitignore`; helpers/tests qui parcourent le dépôt; `docs/development/ENVIRONMENT.md` ou guide de maintenance; tests d'architecture Git/hygiène.
- **Implementation** : ajouter les quatre familles exactes; exclure explicitement racines ignored/env/cache des repository walkers; utiliser le temp système; fournir commande dry-run d'inventaire/rétention.
- **Tests** : `git check-ignore` positifs/négatifs, parcours déterministe avec faux nested repo, absence de DB/secret/output candidat, dry-run sans suppression.
- **SQLite access/write** : aucun / aucune.
- **Provider calls** : 0.
- **Owner approval** : non pour code/docs; toute suppression locale ultérieure exige une autorisation destructive séparée.
- **Commit policy** : un commit hygiène+tests+preuve B06.
- **Rollback** : revert du commit; aucun fichier local supprimé par le lot.
- **Entry gate** : B01 PASS afin que les preuves canoniques ne puissent pas être masquées par de nouvelles règles.
- **Exit gate** : quatre familles correctement ignorées, guards non sur-larges, repository walkers reproductibles, aucune action destructive.

## 12.17.8-B07 — Ré-audit transverse et clôture

- **Findings** : validation des huit must-fix; surveillance CF-MYPY-HIST, CF-SIDECAR-HIST, CF-B01-HIST, CF-DOC-DUP-HIST et des quatre DEFERRED sans les modifier.
- **Cause** : une release gate doit prouver l'état composé, pas seulement les lots isolés.
- **Files planifiés** : nouveau paquet `docs/development/phase_12_17_08_closure/`, manifeste; aucun changement fonctionnel admis dans ce lot.
- **Implementation** : exécuter les 16 gates de `10_12_17_8_FINAL_GATES.md`; inventaire Git final; preuves de seeds, secrets, providers et historique.
- **Tests** : ciblés cumulés, architecture, active/backend mypy, ruff, compileall, suite globale, clean-install lock, seed real gate read-only.
- **SQLite access/write** : seed read-only strict et fixtures temporaires; 0 seed/user write.
- **Provider calls** : 0; live authorization absente.
- **Owner approval** : approbation de clôture avant merge; pas de merge automatique.
- **Commit policy** : un commit documentaire de clôture seulement si 16/16 PASS; aucun push/merge automatique.
- **Rollback** : revert du commit de clôture; les lots techniques sont revertés individuellement si leur gate régresse.
- **Entry gate** : B01-B06 PASS, worktree conforme à la politique, aucune dérive de scope.
- **Exit gate** : 16/16 gates PASS, manifestes intègres, `12.17.8 = PASS`, gate 12.18 calculée séparément.

## Invariants de tous les lots

- frontières Phases 6/11 inchangées sans ADR ;
- aucune base, sidecar, sortie runtime, secret ou credential dans Git ;
- aucun accès direct métier/agent à SQL, filesystem ou provider ;
- génération, validation, évaluation et promotion restent séparées ;
- aucun provider live, retry ou résolution de credential ;
- aucun merge sans revue explicite.
