# Contrat proposé — recherche lexicale locale puis READ-15

Statut de toutes les règles marquées P : PROPOSED_NOT_APPROVED. Nom de travail : SEARCH-HTTP-LOCAL-1.0 ; scope proposé H2_LOCAL_LEXICAL_SEARCH_V1. Ni numéro canonique préexistant ni autorisation d’exécution. IMPLEMENTATION_AUTHORIZED = FALSE.

## 1. Objectif et décision recommandée

P01 — Rechercher des passages locaux indexés à partir de mots, puis ouvrir via READ-15 ceux reliés directement à une ressource existante. Montrer honnêtement les passages non ouvrables. C’est une découverte lexicale bornée, pas un moteur de pertinence pédagogique ni une promesse de recherche exhaustive de toutes les ressources.

Recommandation unique : réutiliser OP-11 LEXICAL + admission F2A + OP-13 ; créer le use case de découverte M03 et son pont outbound ; conserver OP-03/READ-15. Alternative non retenue : ne montrer que RESOURCE. Sans nouveau contrat de recherche filtrée en persistance, cela masquerait les hits non-RESOURCE et pourrait produire une liste vide artificielle dans la fenêtre bornée. Une recherche de toutes les ressources, indexées ou non, exigerait une évolution de persistance supplémentaire et n’est pas proposée ici.

Exclusions : semantic/query embedding, RRF hybride, expansion relationnelle, tri pédagogique, recherche dans les documents complets, fichiers utilisateur, chemins/URL arbitraires, édition/indexation/migration, génération, review, évaluation, promotion, provider, packaging et H3. La complétude SCN-02 historique et la recette de la bibliothèque réelle ne sont pas déclarées acquises.

## 2. HTTP et requête fermée

P02 — Ajouter exactement GET /api/v2/search, sans slash final. Les quatre routes actuelles restent identiques et dans le même hôte. Le tuple proposé, dans cet ordre :

```text
GET       /api/v2/resources/{resource_ref}
GET       /api/v2/search
GET,HEAD  /
GET,HEAD  /assets/app.js
GET,HEAD  /assets/styles.css
```

Le chemin recherche est disjoint du préfixe /api/v2/resources/. /api/v2/resources/search reste un lookup de ResourceRef, pas une recherche. Pas de nouvelle route d’ouverture : le client utilise READ-15 existant. HEAD recherche = 405. Aucune commande POST/PUT/PATCH/DELETE, aucun nouveau preflight.

P03 — Paramètres query stricts :

| Champ | Contrat proposé | Justification |
| --- | --- | --- |
| q | Une chaîne obligatoire, une seule occurrence ; vide/espaces seuls rejetés | Une seule intention lexicale, aucun scope libre |
| limit | Optionnel ; défaut 10 ; décimal ASCII canonique de 1 à 20, sans signe ni zéro initial | Liste UI et fanout bornés |
| Tout autre champ | 400, y compris offset, page, sort, filters, level, topic, version_ref, include | Pas de fonctionnalité ou policy implicite |
| Body | Interdit, même sur recherche | Héritage du contrat transport READ-15 |
| Pagination | Aucune ; pas de token, offset ou total | Ne pas promettre une couverture que la fenêtre ne prouve pas |

P04 — Décodage réservé à ce chemin exact : le target brut reste ASCII, <=8192 octets ; pas de forme absolue, //, fragment, backslash, contrôle brut ni échappement % invalide. Extraire le path sans le décoder. Query sous forme key=value, séparateur & uniquement ; segment vide, clé vide, doublon ou clé encodée refusés. Les clés sont littéralement q et limit. Décoder chaque valeur une fois avec + vers espace, percent-decoding puis UTF-8 strict. Refuser un motif %HH restant dans la valeur décodée (pas de double encodage). Un % isolé peut être une ponctuation de q. Ordre des deux clés indifférent ; le point-virgule ne sépare jamais les paramètres. limit après décodage respecte le décimal canonique.

