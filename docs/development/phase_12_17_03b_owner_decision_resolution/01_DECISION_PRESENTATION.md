# Phase 12.17.3B — Présentation des décisions propriétaire

Les blocs suivent l’ordre optimal du graphe : racines d’abord (`OD-01`, `OD-02`, `OD-05`, `OD-08`), puis décisions dépendantes (`OD-03`, `OD-06`, `OD-07`, `OD-04`). Aucune option n’est sélectionnée.

## 1 — OD-01 · Autorité du corpus métier Phases 1/2

**Enjeu.** Le corpus consolidé Phases 1/2 n’est pas localisé dans le dépôt, donc l’exhaustivité historique des 41 règles candidates n’est pas démontrée. Le propriétaire doit choisir l’autorité documentaire utilisable par 12.17.

- Règles/findings : `CR-002`, `CR-001`, `BRF-001`.
- Option A — Lier le corpus original par chemin/identité, SHA-256, provenance et carte de supersession (`CR-002 REWRITE`, `CR-001 CONSOLIDATE`).
- Option B — Déclarer formellement le corpus indisponible et borner 12.17 aux preuves canoniques ultérieures du dépôt (`CR-002 KEEP + ADD_TESTS`).
- Option C — Produire une reconstruction provisoire, explicitement non autoritative, depuis les ADR/handoffs ultérieurs (`CR-002 REWRITE + ADD_TESTS`).
- Recommandation : **Option A**.
- Confiance : **MEDIUM**.
- Justification :
  - donne la meilleure complétude et la meilleure lignée ;
  - permet une vraie analyse de supersession ;
  - évite de transformer une reconstruction en source primaire ;
  - reste conditionnée à la localisation réelle de l’artefact.
- Impacts :
  - Produit : rétablit ou borne explicitement la complétude historique ;
  - Domain/Application : peut révéler des invariants omis avant la conception des use cases ;
  - API : aucune modification, mais toute future exposition devra tracer sa règle approuvée ;
  - SQLite/données : aucun constat de schéma ;
  - Migration : aucune ;
  - Tests : futurs contrôles de lignée et de supersession.
- Dépendances : racine indépendante ; `OD-03` et `OD-07` en dépendent.
- Risque si différée : l’autorité historique reste incomplète et les décisions dépendantes restent bloquées.

## 2 — OD-02 · Traçabilité de la réutilisation legacy

**Enjeu.** Phase 12.15 déclare une adaptation de Phase 7, mais le répertoire `docs/legacy-review` exigé par le README est absent. Il faut choisir comment clôturer cet écart sans réécrire l’historique.

- Règles/findings : `CR-001`, `EX-01`, `BRF-002`.
- Option A — Créer une trace rétrospective canonique dans `docs/legacy-review`, liée aux preuves Phase 12.15 et explicitement non rétroactive (`CR-001 CONSOLIDATE + ADD_TESTS`).
- Option B — Déclarer le handoff Phase 12.15 comme emplacement canonique et superséder ultérieurement la convention README (`CR-001 REWRITE + ADD_TESTS`).
- Option C — Geler la réutilisation comme non-conformité historique close, incapable d’autoriser une nouvelle réutilisation (`CR-001 KEEP + DEPRECATE`).
- Recommandation : **Option A**.
- Confiance : **HIGH**.
- Justification :
  - respecte l’emplacement actuellement prescrit ;
  - conserve la preuve historique existante ;
  - n’invente aucune approbation passée ;
  - maintient le fail-closed pour toute réutilisation future.
- Impacts :
  - Produit : clôt l’ambiguïté de provenance ;
  - Domain/Application : aucun changement sémantique ou de code ;
  - API : aucun ;
  - SQLite/données : aucune preuve de schéma ou donnée runtime ;
  - Migration : aucune ;
  - Tests : contrôle documentaire de lignée.
- Dépendances : racine indépendante.
- Risque si différée : `EX-01` reste en `EVIDENCE_GAP` et la clôture de gouvernance demeure incomplète.

## 3 — OD-05 · Preuve du schéma SQLite externe

**Enjeu.** Neuf règles exigent le schéma canonique externe, mais les sources 12.17.3A ne fournissent ni chemin exact ni SHA-256 du seed. Le propriétaire peut choisir un mode de preuve, mais aucune équivalence structurelle ne peut encore être prononcée.

- Règles/findings : `CR-007`, `CR-010` à `CR-015`, `CR-031`, `BRF-005` ; règles brutes `BR-014`, `BR-016`, `BR-017`, `BR-020`, `BR-021`, `BR-022`, `BR-024`, `BR-025`, `BR-052`.
- Option A — Autoriser l’introspection read-only du seed exact, liée au chemin, SHA-256 et taille, avec sortie limitée aux métadonnées de schéma (`ALIGN_DATA_MODEL`, aucun export de lignes).
- Option B — Accepter l’écart de preuve pour ce cycle et conserver les neuf règles en `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED` (`CR-010/015 KEEP`).
- Option C — Fournir un export de schéma signé, minimisé et lié au seed, sans fichier SQLite ni contenu de lignes (`CR-010/015 ALIGN_DATA_MODEL`).
- Recommandation : **Option A**.
- Confiance : **HIGH**.
- Justification :
  - vérifie le vrai schéma sans l’inventer depuis les requêtes ;
  - permet de contrôler clés, contraintes, indexes, triggers et vues ;
  - évite copie, mutation et migration du seed ;
  - produit une preuve minimale et reproductible.
