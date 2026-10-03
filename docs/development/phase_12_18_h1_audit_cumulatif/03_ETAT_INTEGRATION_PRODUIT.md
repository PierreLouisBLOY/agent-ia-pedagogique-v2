# 12.18-H1 — État réel d'intégration du produit

## Verdict d'inventaire

**0 serveur produit, 0 lanceur produit, 0 frontend suivi et 0 endpoint HTTP enregistré.** Ce comptage porte sur les fichiers suivis de HEAD, pas sur le nombre de noms de routes dans des handoffs, de DTO ou de capabilities dans un registry. Aucun processus ni navigateur n'a été démarré pour cet audit.

Méthode : inventaire `git ls-files` des surfaces API/CLI/composition/frontend/scripts, lecture du contrat HTTP et de la configuration, recherche bornée des imports/registrations serveur et des propriétaires de use cases. `pyproject.toml` ne contient pas de `project.scripts`, dépendance serveur ou frontend. La CLI de `calibration_tooling` est un outil de calibration, pas un point d'entrée du produit. Un port employé dans les tests, par exemple 8765, n'est pas un port produit choisi.

## Spécifié, implémenté, câblé, testé, recetté

Toutes les mentions de tests ci-dessous renvoient aux preuves historiques/à B07 réutilisées, jamais à une nouvelle exécution H1. « Câblé » signifie ici composition réellement visible ; les compositions de tests sont distinguées du host produit absent.

| Composant | Spécification et implémentation | Câblage observé | Test isolé / intégré réutilisé | Recette navigateur |
|---|---|---|---|---|
| Serveur et lancement | Mode LOCAL_BROWSER / LOOPBACK_ONLY ; implémentation absente | Aucune factory de host ni entrypoint produit | Contrat HTTP seulement | Non exécutée |
| Frontend/assets | Cible navigateur du handoff ; aucun frontend suivi | Aucun service d'assets/UI | Aucune preuve UI | Non exécutée |
| Frontière HTTP | [contrat pur](../../../backend/adapters/inbound/api/local_browser.py), [schéma](../../../backend/infrastructure/config/schemas/http.py) | Port requis, GET/HEAD, preflight borné ; aucune route | Unitaires et composition observabilité HTTP B07 | Non exécutée |
| READ-15 | [inbound Application](../../../backend/adapters/inbound/application/resource_library.py), [query](../../../backend/modules/resource_library/application/queries/get_resource.py) | Délégation IP-03/OP-03 et harness ; pas de montage HTTP | SCN-01 SQLite réel et tests Application | Non exécutée |
| SQLite | [factory](../../../backend/infrastructure/composition/factories/sqlite.py), [loader](../../../backend/infrastructure/config/loaders/sqlite.py) | Stores/runtime/backup/restore disponibles ; pas de host produit | 24 tests seed réels inclus B07 ; copies contrôlées | Runtime utilisateur non vérifiée |
| Orchestration/Evidence | Registries/runtime/WF-0..11/E01..03 implémentés | Harness et injection de ports ; pas de composition utilisateur complète | Scénarios 12.14/12.15, retrieval réel et doubles | Non exécutée |
| Génération/review/correction | Pipelines et adapters implémentés, responsabilités séparées | Factories fournisseurs explicites ; pas de formulaire/route produit | Tests contractuels/doubles ; live 12.16 borné séparé | Non exécutée |
| CAP-R02/A01/A02 | Owners/règles de handoff ; DTO/implémentations encore différés | Entrées registry et sondes de routage seulement | Sonde != owner persistant testé | Non exécutée |
| Observabilité | [session locale](../../../backend/infrastructure/composition/bootstrap/observability.py), writer/sink concret | Points d'injection SQLite/provider/HTTP ; aucun host gérant leur lifecycle | 12 familles, confidentialité, rotation/rétention/flush B07 | Non exécutée |
| Stop/restart/recovery | Recovery runtime et fermeture session disponibles | Pas de serveur à arrêter/redémarrer | Tests recovery/backup/restore, pas recette utilisateur | Non exécutée |
| Dépendances/package | Trois locks/inputs validés, installs B05 réutilisées | Environnement développeur reproductible ; aucun package produit | Guard et pip check B07 | Non exécutée |

Le chemin à intégrer, **pas un chemin actuellement opérationnel**, est :
lanceur → host loopback/frontend → frontière HTTP → inbound Application ou workflow → owner Application → port → adaptateur SQLite/runtime.
Les sessions d'observabilité et de fermeture relèvent de la composition. Ni l'agent ni le navigateur ni le routeur ne reçoivent d'autorité SQL, filesystem métier ou promotion.

## READ-15 : appliquer le dernier contrat