Une erreur sur q/limit après identification du chemin recherche donne SEARCH_REQUEST_REJECTED. Une erreur de framing HTTP ou de target global conserve les codes transport historiques (dont READ15_REQUEST_REJECTED) : aucune refonte du contrat pur B04. /api/v2/search/ et chemin inconnu sans violation globale donnent 404. Si méthode et paramètres sont simultanément invalides sur la route identifiée, méthode non autorisée prioritaire, 405.

P05 — Validation métier de q, dans le nouveau SearchText de M03 :

1. Rejeter avant normalisation tout caractère Unicode de catégorie Cc, Cf ou Cs ; longueur décodée 1..256 points de code. Aucun NUL, contrôle bidi invisible ou surrogate accepté.
2. Normaliser NFC ; convertir les séparateurs Unicode Zs/Zl/Zp en espace ASCII ; replier les espaces consécutifs et retirer les bords. Longueur normalisée 1..256.
3. Former les tokens par runs commençant par une lettre Unicode L* ou un nombre N*, prolongés par L*, N* ou M* ; tout autre caractère sépare les tokens. Une marque isolée ne commence pas un token.
4. Exiger 1..12 tokens, chacun 1..64 points de code ; conserver leur ordre, leur casse et les répétitions. Aucune translittération, accent supprimé ou stemming métier ajouté.

Les valeurs de ces bornes, la normalisation et la syntaxe sont proposées, pas héritées d’un OpenAPI retrouvé. Elles limitent la surface d’entrée et permettent le français. L’HTTP ne copie pas cette validation : il décode ; l’invocation Application injectée valide avant tout target.validate() ou ouverture de connexion. Inbound Application ferme également le payload et les types pour les autres appelants.

P06 — Recherche de tous les tokens, pas une syntaxe FTS publique. Le pont outbound construit une expression FTS5 en mettant chaque token entre doubles guillemets et en les joignant par AND ; l’expression est passée comme paramètre SQL à OP-11 existant. Les opérateurs saisis (OR, NOT), guillemets, *, parenthèses ou apostrophes ne deviennent jamais des opérateurs du client. Exemple : q=fractions+proportionnelles devient deux termes littéraux conjoints ; q=alpha+OR+beta cherche aussi le terme littéral OR. Le tokenizer déjà défini par la fixture/runtime FTS5 décide des correspondances ; aucune promesse de parité sur un schéma réel non inspecté.

## 3. Admission, ordre et fenêtre

H01 — ADR-P12-061 : chaque candidat doit passer is_admissible indépendamment de STRUCTURED ; ni rang lexical, ni présence dans un canal, ni disponibilité d’une ressource ne remplace ce contrôle. La politique ne devient pas un simple filter UI.

P07 — Paramétrage technique fermé, construit dans le pont outbound uniquement :

```text
channel = LEXICAL
semantic_backend = None
scope = {}
source_policy = {"kinds": ("canonical",)}
filters = {"active": True}
required_authority = {"basis": "canonical-registry"}
max_items = 100
```

Les contraintes sont compatibles avec _query_constraints_supported existant. Ne jamais accepter ces dictionnaires depuis HTTP, ni appeler STRUCTURED pour fabriquer une allowlist. Aucun appel SEMANTIC, index dérivé, embedding ou fallback fournisseur. Les DTO agent restent dans le pont outbound, jamais dans M03.

H02 — OP-11 existant sélectionne les search_chunk CURRENT reliés à object_registry, impose CANONICAL aux NOTION, ordonne par bm25 ascendant puis sc.id. P08 — Conserver cet ordre déterministe pour un même snapshot et moteur, sans publier le score brut. Une ligne = un passage ; ne pas fusionner deux passages d’un objet. Aucun retri alphabétique, par disponibilité, par type ou « qualité ».

