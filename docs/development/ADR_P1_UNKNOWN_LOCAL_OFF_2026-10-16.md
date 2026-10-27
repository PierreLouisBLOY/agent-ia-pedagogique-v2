# P1 — successeur d’inspection locale OFF après UNKNOWN

Statut : contrat proposé, revue distincte préalable requise avant implémentation.

## 1. Objet et autorité

Une branche explicite d’inspection permet de conserver et compter une tentative
UNKNOWN précise. Elle ne poursuit pas une génération et ne produit aucune
autorité fournisseur. Les contrats V1/V2, `confirmed()`, les formats historiques,
les writers et le correctif de diagnostic existant restent inchangés.

Le successeur est un profil d’inspection OFF, sans permission P1 nouvelle, sans
grant, resolver, transport, réservation, récupération distante ou activation ON.
Une adoption d’orientation autorise son développement ; elle ne rattache pas des
objets runtime futurs. Toute utilisation réelle exige un plan et un book exacts
adoptés séparément. La qualification utilise des doubles et stores synthétiques.

## 2. Documents fermés et graphe sans cycle

Tous les documents techniques sont JSON canoniques, objets à champs exacts, sans
NaN ni doublon ; descripteur = `{path, sha256}` absolu, sans suivi de lien. Les
captures humaines peuvent être JSON non canonique mais leur SHA porte sur les
octets exacts. Aucun composant ne référence le book ni sa capture d’adoption.

* `P0-UNKNOWN-OFF-PLAN-1.0` : `schema`, `operation` =
  `INSPECT_UNKNOWN_LOCAL_OFF`, `baseline_commit`, `source_tree` (Git 40 hex),
  `source_manifest`, `package`, `historical_profile_envelope`,
  `historical_adoption_control`, `origin_tip_permission_sha256`, `anchor`,
  `manifest`, `operator_delegation`, `target_runtime`,
  `saved_root_native_identity`, `receipt_root_native_identity`, `issued_at_utc`,
  `expires_at_utc`, `continuity_enabled` = false, `ledger_writes_allowed` = false,
  `provider_calls_allowed` = 0 (entier exact).
* `P0-UNKNOWN-OFF-ANCHOR-1.0` : `schema`, `root_permission_sha256`,
  `campaign_namespace_sha256`, `root_lock_sha256`, `original_anchor`,
  `prior_anchor`, `orientation_adoption`, `prior_design_review`, `owner_diagnostic`.
  Les deux ancres historiques sont celles du contrat V2 et ne sont pas remplacées.
  `orientation_adoption` et `prior_design_review` sont des preuves techniques
  opaques relues et hashées sur leurs octets exacts. Leur autorité ne vient pas
  de leurs propres champs : elles sont liées à l’anchor et aux composants du
  book adopté, puis à la SHA humaine attendue injectée séparément. Leur contenu
  n’est ni une permission P1 ni une décision autorisant un effet.
* `P0-UNKNOWN-OFF-MANIFEST-1.0` : `schema`, `anchor`, `historical_manifest`,
  `unknown_disposition`, `expected_slots`, `expected_reserved_budget_usd`.
  `expected_slots` est une liste de trois objets fermés `{namespace_sha256,
  slot_sha256, classification}` : exactement un `CONSUMED`, un
  `KNOWN_REJECTED`, un `UNKNOWN`. Aucune omission, permutation d’identité ou
  quatrième slot n’est admise par ce contrat borné.
* `P0-UNKNOWN-OFF-DISPOSITION-1.0` : `schema`, `disposition` =
  `UNKNOWN_PRESERVE_COUNT_NO_EFFECT`, `target_attempt`, `slot_sha256`,
  `file_sha256s`, `owner_diagnostic`, `preserve_reservation` = true,
  `no_grant_reuse` = true, `no_runtime_mutation` = true.
  `target_attempt` contient exactement `permission_sha256`, `namespace_sha256`,
  `request_sha256`, `request_bytes`, `reserved_usd`, `grant_sha256`,
  `preview_sha256`, `command_id`, `preflight_sha256`.
  `file_sha256s` contient exactement DISPATCH, RESERVED, PROVIDER_ATTEMPTED,
  UNKNOWN. Ces empreintes doivent être réellement observées ; on ne les déduit
  pas d’un relevé incomplet. Le diagnostic humain conserve son identité brute.
