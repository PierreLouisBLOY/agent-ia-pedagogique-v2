# R4 — Sauvegarder, rouvrir et exporter Word

Baseline : `f4ba498ba001dfcae44d76d1a430405cbaf32b3f`.
Mandat : P_R4_SAVE_REOPEN_WORD_GROUPED_DELIVERY, confirmé par le propriétaire.
Voir l'ADR-r4-save-reopen-word pour les frontières et la règle de sérialisation.

## Utilisation

Avec Python 3.12 et les dépendances du projet déjà disponibles :

```text
python -B -m backend.adapters.inbound.cli.local_browser --saved-only --saved-root <DOSSIER_NEUF_HORS_DEPOT> --create-saved --port 8765
```

À la reprise, employer le même dossier et retirer `--create-saved`.
Aucune recherche automatique de stockage, de seed ou de configuration.
Le mode `--saved-only` ne raccorde ni bibliothèque, ni conversation fournisseur.
Dans le mode conversation existant, `--saved-root` ajoute la sauvegarde de la version
R3 consultée. Les versions non sauvegardées restent volatiles. Ne jamais employer
`--create-saved` pour une racine déjà présente.

Parcours : sauvegarder une version → fermer le service → redémarrer →
retrouver les versions → rouvrir la référence exacte → prévisualiser le document →
télécharger le DOCX. Les exports séparés sont sujet élève, corrigé professeur, barème.
Le catalogue n'est pas une sauvegarde de session : aucun grant ni bail n'est restauré.

Les imports autorisés passent par le DTO SavedProduction puis le service Application,
jamais par une API de chemin libre. Ils sont marqués IMPORTED_DOCUMENTARY avec les
SHA-256 des sources exactes ; aucune provenance n'est supposée authentique par le seul
fait d'un téléchargement. Les preuves doivent être vérifiées par le propriétaire de
la composition avant d'appeler ce service. Il n'existe pas d'import HTTP arbitraire.

## Contrat fermé

SAVE-REOPEN-WORD-HTTP-LOCAL-1.0 étend les 16 routes antérieures par six routes :
GET/POST conversation/saved ; GET version/saved ; POST version/saved-validation ;
GET/POST version/promotion ; GET version/preview/{document_kind} ;
GET version/word/{document_kind}. Les préfixes exacts sont dans le registre.
document_kind est exclusivement student, correction ou marking.
Pas de latest, paramètre de chemin filesystem ou query additionnelle.
Host/Origin/nonce et intention locale préexistants sont conservés.

CAP-R02 est réellement exécutée lors de la lecture de version sauvegardée.
CAP-A01 est une action explicite nouvelle avec ses propres référence/date.
CAP-A02 exige CAP-A01 exact sans FAIL puis une gate C-09/C-10 USER fraîche,
validée par GateEngine, avec reconnaissance A16. Son reçu durable est consommé,
non réactivable. Une review bloquante ne donne pas droit à promotion.
Les imports documentaires ne peuvent être validés/promus par ce parcours R4.
CAP-A03 est une commande M12 utilisant un port WordWriter, sans provider.
La promotion est enregistrée dans le patrimoine local R4 ; le seed et l'ancienne
bibliothèque ne sont jamais modifiés ni raccordés implicitement.

Le writer reçoit une projection fermée, pas un bundle complet pour le sujet.
Aucune réponse, commentaire, note cachée, macro, chemin privé ou relation externe
n'est ajouté au DOCX élève. Les champs complets expected_answer/rationale et les
critères sont conservés côté professeur. Les locators ne servent pas au rendu.

## Persistance et limites