P09 — Fenêtre brute maximale 100 candidats, limite déjà supportée par OP-11. Vérifier l’admission des candidats de cette fenêtre ; éliminer les refus sans exposer leur existence/texte. Choisir les premiers limit passages admis. Pour chaque passage retourné, lire OP-13 seulement après admission et vérifier égalité exacte object_ref, passage_ref et version_or_checksum avec OP-11. Fragment absent ou divergence après admission = échec technique 500, pas un succès vidé silencieusement. Pas de contenu matérialisé pour les refus. Un duplicata de passage inattendu ou une projection malformée échoue techniquement, sans correction inventée.

Renvoi de deux indicateurs bornés : window_full = nombre brut reçu égal à 100 (signal conservateur, pas preuve qu’il existe un 101e) ; more_admitted_in_window = nombre admis supérieur à limit. Aucun total du corpus, compte des refus, offset ou pagination. Une réponse vide peut donc avoir window_full=true : la notice UI explique qu’il faut préciser/reformuler, pas que la bibliothèque est vide.

P10 — Un seul snapshot de lecture par requête pour OP-11/admission/OP-13/OP-03. Le nouveau pont outbound expose un contexte read_snapshot(), ouvre uniquement une transaction de lecture sur la connexion readonly/query_only injectée et la clôt sans commit d’écriture. La factory englobe l’invocation Application dans ce contexte et ferme la connexion dans finally. Aucun SQL dans la factory HTTP, l’inbound ou M03 ; BEGIN/rollback éventuels sont dans le pont outbound. Pas de journal applicatif, cache de résultats ou index créé.

Les bornes de résultat ne garantissent pas une durée SQL maximale sur une base réelle non mesurée ; le timeout d’entrée HTTP de cinq secondes n’est pas présenté comme un timeout de calcul FTS. Ce lot de validation futur utilise de petites fixtures synthétiques, et ne promet pas de performance sur la bibliothèque utilisateur.

## 4. Projection JSON fermée

P11 — Succès 200 ; Content-Type application/json; charset=utf-8. Les seules clés de tête sont data et meta. meta contient seulement correlation_id B03, généré selon le contrat existant. data contient uniquement items, window_full, more_admitted_in_window. Aucune recopie de q, de SQL ou des dictionnaires internes.

Chaque item a exactement :

| Champ | Type / sémantique proposée |
| --- | --- |
| position | int 1..nombre de résultats, ordre lexical après admission, pas un score |
| object_ref | identifiant logique OP-11, non vide, <=256 points de code |
| object_kind | registry_object_type, non vide, <=64 ; pas entity_kind/chunk_type |
| passage_ref | identifiant logique du chunk, non vide, <=256 |
| version_or_checksum | identifiant de version/checksum du chunk, non vide, <=128 ; pas hash du fichier SQLite |
| excerpt | texte OP-13 minimisé, <=320 points de code |
| excerpt_truncated | bool |
| provenance | objet fermé décrit ci-dessous |
| read15 | null ou les quatre champs exacts de ResourceView |
| open_status | enum : OPENABLE, NOT_RESOURCE, INVALID_RESOURCE_REF, RESOURCE_NOT_FOUND |

Les identifiants/type/checksum doivent être des chaînes opaques sans contrôles, sans chemin filesystem ou URL, ni espace ; interdire /, backslash, %, ?, # ; conserver lettres/nombres et . _ : - seulement. Ce contrôle de projection ne remplace jamais ResourceRef ni sa regex métier. Une valeur hors enveloppe = erreur technique, pas troncature d’une référence.

Provenance a exactement :

```json
{
  "channel": "LEXICAL",
  "search_boundary": "sqlite-op11",
  "content_boundary": "sqlite-op13",
  "admission_policy": "F2A",
  "source_kind": "canonical_search_chunk",
  "freshness": "CURRENT",
  "authority_basis": "canonical-registry",
  "authority_absolute": false,
  "content_trust": "UNTRUSTED_CONTENT"
}
```