Le [handoff B05](../phase_12_17_05b_b05_resource_ref_contract/06_API_HANDOFF_ALIGNMENT.md) prévoit `GET /api/v2/resources/{resource_ref}`, sans query. ResourceRef est une chaîne exacte ASCII de 1 à 128 caractères, motif `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` ; entrée invalide et référence valide absente restent distinctes.

Le [handoff B06](../phase_12_17_05b_b06_active_canonical_semantics/07_API_HANDOFF_ALIGNMENT.md) remplace l'ancien champ B09 `identity_status`. Les quatre champs actuels sont `resource_ref`, `resource_type`, `canonical_title`, `availability_status`. `canonicality_status` n'est pas exposé ni déduit. Les paramètres `version_ref`, `include` et inconnus sont rejetés, pas silencieusement ignorés. Une réintroduction demanderait un nouveau contrat versionné.

Le mapping prévu 200/400/404/500 doit rester minimisé. Il n'existe pas encore comme endpoint enregistré. Un simple healthcheck ne satisferait ni READ-15 ni les scénarios pédagogiques.

## Deux préalables architecturaux concrets

1. [Le guard B04](../../../tests/architecture/test_local_browser_http_boundary_fitness.py) `test_b04_adds_no_http_server_framework_or_route` inspecte actuellement tout `backend/`, interdit notamment les imports de serveurs, `server.py`/`routes.py` dans API et la chaîne `/api/v2`. L'ajout du serveur requiert donc une évolution canonique/ADR explicite du périmètre, avec nouvelles preuves conservant les invariants. Pas de suppression, exclusion, déplacement de contournement ou skip pour obtenir un PASS.
2. Le contrat HTTP courant n'autorise que GET/HEAD, et OPTIONS uniquement pour le preflight fermé. Création, correction et décisions de gate ne sont pas des POST « déjà autorisés ». Les commandes nécessaires à la recette requièrent un contrat versionné de sécurité/autorité ; on ne doit ni affaiblir le contrat actuel ni déguiser une écriture en GET.

Le [handoff owners](../phase_12_17_04e_b09_legacy_review_api_handoff/API_HANDOFF.json) fixe déjà l'ordre CAP-R02 → CAP-A01 → CAP-A02 et leurs bounded contexts. Il reste à matérialiser contrats/ports et tests d'effet. `WorkflowCompletionEvaluator` est un Protocol injecté, pas une politique produit de complétion à deviner.

## Données, sémantique et configuration

La preuve [B04](../phase_12_17_05b_b04_real_chain_recovery/13_FINAL_HANDOFF.md) porte sur une copie contrôlée : migration 002, cinq invariants, conservation des lignes et recovery. Elle atteste explicitement `USER_RUNTIME_002_APPLIED=FALSE`. B07 complète la preuve des copies sans toucher la runtime utilisateur. **État actuel utilisateur : non vérifié dans H1**, et non « 002 appliquée ».

Les identités conservées sont :

- seed : `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` ;
- migration 001 : `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102` ;
- migration 002 : `e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893`.

Le seed/sidecars PRE/POST identiques sont une preuve B07 réutilisée ; H1 ne les ouvre pas et n'en renouvelle pas le snapshot. Le bootstrap SQLite peut provisionner/migrer une runtime : appeler une factory « pour voir » serait une action, non un audit inoffensif. Il n'est donc pas appelé.

La reconfiguration B07 était uniquement dans le processus de validation : même seed, runtimes/caches externes, flags et credentials retirés sans résolution. Elle ne constitue pas une configuration persistante du lanceur. Le loader produit rejette les alias legacy et accepte les noms V2 avec chemins locaux portables. La cible réelle doit être autorisée/identifiée avant toute opération ultérieure.

`ContextOrigin=UNKNOWN` reste conservé. Les lignes ACTIVE ne deviennent pas CANONICAL ; disponibilité et canonicalité sont deux dimensions. Le créateur historique des sidecars reste inconnu, sans imputation inventée. La recherche sémantique et l'embedding réseau ne doivent pas devenir une dépendance implicite de la consultation locale.

## Observabilité, exploitation et livraison

OBS_A est déjà décidée : NDJSON local, rotation 5 MiB, **5 fichiers au total**, rétention 14 jours, flush ≤ 2 secondes. Aucun prompt/payload complet, réponse brute, secret ou donnée sensible. La composition produit doit effectivement gérer session, fermeture, erreurs et panne du sink ; la présence du writer ne prouve pas son branchement au serveur absent.

Les locks B05 ne démontrent pas une distribution finale, et leur autorisation réseau ponctuelle ne vaut plus autorisation d'installation. Démarrage et consultation locale sans Drive restent distincts d'une éventuelle recette IA live nouvellement autorisée. Une exécution sur doubles est étiquetée comme telle. Le seuil pédagogique de release demeure `NONE`.