Règle SAVED-PRODUCTION-1.0 : JSON UTF-8, clés triées, séparateurs compacts,
ensure_ascii=False, allow_nan=False ; SHA-256 sur ces octets.
Les données originales restent dans une enveloppe immuable ; conservation et actions
R4 séparées. Identité égale avec contenu différent = refus.
Trois versions maximum par production, 300 versions/3000 actions par stockage ;
catalogue de 16 MiB maximum. Verrou interprocessus non bloquant, fsync du candidat,
publication atomique et relecture avant succès. Une panne avant remplacement laisse
le catalogue précédent. Les temporaires .pending ne sont jamais relus comme documents.
Le journal d'actions porte une séquence monotone ; son ordre ne dépend pas des UUID.
Une promotion compare atomiquement l'état des actions contrôlé avant l'ajout : tout
changement concurrent impose une nouvelle décision, sans retry implicite.
La garantie testée concerne l'arrêt de processus/panne d'écriture, pas toutes les pannes
matérielles de disque. Le propriétaire doit conserver ses sauvegardes externes.

Après un résultat de commande incertain, aucun rejeu automatique. Lire d'abord l'état ;
les identifiants d'action identiques permettent une consultation idempotente du reçu.
Le répertoire est local privé hors dépôt avec protections filesystem existantes.
Aucune nouvelle dépendance ; pas de SQLite dans le chemin de persistance R4.

## Contrôles nommés

- tests/unit/test_r4_saved_production.py : atomicité, conflits, reprise, limite et imports.
- tests/unit/test_r4_promotion.py : gate réelle, refus et consommation/idempotence.
- tests/unit/test_r4_word.py : XML, textes complets, absence de correction côté élève.
- tests/integration/test_r4_local_http.py : parcours HTTP et refus de requêtes étrangères.
- tests/architecture/test_r4_product_boundary.py et tests/unit/test_r4_scope_guard.py :
  fermeture exacte, frontières et mutations.
- Régression nommée R1/R2/R3 : guards produit, assets, routes et suites D3 pertinentes.
- Ruff, mypy des changements, compilation vers cache externe.
- Recette navigateur et rendu DOCX : preuves privées séparées, NOT_RUN si indisponibles.

Ce document n'annonce pas un PASS non exécuté. Les résultats datés, empreintes de
commit/clone et états VALIDÉ_LOCAL/PUBLIÉ/INTÉGRÉ_MAIN figurent dans la livraison.
Les exemples privés, logs et rapports de recette ne sont pas dans Git.

## Inventaire borné