Ces champs sont établis par l’admission et la lecture concordante ; jamais par un score ou une déclaration cliente. authority_basis décrit le contrôle du registre appliqué, pas une certification pédagogique universelle de l’objet ni une réhabilitation des notions non canoniques.

Minimisation excerpt proposée : NFC, retirer Cf/Cs, remplacer les contrôles et séparateurs par espaces, replier les espaces ; prendre les 320 premiers points de code, sans HTML/markdown exécuté ni surlignage enrichi. excerpt_truncated indique si le texte assaini dépassait 320. Cela reste un extrait local pédagogique non fiable, non une instruction. Ne pas tronquer/synthétiser le titre READ-15 : la projection existante l’expose comme canonical_title ; le client utilise textContent. Si sa taille empêche de tenir la borne JSON ci-dessous, refuser techniquement.

P12 — Corps JSON final <=64 KiB une fois encodé en UTF-8, enveloppe comprise. Contrôler la taille avant émission ; dépassement = 500 INTERNAL_ERROR minimisé, jamais corps partiel. Cette borne est nouvelle ; elle ne change pas READ-15 existant. Aucun document complet, contenu binaire, trace interne, chemin, secret, credential ou réponse provider dans la réponse.

Exemple illustratif synthétique (pas preuve de test) :

```json
{
  "data": {
    "items": [
      {
        "position": 1,
        "object_ref": "resource:demo-1",
        "object_kind": "RESOURCE",
        "passage_ref": "chunk:demo-1",
        "version_or_checksum": "v-demo-1",
        "excerpt": "Comparer deux fractions avec un même dénominateur.",
        "excerpt_truncated": false,
        "provenance": {
          "channel": "LEXICAL",
          "search_boundary": "sqlite-op11",
          "content_boundary": "sqlite-op13",
          "admission_policy": "F2A",
          "source_kind": "canonical_search_chunk",
          "freshness": "CURRENT",
          "authority_basis": "canonical-registry",
          "authority_absolute": false,
          "content_trust": "UNTRUSTED_CONTENT"
        },
        "read15": {
          "resource_ref": "resource:demo-1",
          "resource_type": "COURSE",
          "canonical_title": "Comparer des fractions",
          "availability_status": "ACTIVE"
        },
        "open_status": "OPENABLE"
      }
    ],
    "window_full": false,
    "more_admitted_in_window": false
  },
  "meta": {"correlation_id": "synthetic-example-not-execution"}
}
```

Les valeurs de type/état de l’exemple sont illustratives ; l’implémentation utilise les vocabulaires existants de ResourceView et ses fixtures valides, pas une nouvelle enum issue de cet exemple.

## 5. Ouverture READ-15, sans conversion abusive

H03 — ResourceRef appartient à backend/modules/resource_library/domain/value_objects/resource_ref.py ; aucune copie exécutable de sa regex. GetResourceQuery conserve son contrat et RES_NOT_FOUND.

P13 — Pour les seuls passages admis effectivement retournés :

1. object_kind différent de RESOURCE : read15=null, open_status=NOT_RESOURCE.
2. Type RESOURCE mais ResourceRef(object_ref) invalide : read15=null, INVALID_RESOURCE_REF.
3. Référence valide : invoquer GetResourceQuery via ResourceLibraryInbound avec GetResourceRequest sur le même snapshot et la même CorrelationId. RES_NOT_FOUND : read15=null, RESOURCE_NOT_FOUND.
4. Succès exact : read15 contient seulement resource_ref, resource_type, canonical_title, availability_status ; resource_ref doit être égal à object_ref ; OPENABLE. Toute autre erreur ou mismatch = 500.

Ne pas déduire une liaison depuis document_ref, passage_ref, titre, préfixe, ordre ou voisinage. Ne pas convertir NOTION/PEDAGOGICAL_CONTENT en RESOURCE. La disponibilité conservée ne vaut ni canonicalité, ni autorisation de promotion/livraison strong.

