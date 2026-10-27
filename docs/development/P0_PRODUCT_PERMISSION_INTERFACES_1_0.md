# P0 — interfaces exactes de la permission produit proposée

2026-10-11. PROPOSED_FOR_DISTINCT_PREIMPLEMENTATION_REVIEW. Aucun grant actif, credential ou appel fournisseur. Complément de l'ADR PRODUCT_PERMISSION amendée, sans changement du service P0 existant.

## Admission et délégation — entrées de composition

La configuration normale explicite injecte P1, le tarif F1 admis, le tokenizer local vérifié, le manifeste de sources adopté et la preuve de délégation locale. Ce sont des pièces privées d'infrastructure et des preuves Application ; aucune ne provient d'un objet HTTP, d'un credential ambiant ou d'une ancienne gate. La configuration locale par défaut n'injecte rien. La qualification n'utilise que des doubles déclarés et des permissions synthétiques non actives.

`operator_delegation_sha256` lie une pièce adoptée identifiant le compte/profil Windows qualifié et l'acceptation du consentement d'un opérateur sur le canal local. Le nonce prouve seulement la possession du jeton de transport de ce processus. Il ne certifie pas l'identité humaine. Une délégation absente ou changée refuse.

`source_admission_manifest_sha256` lie le manifeste Application exact proposé puis adopté. Contrat `P0-SOURCE-ADMISSION-MANIFEST-1.0` :

```
schema, status, application_inventory_sha256, catalogue_sha256,
source_scope_sha256, entries, exclusions
```

Candidat : `status=NON_ADOPTE`. Le futur dossier de décision adopte le SHA binaire exact de ce candidat, sans modifier sa qualification ni transformer UNKNOWN en officiel. L'injection normale ne l'admet que si la preuve `owner_decision_sha256` adopte explicitement ce SHA. Chaque `entry` fermée :

```
notion_ref, source_ref, object_kind, locator, checksum_or_version,
excerpt_sha256, provenance, source_status, available_authority,
authority_basis, admission_scope_sha256
```

Le scope est le SHA canonique de l'entry sans son propre hash ; `source_scope_sha256` est le SHA canonique des entries triées. La provenance et les statuts sont les objets natifs réellement retournés. Une exclusion ne peut être réintroduite sans successeur admis. L'absence d'autorité attestée produit `available_authority=UNKNOWN`, `authority_basis=NOT_ATTESTED_BY_APPLICATION`. Aucun ACTIVE/CURRENT, booléen ou rattachement de notion ne vaut admission. Le manifeste doit s'appuyer sur des hashes d'extraits complets effectivement calculés ; les seules captures partielles ne les remplacent pas.

Nouvelle query pure Application `ReadP0SourceAdmission` recevant le manifeste adopté, sa preuve d'adoption et des passages/résolutions relus par le lecteur Application existant. Aucun SQL, repository ou accès fichier direct dans cette query. Elle compare les identités, les octets d'extrait/hash, la provenance et l'autorité natives au manifeste, exige `RESOLVED_ADMITTED` et la portée exacte `CANONICAL_NOTION_ONLY` ou `EXACT_CONTEXT_ADMITTED`, et refuse troncature/oracle/pièce privée ou CONTENT_GAP. Elle retourne, pour chaque référence effectivement présente dans la préparation :

```
schema = P0-SOURCE-ADMISSION-RECEIPT-1.0
reference = {evidence_id,source_ref,locator,checksum_or_version,excerpt_sha256,provenance_label}
available_authority, provenance, source_status,
admission_manifest_sha256, admission_scope_sha256, owner_admission_sha256,
institutional_resolution_sha256, source_scope_status,
transmission_admission = OWNER_ADMITTED_LOCAL_CONTENT_ONLY
```

Le reçu lie transmission locale admise et autorité disponible séparément. UNKNOWN/NONE survivent à la preview et à la sauvegarde. Il n'atteste ni usage effectif des sources par le fournisseur, ni validation pédagogique. Un nouveau catalogue/runtime/manifest suspend P1.

## Frontière Application et companions HTTP

Nouveau `P0ConsentService`, avec les callbacks explicitement injectés :

```
prepared_reader(preparation_ref:str, preparation_sha256:str) -> Mapping
admission_reader(request:Mapping) -> Sequence[Mapping]  # receipts Application frais
permission.preview(request:Mapping, preparation_ref:str, preparation_sha256:str,
                   source_receipts:Sequence[Mapping]) -> Mapping
permission.accept(request:Mapping, consent:Mapping,
                  source_receipts:Sequence[Mapping]) -> None
generate(command:Mapping) -> dict  # service.execute("generate", exact existing fields)
```

`prepared_reader` lit uniquement `service.prepared` immuable et vérifie le SHA exact. Il ne recrée ni préparation, ni parent, ni résultat. `admission_reader` refait la lecture Application source et la résolution institutionnelle, compare le contexte/référence capturés et produit les reçus frais. Il ne restaure aucun grant. Tous changements imposent une nouvelle préparation/preview visible.

Registry companion `P0_CONSENT_ROUTE_SPECS` distinct des registries historiques :