- Impacts :
  - Produit : peut fermer neuf contrôles structurels ;
  - Domain/Application : révèle les contraintes que modèles et ports doivent représenter ;
  - API : améliore la traçabilité future, sans créer d’endpoint ;
  - SQLite/données : métadonnées read-only uniquement ; état actuel `MISSING` ;
  - Migration : vérification des préconditions seulement, aucune exécution ;
  - Tests : futurs contrats de schéma liés au hash.
- Dépendances : racine indépendante ; `OD-06` et l’option C de `OD-07` en dépendent.
- Risque si différée : aucune clôture data-model/migration n’est défendable et `OD-06` reste conditionnelle.

## 4 — OD-08 · Frontière durable de gouvernance calibration

**Enjeu.** Les invariants durables de calibration coexistent avec des contrôles V4/V5.x issus d’incidents et des autorisations consommées. Il faut définir ce qui reste policy active, historique immuable ou capacité dépréciée.

- Règles/findings : `CR-036` à `CR-039`, `BRF-008`, `BRF-016`.
- Option A — Conserver blind scoring, strong-only, autorisation exacte et lignée certifiée ; archiver les mécaniques V4/V5.x ; maintenir `RELEASE_THRESHOLD = NONE` (`CR-038 REWRITE + CONSOLIDATE + ADD_TESTS`).
- Option B — Garder tous les contrôles versionnés comme policy canonique active (`CR-038/039 KEEP + ADD_TESTS`).
- Option C — Déprécier toute future exécution live et conserver les preuves en lecture seule (`CR-038 DEPRECATE`, `CR-039 KEEP`, `CR-036 REWRITE`).
- Recommandation : **Option A**.
- Confiance : **HIGH**.
- Justification :
  - conserve les invariants de sécurité et de lignée ;
  - sépare policy durable et réparation historique ;
  - réduit la surface de maintenance ;
  - n’infère ni route runtime ni seuil de release.
- Impacts :
  - Produit : calibration reste une preuve, pas une autorité de livraison ;
  - Domain/Application : aucune dépendance production ou route nouvelle ;
  - API : aucun endpoint provider/seuil ;
  - SQLite/données : aucune dépendance ;
  - Migration : aucune ;
  - Tests : policy générale et intégrité de l’historique.
- Dépendances : racine indépendante.
- Risque si différée : les règles incidentielles restent confondues avec la policy durable, mais l’autorisation live demeure consommée/false.

## 5 — OD-03 · Propriétaires Application de CAP-R02/A01/A02

**Enjeu.** Les routes read-production, validation déterministe et promotion existent comme métadonnées sans use cases Application concrets. Le propriétaire doit choisir la frontière et l’ordre de livraison de ces autorités métier.

- Règles/findings : `CR-005`, `CR-031`, `CR-041`, `BRF-003`, `BRF-007`.
- Option A — Trois propriétaires bornés, livrés dans l’ordre CAP-R02 puis CAP-A01 puis CAP-A02 (`CR-041 IMPLEMENT + ADD_TESTS`, `CR-005/031 KEEP`).
- Option B — Un module Application de cycle de vie avec trois handlers et autorités distincts (`CR-041 IMPLEMENT`, `CR-005 CONSOLIDATE`, `CR-031 ADD_TESTS`).
- Option C — Déclarer les trois capacités hors scope et empêcher les routes de suggérer une implémentation (`CR-041 DEPRECATE + REWRITE + ADD_TESTS`).
- Recommandation : **Option A**.
- Confiance : **HIGH**.
- Justification :
  - préserve la séparation lecture/validation/promotion ;
  - évite qu’un routeur ou adapter devienne autorité métier ;
  - permet des lots petits et ordonnés ;
  - maintient les agents derrière Application.
- Impacts :
  - Produit : complète progressivement la chaîne de cycle de vie ;
  - Domain/Application : trois query/commands et handoffs explicites ;
  - API : crée les prérequis, sans autoriser l’exposition ;
  - SQLite/données : futurs ports seulement, aucun SQL direct ;
  - Migration : uniquement si un modèle approuvé l’exige plus tard ;
  - Tests : use cases, transitions et tests négatifs d’autorité.
- Dépendances : dépend de `OD-01`.
- Risque si différée : les routes restent non autoritatives et le cycle de vie produit demeure incomplet.

## 6 — OD-06 · Propriété des dix familles de littéraux SQLite

**Enjeu.** Des statuts, types, titres, acteurs et valeurs par défaut sont actuellement définis par l’adapter de persistance sans propriétaire métier consolidé. Leur alignement ne peut pas être finalisé sans preuve du schéma externe.