* `P0-UNKNOWN-OFF-BOOK-1.0` : `schema`, `operation` = `LOCAL_OFF_ONLY`,
  `components` : SHA exacts `plan_sha256`, `anchor_sha256`, `manifest_sha256`,
  `disposition_sha256`, `source_manifest_sha256`, `package_sha256`.
* `P0-UNKNOWN-OFF-ADOPTION-1.0` (contrôle externe de composition) : `schema`,
  `book`, `owner_evidence`. La capture `P0-UNKNOWN-OFF-OWNER-ADOPTION-1.0`
  contient seulement `schema`, `operation` = `LOCAL_OFF_ONLY`, `book_sha256`,
  `components`. Sa SHA brute attendue est une entrée **distincte et obligatoire
  de la composition de confiance**, jamais reçue d’HTTP ni prise dans la capture.
  Aucune signature cryptographique humaine n’est prétendue. Ni le book ni ses
  composants ne peuvent autoriser ON, un appel ou un nouveau slot.

## 3. Origine, code et contexte exacts

La composition relit le profil V4 historique et son contrôle d’adoption V2,
vérifie les deux enveloppes OFF/ON historiques, leurs composants communs,
ascendants, décisions, tarifs, sources admises, ancres et disposition de rejet.
Elle réutilise `bind_chain_v2`, sans instancier la composition de génération et
sans confronter le vieux package au code nouveau. L’origine reste historique.

Le nouveau code et son package sont vérifiés séparément avec
`verify_source_package(plan, application_root=...)`. Le plan lie leur commit et
arbre, le profil d’origine exact, les mêmes runtime, délégation SID/profil,
stores et identités natives. La fenêtre du plan est incluse dans celle de la
racine ; contrôle frais avant et après chaque inspection, refus si expirée.
`Read15RuntimeTarget.validate()` conserve ses contrôles existants sans SQL libre.
Le contrôle externe exact est relu à chaque inspection. Ni plan ni ancien profil
ne deviennent une permission de génération.

## 4. Lecture sous le LOCK original

Un nouveau reader compose `P0ContinuityProductLedger` uniquement pour son
`locked()` existant (OPEN_EXISTING, lecture, partage nul, identité native et
octets du LOCK racine) et ses contrôles de témoins/orphelins. Il n’hérite pas du
writer et n’expose ni `reserve`, `_publish`, `own_transition` ni récupération.
Le LOCK absent, occupé ou changé est un refus, jamais une création ou réparation.

Sous ce LOCK, inventaire exhaustif des slots de la campagne et des namespaces
normaux, validation `validate_slot` de chaque origine/grant historique :

1. CONSUMED : `confirmed()` et `validate_events` inchangés, capture/préflight liés.
2. KNOWN_REJECTED : `validate_captured_rejection`, comparaison intégrale de
   l’observation avec l’évidence déjà adoptée, aucun reparse du contenu.
3. UNKNOWN : branche explicite, jamais `confirmed()`. Ensemble de fichiers exact
   DISPATCH/RESERVED/PROVIDER_ATTEMPTED/UNKNOWN, octets canoniques liés aux SHA
   adoptés, slot/grant/preview/commande/requête/préflight et origine exacts.
   Capture DISPATCH fermée, corps lié au SHA et à la taille, grant/dispatch/
   préflight liés ; ce corps n’est ni diffusé ni modifié. Événements fermés
   existants : ordre temporel depuis issuance, une tentative au plus (0 RESERVED,
   1 ATTEMPTED/UNKNOWN), statut/usage/artifact nuls, coût non établi. Aucun
   RESULT/capture de réponse/PARSED/CONSUMED/rejet/événement supplémentaire.

