# H2_READ15_LOCAL_STDLIB_V1 — Évidence d'implémentation

## Verdict

**IMPLEMENTED_AND_VALIDATED_WITH_EXPLICIT_REAL_SEED_EXCLUSION — LOCAL_COMMIT_PENDING.**

Baseline et HEAD PRE : 24b7a9850bc4644391dee2307c8a8a31036cd503.
Le SHA du commit local est volontairement absent de ce fichier pré-commit ; il
doit être rapporté après création et contrôle du commit, sans auto-référence.
H3 n'est pas démarrée.

## 1. Autorité réellement reçue

Le propriétaire a approuvé D-SOURCE, D-GUARD et D-INCREMENT pour
H2_READ15_LOCAL_STDLIB_V1, puis a autorisé l'extension A7 sur la même baseline :

- ajout de tests/architecture/test_resource_ref_contract_fitness.py au
  périmètre des fichiers existants modifiables ;
- remplacement de la seule assertion interdisant encore toute présence de
  READ-15 ;
- contrôle positif du registre READ-15 fermé, sans exemption générale ;
- A1–A6 et toutes les autres assertions conservées dans leur portée initiale ;
- commit local cohérent autorisé seulement après réussite des contrôles.

Les permissions restent limitées aux sockets HTTP loopback et aux fixtures
SQLite synthétiques temporaires hors dépôt. Le seed, ses sidecars, les données
et migrations utilisateur, le réseau externe, les fournisseurs, credentials,
push, merge et H3 restent interdits.

Bindings conservés :

- source reconciliation :
  a8dd8edc13d505e504a3983bf5598a834f2fb57ba4fead0d3545f1d2848448d3 ;
- proposition A1–A6 :
  f019d1e74e079ca2ecfc48f77da8ef3bee6904affa59346b48b59d8d9840a80c ;
- contrat : READ15-HTTP-LOCAL-1.0 ;
- ADR : ADR-P12-069.

Le bundle d'extension a été lu comme proposition technique et non comme
autorité autonome. Son SHA-256 est
8081e140c856f1d4039200f245b0960b2da1c2fb05fece4ff3fa95434051888b ;
ses cinq entrées manifestées ont été vérifiées.

## 2. Extension A7

Fichier :
tests/architecture/test_resource_ref_contract_fitness.py.

Nodeid historique conservé :
tests/architecture/test_resource_ref_contract_fitness.py::test_read15_keeps_one_field_and_deprecations_without_http_implementation.
Le nom historique n'est pas utilisé comme vérité fonctionnelle ; le contenu
du test porte le contrat courant.

SHA-256 PRE :
3c06247fa39b27a7a015aee0431753406cf19a97113ecc5c7640e4685fcafdaf.
Dernier commit PRE :
e2c43184a272491371b73131170db488cf3157d6.

Assertion PRE : absence générale de la chaîne
/api/v2/resources/{resource_ref} dans tous les fichiers Python backend.

Assertion POST : égalité stricte de ROUTE_SPECS avec les quatre entrées
approuvées, dont une seule opération métier :

1. GET /api/v2/resources/{resource_ref} ;
2. GET/HEAD / ;
3. GET/HEAD /assets/app.js ;
4. GET/HEAD /assets/styles.css.

SHA-256 POST :
66b6b6bfafc300c5298d722417c80a483f39fafb4aa6b158b54aedfda8e11f6f.

Les six assertions précédentes du nodeid restent inchangées : DTO à un champ,
path parameter unique, query vide, preuve historique endpoint_implemented=false,
et dépréciations version_ref/include. Les trois autres tests et leurs helpers
restent identiques à la baseline.

Le fichier H2 déjà autorisé
tests/architecture/test_local_browser_product_boundary.py contient la
non-régression A7 : registre exact accepté ; cinquième route ajoutée au
registre rejetée ; route /api/v2 déclarée hors de routes.py rejetée.
Le contrôle analyse les octets présents et ne dépend pas du statut Git.

## 3. Implémentation livrée

Inventaire H2 final : 21 chemins, soit :

- quatre guards existants modifiés pour A1–A7 ;
- huit créations code/assets ;
- cinq créations de tests ;
- quatre documents H2.

La surface fonctionnelle reste inchangée par A7 : une seule opération READ-15,
trois assets exacts, aucun body/query/version_ref/include, aucune route
technique additionnelle. Les handlers délèguent à l'inbound Application ; ils
n'importent ni SQL, repository, domaine, provider ou SDK externe.

Le serveur stdlib applique le contrat B04 : bind loopback explicite, registre
fermé, budgets d'entrée bruts, HTTP/1.0 fermé, absence de bannière/log brut et
rejets Host/Origin/framing avant Application. La composition reçoit une
fixture existante, en vérifie le hash et utilise l'adaptateur SQLite en lecture
seule/query-only, sans bootstrap ni migration.

À la suite d'un échec intermittent dans la suite globale, le lifecycle a été
durci dans le fichier serveur déjà autorisé : un signal d'arrêt est consulté
pendant la lecture bornée, avec polling interne de 100 ms. Le délai absolu
d'entrée reste 5 s et le contrat HTTP ne change pas. Cela évite de dépendre du
réveil immédiat d'un recv Windows par shutdown sous charge.

## 4. Contrôles exécutés

### A7 ciblée

- guard ResourceRef + guard produit H2 : **29 passed** ;
- contre-exemples route interne supplémentaire et route hors registre :
  rejetés ;