- `architecture/adr/ADR-r4-save-reopen-word.md` — ADR R4 : données durables distinctes de l'autorité, export et promotion.
- `docs/development/R4_SAVE_REOPEN_WORD.md` — Contrat, inventaire final, utilisation et preuves publiques.
- `backend/modules/work_orchestration/contracts/dto/saved_production.py` — DTO de sauvegarde immuable, empreintes, rapports et provenance documentaire.
- `backend/modules/work_orchestration/ports/outbound/saved_production.py` — Port de persistance atomique, lecture exacte et registre d'actions.
- `backend/modules/work_orchestration/application/services/saved_production.py` — Sauvegarde, réouverture, CAP-R02 et validation nouvelle explicite.
- `backend/modules/lifecycle_promotion/contracts/dto/promotion.py` — Décision humaine versionnée séparée des rapports et imports.
- `backend/modules/lifecycle_promotion/application/commands/promote_saved.py` — CAP-A02 : refus, validation exacte, gate fraîche et idempotence.
- `backend/modules/materialization_export/contracts/dto/word_document.py` — Projection complète fermée élève/corrigé/barème.
- `backend/modules/materialization_export/ports/outbound/word_writer.py` — Port DOCX sans type fournisseur ou filesystem.
- `backend/modules/materialization_export/application/commands/export_saved.py` — CAP-A03 : prévisualisation et export de la version exacte.
- `backend/adapters/outbound/persistence/saved_production.py` — Stockage neuf privé atomique ; réutilisation des primitives sécurisées.
- `backend/adapters/outbound/export/word.py` — Writer OOXML standard sans nouvelle dépendance.
- `backend/adapters/outbound/export/__init__.py` — Package de l'adaptateur export.
- `backend/adapters/inbound/application/saved_production.py` — Frontière Application R4, CAP-R02 et gate C-09/C-10.
- `backend/adapters/inbound/api/saved_production.py` — Contrat HTTP fermé et erreurs minimisées.
- `backend/adapters/inbound/api/routes.py` — Routes R4 explicites ; routes antérieures conservées.
- `backend/adapters/inbound/api/server.py` — Dispatch R4 par frontière injectée ; sécurité locale inchangée.
- `backend/infrastructure/composition/factories/local_browser.py` — Wiring R4 optionnel et mode sans bibliothèque/SQLite utilisateur.
- `backend/adapters/inbound/cli/local_browser.py` — Cible R4 explicite, création/reprise distinctes, aucun environnement implicite.
- `frontend/index.html` — Commandes sauvegarde/réouverture/prévisualisation/export/promotion explicite.
- `frontend/app.js` — Interactions R4 sans rejeu automatique, réponses affichées via textContent.
- `tests/support/r4_synthetic.py` — Fixtures inédites artificielles et helpers de recette.
- `tests/support/r4_scope_guard.py` — Successeur exact vérifiant les deltas R4 et la préservation historique.
- `tests/support/r3_d3_scope_guard.py` — Branchement étroit du successeur R4 pour preuves historiques.
- `tests/support/r3_guard_oracle.py` — Inventaire R4 et projection historique authentifiée des guards.
- `tests/architecture/test_r4_product_boundary.py` — Frontières, inventaire, contrôles de mutation.
- `tests/architecture/test_r3_product_boundary.py` — Fermeture R3 conservée dans le registre élargi R4.
- `tests/architecture/test_local_browser_product_boundary.py` — Registre R4 fermé et non-régression des assertions antérieures.
- `tests/architecture/test_resource_ref_contract_fitness.py` — Assertion de registre actif R4 fermé.
- `tests/unit/test_local_browser_product_routes.py` — Attente de registre élargi sans suppression des refus.
- `tests/unit/test_r4_saved_production.py` — Persistance, conflit, panne, limite versions, isolation d'autorité.
- `tests/unit/test_r4_promotion.py` — CAP-A02 nominal/refus/idempotence sur artificiel seulement.
- `tests/unit/test_r4_word.py` — CAP-A03, XML, intégralité et séparation élève/professeur.
- `tests/integration/test_r4_local_http.py` — Save/restart/read/preview/export et sécurité boucle locale.
- `tests/unit/test_r4_scope_guard.py` — Mutations de sources et refus des changements hors périmètre.
- `tests/support/r3_portable_clone_guard.py` — Inventaire et index historiques : successeur R4 exact sans données privées.
- `tests/architecture/test_conversation_product_boundary.py` — Registre R4 et deux fixtures de guard : délégation Git hors simulation, copie des sources publiques pour mutation.
- `tests/architecture/test_local_search_product_boundary.py` — Uniquement taille du registre actif ; refus conservés.
- `tests/architecture/test_security_recovery_observability_e2e_fitness.py` — Union exacte des nouveaux owners R4 ; aucun préfixe ouvert.

- `tests/architecture/test_r3_d3_boundary.py` — Lecture historique des routes par projection R4 authentifiée, autres contrats inchangés.

- `tests/support/r3_prepare_contract_alignment_guard.py` — Projection historique authentifiée des guards R4 et union exacte d'inventaire.
- `tests/support/r3_parse_observability_guard.py` — Projection historique authentifiée, sans supprimer les contrôles de mutation.
- `tests/support/r3_editorial_correction_guard.py` — Union exacte R4 dans violations, après authentification des successeurs D3/portable ; tables et refus historiques conservés.

Les sources historiques et manifests antérieurs ne sont pas réécrits. Le successeur
R4 vérifie l'empreinte de chaque changement et les symboles autorisés avant de présenter
les octets baseline aux anciens oracles. Les contrôles actifs vérifient les routes et
comportements R4 ; aucun répertoire complet n'est exempté.

Arrêt après R4. Ni nouvelle version du pilote, ni promotion du pilote, fournisseur,
comptage, migration utilisateur ou démarrage de R5–R8/H3.