| Route POST | Objet fermé |
|---|---|
| `/api/v2/p0/consent-preview` | `command_id,preparation_ref,preparation_sha256` |
| `/api/v2/p0/consent-generate` | `command_id,preparation_ref,preparation_sha256,preview_sha256,transfer_accepted,cost_bound_accepted` |

Même sécurité locale Host/Origin/nonce/intent existante et même enveloppe P0. Endpoint optionnel explicitement lié ; sinon refus `P0_PRODUCT_PERMISSION_REQUIRED`, zéro effet. Le navigateur n'envoie aucun grant, manifeste, chemin, URL, tarif, tokenizer, contenu, plafond ou clé. JSON dupliqué/non fini/inconnu refuse. Le consentement accepte la transmission des octets exacts montrés et le coût majoré exact, ainsi que la conservation de sécurité annoncée. Il est celui de l'opérateur local délégué et ne vaut ni recette ni review ni release.

Preview fermée `P0-PRODUCT-CONSENT-PREVIEW-1.0` :

```
schema, permission_sha256, preparation_ref, preparation_sha256, context_sha256,
reference_set_sha256, request_sha256, request_bytes, request_body_utf8,
cost_bound_usd, preflight, source_receipts, issued_at_utc, expires_at_utc
```

L'UI dérive le contexte et les extraits de `request_body_utf8`, affiche les reçus sources réels, destination/profil fixed G1, préflight complet, review NOT_RUN, source usage NOT_IN_OUTPUT_SCHEMA/RESERVE et le coût majoré. `preview_sha256=SHA(canonical(preview))` est affiché séparément dans l'enveloppe. Pas de réservation preview. Au plus 128 previews en mémoire ; expiration ≤15 min, pas de persistance donnant autorité. Un état perdu impose une nouvelle preview, pas un nouveau fournisseur. Les plafonds restants sont une projection informative du ledger privé, relus sous lock avant effet ; ils ne donnent aucune autorité supplémentaire.

## Composition normale et preuve F1 fraîche sous lock

Un broker spécifique `P0ProductGenerationAdapter` implémente le port génération existant par délégation à un G1 nouveau. Il possède preview/accept et les companions read-only controls/recovery. P0CreationService reste producteur de candidats et publication Application. `build_normal_p0_permission(...)` est une factory nouvelle recevant exclusivement des injections qualifiées. `build_p0_creation` et `build_browser_runtime` n'acceptent qu'une option normale explicite ; leur voie par défaut reste sans fournisseur.

Pendant `accept`, sous le verrou interprocessus F02 de P1, l'adaptateur recalcule le body canonique, les reçus Application et **le préflight réel** via tokenizer local/price actuellement liés. Il exige égalité intégrale `fresh_F1 == preview.preflight`, coût frais == coût montré, et identities courantes == P1. Ensuite seulement, contrôle des slots/coût cumulés, publication exclusive d'un slot lié à permissionSHA/previewSHA/command/G1SHA/bodySHA/F1SHA/coût frais, création en mémoire du G1 exact et marquage consentement consommé. Un coût diminué et une preview rehashée sont refusés par la comparaison fraîche. Le prototype pur teste l'égalité imposée ; le futur test runtime devra prouver le vrai recalcul sous le lock avant resolver/transport.

Namespace G1 = SHA canonique de `{permission_sha256,preview_sha256,command_id,nonce_sha256}` où l'entropie privée neuve est créée uniquement par l'infrastructure. Un second consentement du même preview est refusé même en deuxième processus/restart. Aucun remboursement automatique du slot, même si la publication RESERVED G1 ou la validation Application échoue. Aucun compteur mutable ou fourni par HTTP. `authorize(request)` ne trouve qu'un accept exact ; sans accept, false/zéro effet. `generate(request)` consomme son G1 puis exécute le port relu, jamais un ancien grant, un fallback ou un nouvel appel de reprise.

La reprise froide énumère les slots/dispatchs exacts confirmés sous P1 sans les autoriser. La factory injectée récupère les G1 historiques techniques associés, même expirés, et appelle les companions confirmés du port puis l'Application de publication. UNKNOWN/incomplet/preuve manquante après capture refuse et conserve tout. La reprise n'ouvre pas de slot/grant, ne résout aucune clé, ne recalcule pas pour autoriser et n'envoie rien. Plusieurs résultats confirmés sont repris séparément avec collision de version refusée.

## Tests attendus avant activation

Nominals six familles/quatre niveaux admissibles ; local sans injection zéro effet ; admission absente/source horsmanifest/UNKNOWN préservé ; délégation absente/profil changé ; vrais contrôles HTTP ; coût diminué rehashé/freshF1 changé ; slots concurrents interprocessus ; permission/source/body/context/runtime modifiés ; troncature/oracle ; publication impossible ; timeout ; restart sans redispatch ; controls RESERVE et warnings jusque dans Application save/read. Les doubles de transport/credential/tokenizer/prix sont déclarés et ne prouvent ni intelligence ni qualité pédagogique. Pas de nouvel appel réel ni de grant actif dans la qualification.