- Règles/findings : `CR-015`, `BRF-006`, `BRF-013`.
- Option A — Attribuer chaque vocabulaire à son bounded context Domain/Application et traduire explicitement dans l’adapter (`CR-015 REWRITE + ALIGN_DATA_MODEL + ADD_TESTS`).
- Option B — Définir un vocabulaire transverse au niveau Application, avec traduction Domain quand nécessaire (`CR-015 CONSOLIDATE + ALIGN_DATA_MODEL + ADD_TESTS`).
- Option C — Déclarer les valeurs techniques uniquement, les geler et interdire leur interprétation comme états métier (`CR-015 DEPRECATE + KEEP + ADD_TESTS`).
- Recommandation : **Option A**.
- Confiance : **HIGH**.
- Justification :
  - respecte l’ownership par module ;
  - empêche l’infrastructure de créer la règle métier ;
  - évite de spécialiser `shared_kernel` ;
  - rend les traductions et transitions testables.
- Impacts :
  - Produit : clarifie la signification du cycle de vie ;
  - Domain/Application : enums/value objects et defaults possédés par contexte ;
  - API : expose seulement des valeurs métier traduites ;
  - SQLite/données : alignement conditionné au vrai schéma ; preuve actuelle `MISSING` ;
  - Migration : possible seulement si les valeurs stockées doivent changer ;
  - Tests : transitions et conformité adapter/schéma.
- Dépendances : dépend de `OD-05`.
- Risque si différée : les littéraux restent une dette technique et ne doivent être exposés comme vocabulaire canonique.

## 7 — OD-07 · Scope READ-15 `version_ref` et `include`

**Enjeu.** Le use case livré accepte uniquement `resource_ref`, tandis que `version_ref` et `include` sont documentés comme différés. Le propriétaire doit supprimer cette promesse active, la réserver explicitement ou autoriser une future extension.

- Règles/findings : `CR-009`, `BRF-014`.
- Option A — Déprécier les options du scope READ-15 actif et exiger un nouveau contrat versionné pour un besoin futur (`CR-009 DEPRECATE + REWRITE + ADD_TESTS`).
- Option B — Conserver les noms comme réservés, avec rejet fail-closed obligatoire aujourd’hui (`CR-009 KEEP + ADD_TESTS`).
- Option C — Autoriser une future implémentation après exigences consommateur et preuve SQLite (`CR-009 IMPLEMENT + ALIGN_DATA_MODEL + ALIGN_API + ADD_TESTS`).
- Recommandation : **Option A**.
- Confiance : **MEDIUM**.
- Justification :
  - correspond exactement au contrat implémenté ;
  - n’invente pas de modèle de version ;
  - réduit la surface d’entrée ;
  - laisse un futur use case rouvrir explicitement le besoin.
- Impacts :
  - Produit : frontière READ-15 claire ;
  - Domain/Application : requête actuelle à un champ inchangée ;
  - API : aucune option non supportée ; option C exigerait une surface validée ;
  - SQLite/données : A/B sans preuve ; C conditionnée à une preuve actuellement `MISSING` ;
  - Migration : aucune pour A/B, potentielle pour C ;
  - Tests : dépréciation/rejet ou, pour C, version/include/allowlist.
- Dépendances : dépend de `OD-01`; option C dépend aussi de `OD-05` et de la preuve SQLite.
- Risque si différée : le code reste sûr et étroit, mais l’ambiguïté documentaire et l’absence de test persistent.

## 8 — OD-04 · Premier scope `/api/v2`

**Enjeu.** Onze règles sont exposables mais aucun endpoint HTTP n’existe. Il faut choisir un premier scope dont l’API reste un adapter vers Application, jamais vers SQL ou un repository.

- Règles/findings : `CR-006`, `CR-007`, `CR-008`, `CR-041`, `BRF-004`.
- Option A — Exposer uniquement le lookup Resource READ-15 en lecture seule, traduit vers `GetResourceQuery` (`CR-006/007/008 ALIGN_API`, `CR-041 IMPLEMENT + ADD_TESTS`).
- Option B — Exposer read-production, validation et promotion après implémentation de leurs propriétaires Application (`CR-041 IMPLEMENT + ALIGN_API`, `CR-005 ADD_TESTS`).
- Option C — Retirer l’HTTP du scope courant et conserver uniquement les inbounds Application (`CR-041 DEPRECATE + REWRITE`).
- Recommandation : **Option A**.
- Confiance : **HIGH**.
- Justification :
  - READ-15 est le seul slice Application concret ;
  - surface read-only minimale ;
  - réutilise les erreurs et validations existantes ;
  - permet des tests stricts d’absence d’accès direct au store.
- Impacts :
  - Produit : plus petit accès HTTP utile ;
  - Domain/Application : aucune nouvelle règle, délégation au query existant ;
  - API : un endpoint borné avec validation et mapping `RES_NOT_FOUND` ;
  - SQLite/données : accès indirect via `OP-03`, aucune nouvelle preuve pour décider A ;
  - Migration : aucune attendue ;
  - Tests : contrat, validation, not-found, minimisation et architecture.
- Dépendances : option A utilise l’owner Resource existant ; toute option non-resource dépend de `OD-03`.
- Risque si différée : `/api/v2` reste à `0/11` règles exposées, sans compromettre les règles métier internes.
