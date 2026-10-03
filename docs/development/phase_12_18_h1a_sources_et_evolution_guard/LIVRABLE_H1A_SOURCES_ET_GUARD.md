# 12.18-H1A — Sources et proposition d'évolution du guard

## Verdict

**PASS documentaire borné — prêt pour une revue propriétaire unique.**

Baseline vérifiée et inchangée : `24b7a9850bc4644391dee2307c8a8a31036cd503`.
Le prompt H1A a été exécuté dans son seul périmètre documentaire. L'ADR est **PROPOSED / NOT_APPROVED**. H2/H3 ne sont pas démarrés. Aucun écart technique H1 n'est déclaré fermé.

Livrables : [matrice des sources et des neuf écarts](01_SOURCES_ET_ECARTS_RECONCILIES.json), [proposition d'ADR et évolution exacte des guards](02_PROPOSITION_EVOLUTION_GUARD.md), [paquet propriétaire et plan H2](03_PAQUET_DECISION_ET_PLAN_H2.md), ce rapport et [manifeste](MANIFEST_SHA256.txt).

## Sources : ce qui est rétabli, ce qui ne l'est pas

Les 14 sources transmises ont leurs hashes et tailles confirmés contre l'index et les deux manifests du paquet : 21 entrées du manifeste général et 14 entrées du manifeste de sources. Archive inchangée :
`a4ae5268736afc8d5b7ac9f0eda1c24ff123bface3a7a2d10416d2d7bb78ccbd`.

Les originaux, extractions et rendus restent hors dépôt, sans import ni nettoyage. Leur authenticité est bornée à la concordance des octets transmis et aux identités antérieures disponibles, pas à une certification de complétude de tous les artefacts canoniques.

Deux lacunes d'identité H1 sont fermées dans la nouvelle matrice, sans réécrire H1 :

- `PROJET_V2_DECISION_EXECUTION_NAVIGATEUR_LOCAL.md` : hash attendu `c75d98d572c1f1ccd6438bcbc32e30f5bc521d328c1e9b037432248df7f00936`, confirmé. Critères et nomenclature H1/H2/H3A/B/C rétablis ; cela ne prouve pas la recette.
- `PROJET V2 Feuille de Route` : PDF sans extension, hash attendu `a6302abadcb919cdf1f14bb1343e668c9b4b82d877175bdc17c06b8c7e0b0e01`, confirmé. Macro historique conservée, y compris Phases 13 Tests/recette et 14 Déploiement/stabilisation.

Le **contrat/livrable exact 12.1 reste non identifié** : aucun nom original ou hash attendu n'est inventé. La Phase 1 (EXT-S01) et le §12.1 de Phase 6 ne sont pas cette sous-phase.

Sept originaux distincts référencés par EXT-S08 §18 sont absents du bundle et non retrouvés dans la recherche locale bornée :

1. `PHASE_8_15_GATE_FINAL_CANONIQUE.xlsx`
2. `PHASE_8_11_OPENAPI_V2_CANONIQUE.yaml`
3. `PHASE_8_11_OPENAPI_V2_CANONIQUE.json`
4. `PHASE_8_12_CONTRACT_TEST_SUITE_CANONIQUE.zip`
5. `PHASE_8_12_PYTEST_JUNIT_CANONIQUE.xml`
6. `PHASE_8_13_MATRICE_FRONTEND_ENDPOINTS_CANONIQUE.xlsx`
7. `PHASE_8_14_AUDIT_TRANSVERSAL_RATIONALISATION_CANONIQUE.xlsx`

Recherche : dépôt (fichiers suivis/non ignorés), noms exacts dans le dossier projet documenté et le dossier d'entrée. Aucune recherche disque globale ni connexion Drive/GitHub/réseau. Il s'agit d'une absence dans ce périmètre, pas d'une preuve d'inexistence ailleurs. Aucun hash absent, OpenAPI, JUnit ou résultat de test n'a été fabriqué.

### Rôle des 14 sources et divergences importantes

| Sources | Apport à H1A et limite |
| --- | --- |
| EXT-S00 / Phase 0 | Périmètre produit individuel : recherche, création/transformation, vérification, conservation/export ; READ-15 n'est pas toute V2. |
| EXT-S01 / Phase 1 | Domaine métier, sans remplacer le livrable 12.1 absent. |
| EXT-S02 / Phase 2 | Modèle cible compilé ; pas preuve d'une base réellement migrée. |
| EXT-S03 / Phase 3 | Migration et identité historique du seed ; réserve documentaire 3.24 conservée, aucun nouvel audit physique. |
| EXT-S04 / Phase 4 | L'ouverture mentionne 4.1, mais la section finale 4.15 conclut bien PASS/CLOSED : pas de réouverture fondée sur la seule première page. |
| EXT-S05 / Phase 5 | Contrats des services ; présence de l'owner spécifié différente de son implémentation. |
| EXT-S06 / Phase 6 | Z07 inbound et Z10 composition autorisent l'adaptateur HTTP futur, sans framework concret imposé ni dépendance HTTP dans le métier. |
| EXT-S07 / Phase 7 | Persistance sqlite3 ; anciennes fixtures CANONICAL supersédées pour la sémantique actuelle par les décisions B06. |
| EXT-S08 / Phase 8 | API/UI spécifiées, 54 opérations/11 écrans ; compilation non substituable aux sept originaux. Ses tests HTTP « live » ne donnent aucun droit provider. |
| EXT-S09 / Phase 9 | IA/RAG assistive ; politique retrieval ultérieure F2A/ADR-P12-061 conservée. |
| EXT-S10 / Phase 10 | Spécification de validation/qualité clôturée, pas preuve d'exécution sur produit ; aucun seuil release adopté. |
| EXT-S11 / Phase 11 | Frontières agent/Application et responsabilités conservées ; backlog non équivalent au catalogue numéroté 12.1. |
| EXT-S12 / macro | Historique de Phases 13/14 préservé, sans leur clôture ou recréation. |
| EXT-S13 / navigateur | Mode de livraison et critères 12.18 rétablis, sans autoriser l'évolution du guard ou constater un produit fini. |

La lecture structurée des textes et tableaux DOCX a permis de distinguer compilations, états historiques et annexes indépendantes. Les corps pertinents S06/S07/S08/S11 ont été lus intégralement ; les autres compilations ont été examinées de façon ciblée selon la matrice. Trois pages PDF pertinentes ont été rendues et inspectées. Les outils de rendu DOCX disponibles n'ont pas permis une vérification visuelle complète : aucune certification de mise en page ni réaudit exhaustif de toutes les Phases 0–11 n'est revendiqué.

## Neuf écarts H1 conservés sans perte

Les 33 exigences H1 et les six fichiers existants sont intacts. Les neuf identifiants et titres originaux sont repris exactement dans la matrice.

| Écart | Résultat H1A |
| --- | --- |
| S01 | Deux identités restaurées ; 12.1 non identifié et sept annexes absentes. Exhaustivité non revendiquée. |
| I01 | Évolution du guard spécifiée, non approuvée ; serveur/composition encore absents. |
| I02 | UI/lanceur/package encore absents ; premier incrément proposé, pas livré. |
| I03 | READ-15 Application prêt ; contrat transport nouveau à approuver, endpoint absent. |
| I04 | Workflows produit incomplets et owners CAP-R02/A01/A02 toujours à développer. |
| I05 | GET/HEAD conservés ; commandes HTTP non autorisées et contrat manquant. |
| I06 | Runtime utilisateur non vérifiée ; aucune migration 002 déduite ni base ouverte. |
| I07 | OBS_A disponible ; lifecycle serveur encore à raccorder et recetter. |
| I08 | Doubles et calibrations historiques ne valent pas recette produit ; aucun live autorisé. |

Les handoffs récents priment sur les anciennes variantes : ResourceRef, quatre champs avec availability_status, aucune canonicalité déduite, version_ref/include rejetés. ContextOrigin=UNKNOWN et RELEASE_THRESHOLD=NONE demeurent. La sauvegarde temporaire B04 nettoyée n'est pas présentée comme disponible.

## Guard : résultat technique de lecture, sans modification

**Trois fichiers, quatre nodeids, six assertions A1–A6** ; détail exact, helpers, imports, exceptions et hashes dans l'ADR proposée.

| Fichier | SHA-256 PRE = POST |
| --- | --- |
| `tests/architecture/test_local_browser_http_boundary_fitness.py` | `d324d383351cce3039225a8439338f6059abbd2b34bebf286b0e29b8933d56e6` |
| `tests/architecture/test_minimal_local_observability_fitness.py` | `87adef3498b85d2bf9f9c462b8b493b29b4d6a474c36976ba775297fde249d7e` |
| `tests/architecture/test_security_recovery_observability_e2e_fitness.py` | `9b7d9a25430a41dd5a1c6696b11d582dbfe37d7b5cf425ccc0946d6baf37b501` |

Les six changements envisagés portent sur l'absence globale d'import serveur, de fichiers server/routes, de chaîne /api/v2, de frontend, de serveur depuis le guard B03 et sur l'allowlist de changements backend du guard F. Aucun autre invariant ne doit être neutralisé.

Proposition ADR-P12-069, numéro libre constaté : exceptions exactes, un seul import http.server, quatre routes fermées dont une opération métier, huit créations code/assets, cinq nouveaux fichiers de tests, trois guards à modifier et preuve PRE/POST nouvelle. Les anciens manifests et commits restent inchangés ; les trois guards ne sont pas des membres des 48 identités protégées B07. Cette vérification ne confère pas une permission de les éditer.

## Premier incrément proposé et reste du produit

`H2_READ15_LOCAL_STDLIB_V1` : hôte Python 3.12 stdlib borné, frontend local minimal, GET READ-15 via Application, observabilité et stop/restart ; aucun nouveau paquet ni lock, aucune IA. Tests sur données synthétiques temporaires hors dépôt, requêtes loopback uniquement **après approbation**. Aucun serveur n'a été démarré ici.

Les owners manquants, recherche/workflows produit complets, commandes HTTP, données réelles, migration éventuelle, package et recette H3 sont séparés et conservés dans le plan, avec sources, ports, tests, limites et commits seulement envisagés. Aucun nouvel écran de santé n'est pris pour une recette pédagogique.

Un choix différent de dépendances nécessiterait une décision et éventuellement une autorisation réseau distincte ; l'accès à la runtime utilisateur et une éventuelle migration exigeraient aussi leur autorisation. Les autorisations live historiques sont consommées, sans réutilisation.

## Contrôles documentaires effectués

- HEAD inchangé ; index vide ; diff des fichiers suivis vide ; `git diff --check` réussi.
- 2 257 fichiers suivis : hashes PRE/POST identiques, incluant code, guards, configuration, locks et anciens manifests.
- Six fichiers H1 : hashes PRE/POST identiques ; leurs changements non suivis attendus préservés.
- 14 sources externes : tailles/hashes POST conformes ; 35 entrées des deux manifests externes vérifiées ; archive inchangée.
- JSON parsé ; cardinalités 14 sources, neuf écarts uniques avec titres H1 exacts, trois lacunes originales et sept annexes ; 27 bindings de références locales vérifiés.
- Nouveaux documents : UTF-8 strict sans BOM, LF terminal unique, aucune fin de ligne CR ni espace terminal ; liens Markdown locaux résolus ; recherche ciblée de secrets et localisateurs privés sans candidat.
- Manifeste H1A : quatre entrées, excluant sa propre empreinte, puis vérification des hashes.
- Disposition finale attendue et contrôlée : exactement cinq nouveaux fichiers H1A, plus les six H1 déjà non suivis ; aucun import binaire, staging ou nettoyage.

Aucune suite technique relancée, conformément au prompt documentaire. Preuve B07 réutilisée explicitement : **4 947 passed / 5 skipped préexistants / 0 failed**, 16/16 gates B07 ; historique mypy 15 erreurs / 10 fichiers toujours distinct des checks actifs verts. Les tests B07 ne constituent pas une preuve d'exécution du serveur proposé. La clôture 12.17.8 reste acquise ; aucune clôture globale 12.17/12/projet ajoutée par H1A.

## État de sortie et prochain geste

```text
H1A = PASS_DOCUMENTAIRE_BORNE
H1_GAPS_PRESERVED = 9
TECHNICAL_GAPS_CLOSED = 0
H2_READINESS = READY_FOR_SINGLE_OWNER_REVIEW
OWNER_APPROVAL_STATUS = NOT_RECEIVED
H2_STARTED = FALSE
H3_STARTED = FALSE
GUARD_MODIFIED = FALSE
CODE_OR_CONFIG_MODIFIED = 0
SQLITE_ACCESSED_OR_WRITTEN = 0
PROVIDER_CALLS = 0
NETWORK_CALLS = 0
CREDENTIALS_READ = 0
TECHNICAL_TESTS_EXECUTED = 0
STAGING_COMMIT_PUSH_MERGE = NONE
```

Prochain geste : revue du [paquet de décision unique](03_PAQUET_DECISION_ET_PLAN_H2.md), portant sur D-SOURCE, D-GUARD et D-INCREMENT. Aucun champ d'approbation rempli, aucun horodatage inventé. Le PASS porte sur ce raccordement documentaire uniquement.