- stress lifecycle après correction :
  **12/12 passed** sur
  test_stop_interrupts_incomplete_request_and_flushes.

### Ensemble ciblé H2 final

Quatorze fichiers H2/B03/B04/F/Application/ResourceRef ont été exécutés avec
--import-mode=importlib, cache pytest désactivé, basetemp et bytecode hors
dépôt :

**186 passed, 0 failed, 0 skipped.**

JUnit SHA-256 :
0f94850024df5f2a6e54174227ce922f5755427aee9bd9c064e5668db6e7c84c.

Les 186 tests incluent les réponses synthétiques trouvée, absente et invalide,
les quatre champs exacts, les erreurs publiques, les rejets
query/version_ref/include/body, l'intégration HTTP → Application → port →
SQLite read-only, les limites d'entrée, le lifecycle, OBS_A et les guards
positifs/négatifs.

### Suite de fin d'incrément

Une première invocation globale a trouvé :
5043 passed, 28 skipped, 1 failed. L'unique échec était
tests/non_functional/test_retrieval_quality_real_gate.py::test_retrieval_quality_real_gate_is_reproducible_on_two_fresh_runtimes,
qui exige le seed réel et échoue avec CANONICAL_SEED_REQUIRED.

Cette tentative n'a ouvert, lu ou haché aucun SQLite réel. Elle a néanmoins
effectué une consultation read-only de métadonnée is_file() sur le chemin
runtime par défaut avant l'échec. Cet écart de procédure est consigné
explicitement : aucun contenu, sidecar ou credential n'a été accédé.

Une recherche ciblée a confirmé qu'il s'agit du seul test non fonctionnel qui
appelle directement load_sqlite_paths(os.environ).canonical_seed_path sans
opt-in préalable. La suite autorisée a donc été rejouée avec l'unique exclusion
d'invocation suivante, motivée par l'interdiction propriétaire et non par une
régression :
--ignore tests/non_functional/test_retrieval_quality_real_gate.py.
Ce test est **NOT_RUN / NOT_PASS**.

Une première reprise autorisée a révélé l'échec lifecycle intermittent décrit
au §3 : 5042 passed, 28 skipped, 1 failed. Après correction, stress-test et
rejeu ciblé, la passe globale finale autorisée donne :

**5043 passed, 28 skipped, 0 failed.**

JUnit final SHA-256 :
05de4e64bb73a128cf1df8db729c445082ca846c34527cfea7ed11c4b445de2f.

Les 28 skips sont préexistants : gates seed/runtime/provider explicites et deux
tests de liens symboliques indisponibles sous cet environnement Windows.
Aucun skip, xfail, marker, fichier de configuration ou code de test n'a été
ajouté pour les produire.

### Qualité et environnement

- Ruff, dépôt complet, --no-cache : PASS ;
- mypy backend : **688 fichiers**, zéro erreur ;
- compileall -q backend, pycache hors dépôt : PASS ;
- pip check : aucune dépendance cassée ;
- aucune dépendance ou lock ajouté/modifié ;
- les noms de tests unit/integration identiques imposent
  --import-mode=importlib au niveau de l'invocation ; aucun package ou
  renommage hors inventaire n'a été créé.

## 5. Confidentialité, données et lifecycle

Toutes les fixtures SQLite sont créées à neuf dans le temp système avec des
contenus marqués synthétiques. Elles ne sont ni des copies ni des dérivés du
seed ou d'une runtime utilisateur. Les connexions, serveurs et sessions
observabilité sont fermés ; aucun serveur n'est laissé actif.

La barrière de processus des validations supprime les variables
OpenAI/Anthropic/gates réelles, refuse les ouvertures SQLite hors temp et
limite connect/bind/DNS/URL aux littéraux loopback. Aucun appel fournisseur,
credential, réseau externe, téléchargement ou résolution de dépendance n'a eu
lieu.

    DATA = SYNTHETIC_ONLY
    SQLITE_REAL_OPEN_READ_HASH = 0
    USER_RUNTIME_METADATA_STAT = 1_UNINTENDED_READONLY_NO_CONTENT
    USER_MIGRATIONS = 0
    EXTERNAL_NETWORK_CALLS = 0
    PROVIDER_CALLS = 0
    CREDENTIAL_RESOLUTION = 0
    LOCK_CHANGES = 0
    PERSISTENT_CONFIGURATION_CHANGES = 0
    PUSH = NONE
    MERGE = NONE
    H3_STARTED = FALSE

## 6. Intégrité et limites

Les six sources H1 et cinq sources H1A restent hors du commit H2 et inchangées
à leurs empreintes historiques. Les 48 identités B07 protégées restent
inchangées. Le manifeste H2 couvre les vingt autres chemins de l'inventaire
final sans auto-référence.

Le commit local doit contenir l'incrément H2 cohérent complet, pas le seul
guard A7. Avant commit : inventaire staged exact, diff complet, absence de
secret/runtime/temp et git diff --cached --check. Après commit : HEAD,
inventaire et guards revérifiés. Aucun push ni merge.

Cet incrément ne clôt ni l'ensemble H2, ni 12.18, ni le produit. Restent
notamment ouverts : les annexes Phase 8 et la source exacte 12.1, recherche et
workflows complets, CAP-R02/A01/A02, commandes HTTP, runtime réelle, packaging
et recette H3. Aucune interaction navigateur graphique n'a été réalisée :
les preuves couvrent HTTP loopback et assets statiques seulement.
