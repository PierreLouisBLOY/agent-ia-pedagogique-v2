# ADR LU-PRODUIT-01 — permission produit bornée et consentement local

Statut : AMENDED_FOR_DISTINCT_PREIMPLEMENTATION_REVIEW. 2026-10-11. Aucun effet live, grant actif ou credential créé. Producteur S4. La revue distincte du premier prototype a demandé les trois précisions ci-dessous ; cet amendement doit être relu avant code runtime P1.

## Besoin et frontière

Le G1 relu fixe une préparation Application volatile exacte. Il ne permet pas au propriétaire de lancer V2, choisir un contexte admissible et produire sans intervention de Codex entre opérations. Ne pas l'élargir silencieusement : ajouter une permission produit d'infrastructure explicitement adoptée, désactivée par défaut, qui permet au produit de construire un G1 exact après un consentement du propriétaire dans l'UI locale. Les anciennes permissions Boréal/MEGA/R2 restent exclues. Le navigateur ne fournit jamais un JSON grant, une URL, un fichier, un quota ou une clé.

## P1 — contrat fermé de permission produit proposé

`P0-PRODUCT-CREATE-PERMISSION-1.0` :

```
schema, owner_decision_sha256, baseline_commit, source_tree_sha256, package_sha256,
runtime_sha256, profile_sha256, output_schema_sha256, tokenizer_manifest_sha256,
tariff_sha256, receipt_root_sha256, permission_namespace_sha256,
operator_delegation_sha256, source_admission_manifest_sha256,
issued_at_utc, expires_at_utc, allowed_families, allowed_levels,
institutional_catalog_sha256, selected_admitted_sources_only,
excluded_oracles_and_private_evidence, require_exact_local_consent,
local_operator_delegation_accepted,
provider, model, endpoint, reasoning, tier, max_output_tokens,
max_calls, count_calls, review_calls, modify_calls, retry, fallback, parallelism,
per_call_ceiling_usd, cumulative_ceiling_usd, live_authorized, transfer_authorized
```

Identités vérifiées par la factory, hashes complets et baseline de 40 caractères hexadécimaux minuscules ; source/package/runtime/catalogue exacts. Familles et niveaux non vides parmi les enums P0 courantes ; sélection institutionnelle exacte et sources admises authentifiées Application obligatoires. Les quatre booléens de contrôle sont vrais, exclusion obligatoire des oracles/corrigés de référence et pièces privées non admises. CREATE uniquement ; autres opérations/COUNT 0, retry0/fallbackNONE/parallélisme1 ; profil Terra low/default, Responses, sortie4096, flags/outils G1 inchangés. Nouvelle fenêtre UTC propriétaire finie, ≤30 jours maximum proposé (valeur exacte à adopter) ; aucun renouvellement automatique. Maxcalls entier 1..14 proposé, plafond par appel ≤0,14USD, cumul strictement positif ≤maxcalls×plafond par appel. Les valeurs opérationnelles finales restent à choisir dans la décision groupée, sans activation ici.

## Opérateur local et admission des sources

Le nonce et les contrôles Host/Origin/intent protègent le transport local ; ils n'authentifient pas une personne et ne prouvent pas qu'elle est le propriétaire. La décision P1 devra accepter explicitement la délégation de consentement à l'opérateur du canal local qualifié, sur le compte Windows et le profil exact liés par `operator_delegation_sha256`. Aucun attribut HTTP « owner » ne crée cette délégation. Sans cette adoption ou si l'identité du profil local change, STOP. L'UI nomme « consentement de l'opérateur local délégué » et indique que l'acceptation pédagogique reste séparée.

Le booléen `selected_admitted_sources_only`, un statut ACTIVE/CURRENT, une correspondance de notion ou l'absence d'autorité connue ne valent pas admission. P1 lie un **manifeste exact de sources**, adopté une fois dans la décision groupée ; son candidat reste NON_ADOPTE durant la qualification. Chaque ligne conserve ID notion/source, type, version/checksum, locator, SHA de l'extrait complet, provenance et statut/autorité réellement disponibles, et SHA du scope exact. Chaque sélection est relue par le lecteur Application authentifié et confrontée à cette ligne, puis à la résolution institutionnelle exacte. Une query Application émet un reçu `P0-SOURCE-ADMISSION-RECEIPT-1.0` par référence, avec les mêmes identités, `admission_manifest_sha256`, `admission_scope_sha256`, `owner_admission_sha256` et `institutional_resolution_sha256`. Une source absente, une identité ou un extrait changé, une troncature, une relation contextuelle non admise, une pièce privée ou un oracle interdit sont refusés. Le contrôle du reçu ne dépend jamais d'un booléen fourni par le navigateur.

L'admission de transmission d'un contenu local et son autorité disciplinaire sont distinctes. UNKNOWN/NONE restent UNKNOWN/NONE dans le reçu, la preview, les contrôles et la sauvegarde. Un propriétaire peut adopter explicitement une ligne pour usage local sans lui conférer une autorité officielle ni une validation pédagogique. `CANONICAL_NOTION_ONLY` atteste uniquement l'identité de notion ; `EXACT_CONTEXT_ADMITTED` atteste la relation exacte existante, sans enrichissement implicite. La résolution globale doit être RESOLVED_ADMITTED et revalidée ; tout CONTENT_GAP reste bloquant. Le manifeste et les reçus exhaustifs ne sont pas remplacés par les 37 exemples de capture.

Le tarif lié est admis explicitement pour la période propriétaire ; retrieved_at≤issued_at≤now<expires_at. Un changement de code/package/runtime/catalogue/tokenizer/tarif suspend la permission. Son identité n'autorise aucun transfert autre que les préparations admises et explicitement confirmées dans l'UI.