L’action « Ouvrir » n’est offerte que pour OPENABLE ; elle appelle GET READ-15 avec encodeURIComponent(read15.resource_ref), sans query/body/version_ref/include. READ-15 relit son état courant ; un résultat devenu absent reçoit son 404 habituel. Pas de cache ou promesse transactionnelle entre deux requêtes HTTP.

## 6. Erreurs et invariants HTTP conservés

| Cas | Statut / code public | Catégorie |
| --- | --- | --- |
| q absent/vide/invalide, limit ou query non admis sur recherche | 400 SEARCH_REQUEST_REJECTED | validation (nouveau) |
| Framing/target global invalide | 400 READ15_REQUEST_REJECTED | validation (historique conservé) |
| Aucun passage admis | 200, items=[] | Succès vide explicite, jamais erreur masquée |
| Schéma/FTS absent, lecture échouée, projection/provenance divergente, output trop gros | 500 INTERNAL_ERROR | technical |
| Route inconnue | 404 ROUTE_NOT_FOUND | transport |
| Méthode interdite | 405 METHOD_REJECTED | transport |
| Host, Origin, preflight refusé | 403, code B04 correspondant | security |

Enveloppe erreur : seulement error={category,code}, meta={correlation_id}. Aucun message d’exception, stack, q, chemin, SQL, title ou excerpt. L’endpoint recherche ne modifie pas public_error READ-15 : son nouveau mapper traite SEARCH_REQUEST_REJECTED et le serveur sélectionne ce cas explicitement ; tous les codes historiques restent inchangés. Une exception d’infrastructure n’est jamais convertie en RES_NOT_FOUND ou en items=[].

H04 — ADR-P12-069 et schéma HTTP : localhost littéral 127.0.0.1 / ::1, port explicite, Host/Origin exacts, CORS désactivé, aucun DNS/reverse DNS, HTTP/1.0 avec fermeture, un seul traitement simultané, trois assets exacts, target 8 KiB, headers 64 KiB, deadline d’entrée et timeout socket de cinq secondes. Même CSP, absence de bannière/cache/log brut. Aucun élargissement de bind, origine, méthode globale ou service de fichiers.

Le seul assouplissement de la règle globale de target est P04 : tolérer ? avec q/limit sur /api/v2/search uniquement. Le rejet de tout query sur READ-15 et assets demeure, y compris un ? vide. Cette évolution et le tuple fermé sont soumis ensemble à la décision et à G01..G04/U01.

## 7. Chaîne Application et composition proposées

```text
UI locale (3 assets)
  -> GET recherche / API SearchEndpoint, invocation injectée
  -> Application inbound LocalSearchUseCaseInbound.invoke(UseCaseRequest)
  -> LocalSearchInbound.search_local(SearchLocalRequest, CorrelationId)
  -> M03 SearchLocalQuery
  -> LocalSearchPort.admitted_window(text=SearchText, result_limit=limit, candidate_limit=100)
  -> nouveau pont outbound : OP-11 LEXICAL -> F2A -> OP-13 concordant
  -> DTO M03 admis + fenêtre -> liaison ResourceLibraryInbound / OP-03
  -> LocalSearchView -> UseCaseResult -> JSON fermé -> UI
  -> sélection ouvrable -> READ-15 existant
```

P14 — application.search_local_passages est un nouvel identifiant de use case pour l’inbound produit direct, pas une capability ajoutée aux registries agents. Payload fermé {q: str, limit: int} ; bool refusé comme int. DTO input utilise SearchText et limit validés ; output et port outbound ne dépendent ni d’HTTP, SQL, filesystem ni agent_runtime. L’Application recherche consomme les deux ports de M03 et ne connait ni Query FTS, ni connexion.