Le contrat n’invente pas une réponse ni une cause. La limite financière historique
est validée par le grant et le slot ; la réservation reste entièrement comptée.
Le relevé propriétaire doit lier origine, campagne, LOCK, cible, événements et
flags UNKNOWN, sans prétendre coût facturé ou succès. Les champs absents restent
un refus. Aucun témoin historique ou ancien grant n’est réécrit.

Le cumul Decimal utilise les trois réservations complètes et les plafonds racine.
La somme ne peut être diminuée, UNKNOWN ne libère jamais de slot. Revalidation de
tous les octets lus et de l’inventaire avant retour, sous le même LOCK : changement
concurrent, doublon, orphelin, lien, quatrième slot, événement ou origine inconnue,
total divergent, overspend ou identité modifiée => refus.

## 5. Frontière Application et projection

Le reader ne fournit que `inspect(inspection_ref,
expected_plan_or_profile_sha256)`, lié au plan exact. Il entre dans
`InspectP1Campaign` et `P1CampaignInspectionInbound` existants. La vue reçoit une
branche de schéma explicite `P0-PRODUCT-UNKNOWN-OFF-OBSERVATION-1.0`, projetée en
`P1-CAMPAIGN-UNKNOWN-OFF-METADATA-1.0` :

`schema`, `state` = `OFF_RESERVATIONS_OBSERVED_NOT_EFFECT_AUTHORIZED`,
`timestamp_utc`, `inspection_plan_sha256`, `campaign_namespace_sha256`,
`root_permission_sha256`, `origin_tip_permission_sha256`, `root_lock_sha256`,
`disposition_sha256`, `slots_reserved` = 3, `consumed_count` = 1,
`known_rejected_count` = 1, `unknown_count` = 1, `reserved_budget_usd`,
`financial_basis` = `RESERVATIONS_NOT_BILLED_COST`, `actual_billed_cost_status` =
`NOT_ESTABLISHED`, `live_enabled` = false, `effect_permitted` = false,
`provider_calls` = 0, `ledger_mutations` = 0, `course_qualification` =
`NOT_COMPLETED`.

Pas de capacité restante présentée comme disponible, de chemin, passage privé,
corps, exception brute, credential ou en-tête. Les erreurs du port utilisent les
catégories Application existantes ; aucun nouveau système de diagnostic. Le
reader est accessible à une composition explicite OFF, jamais autochargée par le
lanceur utilisateur, jamais ajoutée comme bypass à une route d’envoi.

## 6. Delta prévu et qualification

Nouveaux modules : `p0_product_unknown_off_contract.py`,
`p0_product_unknown_off_reader.py`, factory `p0_unknown_off.py`, validateur DTO
`p1_unknown_off_inspection.py`. Modification bornée de
`p1_campaign_inspection.py` pour aiguiller le nouveau schéma seulement.
Tests unitaires du contrat et de la projection ; intégration Windows native de
la factory et de l’inbound sur trois slots synthétiques. Aucun autre changement
de writer, profil V4, parseur, diagnostic ou contrat normal.

Matrice obligatoire : nominal OFF, préservation octets/noms/identités historiques,
conservation UNKNOWN et cumul ; cible/ancêtre/LOCK/store/source/package/adoption
faux ou changés ; événements manquants/en plus ; UNKNOWN supplémentaire ; slot
omis/dupliqué ; budget diminué/dépassé ; expiry ; concurrence ; erreur reader ;
refus des effets/grants/ON et absence de seconde tentative ; projection sans
données privées. Doubles transport et resolver explicitement refusants durant
l’inspection, writers instrumentés refusants. Regressions V1/V2 et Application
pertinentes, lint/typecheck applicables, contrôles des gardes de livraison.

La recette enseignante et la qualification COURSE live ne sont pas engagées.
Une suite OFF PASS ne change pas UNKNOWN ni les permissions d’un futur effet.
