# Matrice finale des seize gates

Critères inchangés issus du plan canonique 10. Baseline technique testée : `f28b29f0964d2642b74eb7098f90359d15fb4f0c`.

```text
FINAL_GLOBAL_GATES_COUNT = 16
PASS = 16
FAIL = 0
PARTIAL_ACCEPTED = FALSE
PHASE_12_17_08_B07 = PASS
```

Ces verdicts sont effectifs **uniquement après la transaction documentaire et le postcontrôle propre de 14**. La gate 14 est une postcondition, pas une revendication de propreté pendant le staging.

| # | Gate | Critère PASS canonique | Preuve finale |
|---:|---|---|---|
| 1 | OPEN_P0 | `OPEN_P0 = 0` | PASS — Registre recalculé : 30 findings, 22 CLOSED, 4 HISTORICAL, 4 DEFERRED ; aucun P0 ouvert. |
| 2 | P1 bloquants | `OPEN_BLOCKING_P1 = 0` | PASS — CF-REPO-001 fermé : 137 blobs (126 + 11) présents dans B01 ; contenu inchangé sur la baseline corrigée. |
| 3 | Active mypy | 0 diagnostic sur le graphe actif documenté | PASS — Exécuté de nouveau sur la baseline corrigée : 0 diagnostic / 42 fichiers, mypy 2.3.1, exit 0. |
| 4 | Backend mypy | 0 diagnostic sur tout `backend/` | PASS — Exécuté de nouveau sur la baseline corrigée : 0 diagnostic / 683 fichiers, mypy 2.3.1, exit 0. |
| 5 | Suite globale | 0 failure | PASS — 4947 passed, 5 skipped, 0 failed, 0 error ; 4952 collectés ; 1617.21 s ; exit 0 et JUnit complet. 24/24 tests seed et 872/872 architecture passent. |
| 6 | Seed inchangé | SHA256 `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`, PRE=POST | PASS — SHA attendu authentifié avant SQLite ; mode ro + immutable dans le test corrigé. Snapshots principal/WAL/SHM/journal PRE/POST strictement identiques après la suite complète. |
| 7 | Runtime valide | provisionnement/migrations/recherche sur runtimes temporaires PASS | PASS — 24/24 tests seed réels passent, dont provisioning, application, Search/RAG, retrieval sur deux runtimes et lifecycle/backup/restore. Runner multi-version et migration corrective 002 testés sur fixtures temporaires externes ; aucun déploiement utilisateur. |
| 8 | Secrets | `SECRET_FINDINGS_COUNT = 0` | PASS — Scan borné de tous les fichiers suivis et candidats canoniques B07 : zéro signature sensible et zéro chemin DB/secret/output interdit ; valeurs jamais affichées. |
| 9 | Fournisseurs | `PROVIDER_CALLS = 0`, aucune autorisation live active, aucun credential résolu | PASS — 0 appel fournisseur, 0 credential résolu, autorisations live désactivées. Les trois opt-ins restent skippés ; les validations de contrats emploient des doubles. |
| 10 | HTTP local-browser | contrat loopback-only PASS; aucun serveur ajouté | PASS — Guards architecture et tests unitaires/composition HTTP inclus dans la suite globale réussie ; contrat loopback-only conservé, aucun serveur ni endpoint ajouté. |
| 11 | Observabilité minimale | 12/12 signaux PASS, confidentialité PASS, sink failure-isolated | PASS — Tests des 12 familles, confidentialité, rotation 5 MiB × 5, rétention 14 jours, flush ≤ 2 s et isolation du sink inclus dans la suite globale réussie. |
| 12 | Dépendances | reproductibilité PASS ou exception exacte approuvée | PASS — Trois locks et inputs inchangés ; six clean installs B05 réutilisées (deux par ensemble). Guard de reproductibilité et pip check passent ; aucune résolution réseau B07. |
| 13 | Hygiène dépôt | quatre gaps fermés, aucun DB/secret/output runtime suivi, repository walks déterministes | PASS — 203/203 ensembles conservés, 20664 fichiers et 2994 répertoires ; empreintes de métadonnées PRE/POST identiques ; guards d'hygiène réussis, zéro suppression/pollution. |
| 14 | Politique worktree finale | aucun staged, aucune modification tracked, aucun untracked canonique; ignored local autorisé et inventorié | PASS — Postcondition de la transaction documentaire : commit local limité à l'allowlist B07, puis git status --porcelain=v1 -z vide. Ce PASS n'est valable qu'après succès de ce postcontrôle ; le staging préparatoire ne constitue pas une preuve de propreté. |
| 15 | Disposition 126 | `126/126` conformes à l'option propriétaire, suivis comme preuve après minimisation éventuelle | PASS — 126/126 preuves B01 inchangées ; six minimisations autorisées et 18 reconstitutions EOF conservées ; aucun nouveau rebind. |
| 16 | Disposition 05C | `11/11` preuves 12.17.5C versionnées et manifestes valides | PASS — 11/11 preuves 05C suivies et inchangées ; 23 manifestes sources / 254 entrées valides, aucun manifeste historique réécrit. |

Le JSON 04 porte les critères, sources, preuves obligatoires et scopes par gate. Les preuves détaillées actuelles sont en 13. Le snapshot 08 conserve le premier passage interrompu : 14/16, gates 5 et 14 en échec, sans résultat global complet. Cette histoire n'est pas transformée rétroactivement en PASS.

La gate 7 concerne les copies/runtimes temporaires, jamais un déploiement de la migration 002 chez l'utilisateur. Les 872 tests architecture et les 24 tests seed sont inclus dans les 4952 tests, non additionnés.