## Parcours proposé, sans intermédiaire Codex

1. Lancement explicite `normal` avec profil privé vérifié, permission propriétaire adoptée et resolver opaque injecté par le canal natif masqué déjà prévu. Mode local par défaut : aucun chargement de permission/clé et aucun transport. Pas d'environnement credential ambiant ni nouvelle acquisition implicite.
2. UI existante : intention → contexte confirmé → sélection institutionnelle exacte → extraits admis via Application → prepare. Rien n'est envoyé à ce stade.
3. Companion `POST /api/v2/p0/consent-preview`, fermé command_id/preparation_ref/preparation_sha256. Les règles Host/Origin/nonce/local-intent existantes s'appliquent. Query Application lit la préparation existante immuable et les reçus exacts ci-dessus, prépare le même body Responses canonique, puis factory vérifie P1 et F1. Le retour affiche le contexte exact, les reçus sources avec ID/version/provenance/autorité et extraits réellement transmis, le modèle/destination, bodySHA/taille, maxoutput, le préflight F1 complet et sa borne/coût/plafonds restants et les limites review/usages/calculs. Aucun oracle de référence n'est joint. Ce retour n'est ni grant ni réservation. Un previewSHA lie tous les éléments montrés et expires≤15 minutes ; état serveur borné, aucune permission créée par un champ HTTP.
4. Le propriétaire coche l'accord explicite de transfert/conservation de sécurité et de coût maximal affiché, puis déclenche `POST /api/v2/p0/consent-generate`. Objet fermé command_id/preparation_ref/preparation_sha256/preview_sha256/transfer_accepted/cost_bound_accepted. Les deux booléens doivent être vrais et les valeurs identiques à la preview. Recalcul immédiat de la préparation/body/proofs/source/package/P1/F1 ; tout changement STOP et exige une nouvelle preview visible, sans envoi automatique.
5. La factory construit en mémoire un **G1 nouveau exact**, lié à P1 et au consentement exact, durée min(120minutes, P1expiry). Elle réserve atomiquement dans le budget privé P1 avant credential/transport. Puis P0GenerationService normal consomme la préparation et utilise l'adaptateur G1/AG03 relu. Pas de deuxième appel généré depuis un consentement consommé, même après timeout, déconnexion ou redémarrage.
6. Réponse technique capturée, guards/validation Application, conservation Application de sécurité explicite, affichage source/contrôles, revision locale, sauvegarde/reprise/export existants. AG04 non lié en CREATE-only ; qualité non signée, source usage non déclaré dans le schéma distinct des références fournies. Une récupération confirmée ne requiert aucun consentement nouveau et ne réactive aucun droit, selon l'ADR de reprise relue.

## Budget et namespace privés — opération technique spécifique

Un ledger append-only neuf, lié à P1, outsideGit sous racine privée qualifiée. Les réservations pessimistes sont des reçus immuables et ne sont jamais remboursées automatiquement après échec. Sous un verrou Windows spécifique conservé en fichier, ouvert exclusivement par handle sans modifier son contenu, la factory relit les reçus F02, calcule somme/maxcalls, refuse les incohérences et publie un slot exclusif nouveau lié au G1/consentement. **Toujours sous ce verrou et avant le slot**, elle recalcule le vrai F1 depuis les octets canoniques courants, le tokenizer local vérifié et le tarif admis : égalité intégrale du préflight à celui montré dans la preview, égalité de sa borne au coût annoncé et réservé. Un hash de preview recalculé ne rend pas recevable un coût diminué. Le prototype pur exige un paramètre de préflight frais identique ; seul le futur test de raccord runtime prouvera son recalcul réel. Après publication, elle ferme le handle ; aucune suppression de lock/slot historique. Parents retenus contre substitution, fichiers no-follow, publication exclusive actuelle réutilisée. Pas de simple mutex mémoire pour garantir le cumul entre processus. Aucun compteur fourni par le navigateur ou fichier de budget mutable écrasé.

Le reçu RESERVED G1 reste obligatoire avant resolver. Une réservation budget réussie suivie d'un échec de reçu G1 consomme ce slot pessimiste ; aucune compensation cachée. Maxcalls et cumul ne peuvent être dépassés en concurrence. Réserver et envoyer restent distincts ; publier une preuve impossible interdit le fournisseur.

## Contrats, revue et qualification

Relire P1, preview/consent, construction G1 et ledger exacts avant code de ces nouveaux chemins. Le prototype pur vérifie le scope P1, la dérivation identitaire du G1 et la majoration cumulative ; il ne constitue pas une preuve d'atomicité Windows. Les tests de raccord devront ensuite exercer vrais nonce/Origin/Host, mutation context/reference/body/preflight/clock/permission, consentement absent/false/substitué/consommé, concurrence multi-instance ledger, publication impossible, défaut secret/transport, timeout et reprise attestée sans redispatch.

Le profil exact et sa décision groupée future réunissent code/package/runtime/catalogue, fournisseur, tarif admis/période, tokenizer officiel vérifié, racine/ledger privé, périmètre sources, plafond/periode/maxcalls et consentement UI. Aucun accord tarifaire ou fournisseur n'est déduit de l'ADR. Aucun credential ni appel réel dans ce lot de qualification. La preuve à doubles teste la mécanique et ne prouve aucune intelligence fournisseur ou adoption pédagogique.

Retour arrière : mode sans fournisseur et absence d'injection P1. Tous reçus et versions restent conservés. Aucun changement des anciens contrats HTTP, grants, scanner global, seed/runtime original ou gates historiques.