Signature proposée du port outbound : admitted_window(*, text: SearchText, result_limit: int, candidate_limit: int = 100) -> LocalSearchWindow. LocalSearchWindow contient seulement les passages admis et matérialisés retenus (au plus result_limit), window_full et more_admitted_in_window ; l’admission des 100 candidats éventuels précède la sélection, mais OP-13 ne lit que les passages retenus. L’Application vérifie la cardinalité, conserve leur ordre et effectue la liaison READ-15. L’inbound et la projection HTTP refusent tout outcome incohérent, effet/commande annoncé ou corrélation différente, comme le compartiment READ-15 actuel ; rien n’est accepté comme succès sur la seule présence d’un champ data.

La factory existante reçoit toujours la target explicite. Le reader de recherche est injecté à LocalRead15Service comme paramètre nommé optionnel afin de conserver les constructeurs READ-15 existants ; absence de reader sur une requête recherche = 500, pas branche alternative cachée. build_local_read15 fournit les deux endpoints. Construire les adapters recherche ne fait aucune requête de découverte de schéma ; les anciennes fixtures READ-15 à table resource seule continuent de servir READ-15. Le défaut FTS ne se révèle que sur recherche et échoue explicitement.

Validation métier avant target.validate ; hash explicite avant connect_sqlite(readonly=True, allowed_root=...). Une seule connexion, possédée et fermée par la composition ; ne pas cumuler les close() de wrappers sur une connexion encore utilisée. Aucun build_sqlite_runtime/provisioning, aucun loader d’environnement, seed, migration, credential ou réindexation.

## 8. UI, confidentialité et observabilité

P15 — Ajouter à index.html un formulaire recherche distinct (q + submit ; limit interne par défaut), une zone de statut accessible aria-live et une liste. Conserver les ids/actions READ-15 existants. Résultat : excerpt, type d’objet, références et provenance lisibles ; titre et bouton Ouvrir seulement si prouvés. Notice permanente : « Recherche lexicale dans les passages indexés ; certains résultats ne sont pas des ressources ouvrables. » Notice de fenêtre si window_full ou more_admitted_in_window. Ne pas appeler automatiquement READ-15 pour chaque hit.

app.js : fetch same-origin, credentials omit comme existant, URLSearchParams pour q/limit ; pas de q dans URL de navigation/historique, stockage, console ou télémétrie. Annuler la recherche précédente et ignorer sa réponse tardive ; preventDefault ; état occupé et erreurs minimisées. Un clic explicite sur Ouvrir reprend le lookup existant. Tous les textes sont insérés via textContent ; aucune interprétation HTML, script, lien arbitraire ou contenu enrichi. styles.css seul pour la présentation ; pas de nouvelle bibliothèque/CDN/asset.

H05 — OBS_A inchangée : NDJSON local privé, 5 MiB, cinq fichiers au total, 14 jours, flush <=2s. Réutiliser http_request et corrélation ; route_template vaut /api/v2/search, jamais target+query. En échec de parsing, /{unmatched} et code fermé. Le schéma existant accepte ce template sans modification.

Exclus des logs : q brut ou normalisé, tokens/FTS, tout résultat/excerpt/titre, object_ref/passage_ref/checksum, payload/body, chemins, credentials, réponses providers et exceptions. Pas de hash de requête comme contournement de minimisation. Aucun nouveau label à haute cardinalité. Une panne du sink ne transforme pas la recherche en échec métier. L’arrêt/flush/port occupé sont testés sur fixture seulement après approbation.

## 9. Limite de décision

Toutes les règles P01..P15, y compris ownership M03, noms HTTP/use case, bornes, minimisation, permissions de tests et inventaire exact, forment UNE proposition à approuver. Aucun choix indispensable TO_DEFINE. Si ce contrat ne convient pas à l’objectif de découverte bornée, le propriétaire peut le réviser avant tout code ; le paquet ne prétend pas résoudre les lacunes de données réelles, de sources originales ou de recette complète.
