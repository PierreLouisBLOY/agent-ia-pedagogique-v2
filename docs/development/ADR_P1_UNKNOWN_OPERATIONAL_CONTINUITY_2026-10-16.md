# P1 — continuité opérationnelle bornée après UNKNOWN

Statut : contrat exact proposé à revue distincte préalable ; aucune implémentation
avant avis favorable. Même LU-PRODUIT-01. Autorisation de développement local
hors fournisseur enregistrée séparément, sans activation réelle.

## 1. Objet et non-régression

Une composition opérationnelle explicite conserve trois historiques exacts
(CONSUMED, KNOWN_REJECTED, UNKNOWN) et peut préparer une seule nouvelle création
COURSE/CHAPTER, dans les contextes déjà admis, après une décision d'opération
distincte. Ce développement ne matérialise aucun binding/grant/slot réel.
L'inspection OFF et ses reçus sont acquis et ne sont pas rejoués.

`P0NormalReceipt.confirmed`, validate_events, les contrats P1/G1, profils V1–V4,
leur binders, le diagnostic et le lecteur OFF restent sémantiquement inchangés.
UNKNOWN historique n'est jamais confirmé, reclassé, récupéré ou remboursé.

## 2. Documents fermés, chemins et adoption

Les nouveaux documents H/I/O/B et contrôles sont des objets JSON canoniques,
sans doublon ou non-fini. `descriptor` signifie le contrat existant `{path,sha256}`
absolu sans suivi de lien. Les captures humaines brutes et les témoins techniques
historiques, notamment off_result, peuvent être non canoniques : décodage strict
sans doublon/non-fini et validation fermée de leur schéma, SHA sur leurs octets
bruts inchangés. Aucune réécriture n'est autorisée pour les rendre canoniques.
Les entiers rejettent bool ; SHA=64 hex minuscules,
Git=40 hex ; montants Decimal positifs ou nuls, jamais floats.

### 2.1 Capsule H — historique gelé

Schéma `P1-UNKNOWN-CONTINUITY-HISTORY-1.0`, champs exacts :
`schema`, `off_plan`, `off_book`, `off_adoption`, `off_expected_owner_sha256`,
`off_result`, `frozen_inventory`, `policy`.

Les quatre chemins sont descripteurs. off_expected_owner_sha256 est un SHA,
policy vaut `PRESERVE_COUNT_NO_REPLAY`. frozen_inventory est une liste de 1 à
1024 objets fermés `{name,sha256,device,inode}` : noms de fichiers JSON simples
et uniques, pas de séparateur/point-point ; device/inode entiers natifs non nuls.
Les 20 fichiers de la campagne actuelle ne sont pas supposés par leur nombre :
le classement exhaustif doit prouver les trois slots et leurs événements exacts.
Les témoins d'autres campagnes ne sont jamais adoptés comme nouvelle autorité.

Le book/adoption OFF sont vérifiés avec validate_adoption existant et SHA attendue
de H ; le plan et ses six composants restent exactement adoptés. Le résultat
est le rapport technique acquis `LU-P1-ACTUAL-APPLICATION-UNKNOWN-OFF-INSPECTION-1.0`,
state=APPLICATION_OFF_INSPECTION_SUCCEEDED_NO_EFFECT_AUTHORITY, observation fermée
P1-CAMPAIGN-UNKNOWN-OFF-METADATA-1.0, trois slots/1+1+1, mêmes plan/campagne/LOCK,
effect_permitted=false/live_enabled=false, provider_calls/sql_queries et mutations=0.
Il est une preuve historique, pas un préflight frais ni une permission d'effet.

La chaîne historique V2 est rechargée par les composants déjà livrés ; les
descripteurs et anciennes adoptions sont vérifiés, sans invoquer inspect().
Ne jamais comparer le package historique à la source courante : code/package
courants sont vérifiés séparément. Les octets et identités H sont revalidés
dans les préflights normaux sous le LOCK original, avant et après les phases.

### 2.2 Intention I — une préparation Application distincte

Schéma `P1-UNKNOWN-CONTINUITY-INTENT-1.0`, champs exacts : `schema`,
`preparation_sha256`, `request_sha256`, `request_bytes`, `context_sha256`,
`reference_set_sha256`, `old_intent_sha256`, `new_intent_sha256`,
`old_objectives_sha256`, `new_objectives_sha256`, `cost_bound_usd`.

request_bytes est entier 1..249999 ; coûts <=0.14. Les autres suffixes SHA sont
des SHA. Ancienne et nouvelle empreintes d'intention/objectifs doivent différer.
Les valeurs sont recomputées sur les deux requêtes réellement liées, jamais
acceptées comme un drapeau envoyé par HTTP. La préparation vient du chemin
Application normal. Le corps nouveau est reconstruit par build_p0_content_request.

Projection métier neutre fournisseur : resource_type, level, discipline,
institutional (sélection), topics, objectives, difficulty, références exactes.
P0Context valide sa structure ; pas de titre, date, progression locale ou ID
technique comme preuve de nouveauté. Normalisation NFKC + casefold + espaces
contractés des chaînes ; mappings triés, listes d'objectifs/notions/références
traitées comme ensembles canoniques. Un corps identique à UNKNOWN ou des
objectifs/projection normalisés égaux est un refus. La nouvelle préparation et
ses références restent validées par les contrats normaux et admissions exactes.
Une paraphrase peut changer la projection sans changer le besoin : le logiciel
ne certifie pas la différence sémantique. La décision humaine exacte ci-dessous
doit confirmer un besoin pédagogique indépendant ; ambiguïté = refus humain.

### 2.3 Plan O et book B — pas de grant anticipé

Schéma `P1-UNKNOWN-CONTINUITY-OPERATION-1.0`, champs exacts : `schema`, `history`,
`intent`, `profile_envelopes`, `profile_adoption`, `issued_at_utc`, `expires_at_utc`,
`max_new_operations`, `operation`, `retry`, `fallback`, `parallelism`.

history et intent sont descripteurs ; profile_envelopes est fermé `{off,on}`,
descripteurs d'enveloppes V4 ; profile_adoption est le contrôle V4 exact existant.
operation=ONE_DISTINCT_CREATE_AFTER_UNKNOWN, max_new_operations=1, retry=0,
fallback=NONE, parallelism=1. Fenêtre UTC incluse dans la racine P1, sans extension.
Les profils restent fermés V4, pas de champ supplémentaire toléré. Leurs sources,
store, opérateur, tarifs/tokenizer et admissions passent leurs contrôles normaux.

Book `P1-UNKNOWN-CONTINUITY-BOOK-1.0`, champs `{schema,operation,components}` ;
operation=ONE_DISTINCT_CREATE_AFTER_UNKNOWN ; components fermés :
`plan_sha256`, `history_sha256`, `intent_sha256`, `source_manifest_sha256`,
`package_sha256`, `profile_off_sha256`, `profile_on_sha256`.

Contrôle `P1-UNKNOWN-CONTINUITY-ADOPTION-1.0`, champs `{schema,book,owner_evidence}`.
Projection propriétaire `P1-UNKNOWN-CONTINUITY-OWNER-1.0`, champs : `schema`,
`operation`, `book_sha256`, `components`, `new_need_confirmed`,
`unknown_risk_acknowledged`, `not_a_retry`. Ces trois booléens valent true et
restent une décision humaine, pas une déduction de la SHA. La réponse brute est
conservée séparément avec provenance directe ; aucune signature prétendue.
expected_owner_sha256 est une entrée distincte de composition de confiance,
jamais HTTP ni lue dans la capture comme source d'autorité. Tout est revalidé.
H/I/O ne référencent pas B ni son adoption ; O ne référence pas de futur G1.

## 3. Chaînes V4 et composition opérationnelle

Le binder V2 historique est inchangé. Le filtre de la factory V4 actuelle qui
n'admet comme ancêtre V4 que son propre OFF n'autorise pas un descendant du tip
UNKNOWN. Il ne sera pas affaibli : le successeur dispose d'un binder explicite
pour sa paire courante et le préfixe historique validé.

Il réutilise bind_chain_v2 (contrat pur), bind_profile4, _proof/_ancestors et les
contrôles d'adoption existants : préfixe exact des origines historiques gelées ;
OFF courant a pour parent le tip historique ; ON ajoute seulement son OFF.
Tout ancêtre supplémentaire ou remplacé refuse. Les manifests V2 gardent leurs
champs, racine, limites, ancres et rejet exact. La factory nouvelle prouve la
correspondance de la paire externe au mode actuel et aux deux SHA du book.
L'autorité opérationnelle vient du contrôle supplémentaire, pas d'un nouveau SHA.

P0UnknownContinuationComposition est explicite, jamais autoloadée. Elle réutilise
les phases natives de lecture et le chemin de consentement Application existant.
Deux petits hooks de construction par défaut dans la factory/broker V4 permettent
d'injecter les sous-classes ; leurs comportements par défaut restent identiques.
Pas de création puis remplacement d'un broker vivant, monkeypatch ou second
pipeline fournisseur. Les nouveaux descripteurs H/I/O/B/adoption entrent dans le
read-set protégé ; toute modification ou fin asynchrone non confirmée empoisonne
la phase et interdit l'effet. OFF débranche la génération, aucun resolver réel
n'est construit pendant la qualification synthétique hors fournisseur.

La comparaison métier est un contrat Application neutre sous work_orchestration ;
le nouveau ledger reste adaptateur FS. Les requêtes agents utilisent les inbounds
existants ; aucun accès direct agent aux stores, SQL ou secrets. Pas de nouveau
framework, fournisseur, dépendance ni API/commande d'inspection.

## 4. Ledger borné et transitions

P0UnknownContinuationLedger dérive du ledger V4 seulement pour le LOCK, les
writers create-only et OwnPending ; slots() est remplacé explicitement.
Il valide trois historiques via leurs origines : confirmé normal, rejet capturé,
UNKNOWN exact. validate_unknown est appelé sur la chaîne historique au tip
UNKNOWN (pas sur la nouvelle permission). UNKNOWN n'appelle jamais confirmed().
Fichiers supplémentaires, omis, liens, octets ou identités natives différents,
LOCK absent/occupé/changé, orphelin ou origine inconnue = STOP.

Inventaire autorisé : les trois slots figés, plus zéro ou un slot créé par la
permission courante et la préparation I. reserve() refuse un deuxième ajout
quel que soit son nouveau preview/command_id et garde l'ancien slot. Le namespace
G1 est dérivé normalement, dans la campagne et le cumul racine existants.
Dans GENERATE, seul OwnPending lié à ce broker vivant autorise le slot en cours.
Les étapes précédentes sont revérifiées avant résolution du credential et appel.
Les réutilisations de preuve native dans Normal restent préprovider : slot sans
événement puis RESERVED+DISPATCH, identités liées à OwnPending. Après le retour
Normal, slots() vérifie le terminal complet sous le même LOCK ; aucun
require_proof supplémentaire ne sera inséré après provider pour tolérer des
stades non prévus. Pas d'élargissement des phases ou prédicats historiques.

Transitions : BOUND_OFF → (activation future distincte) PREVIEWED → consentements
frais → RESERVED → PROVIDER_ATTEMPTED → RESPONSE_CAPTURED → PARSED → CONSUMED.
PREVIEW ne réserve rien. ACCEPT revalide les origines, intention, fenêtre, coût et
cumul sous LOCK avant le seul G1/slot nouveau. GENERATE revalide les mêmes faits
et capacité vivante ; au plus une tentative. Tous les événements restent ceux
du protocole normal. Refus/crash/nouvel UNKNOWN/rejet/partiel après réservation :
slot entier conservé, profil bloqué, pas de retry/fallback/refund/recovery.
Un redémarrage ne reconstitue aucune capacité depuis les fichiers.

Pour un nouveau slot terminé, confirmed()/validate_events normaux sont requis.
Après succès la permission d'ajout reste épuisée ; elle ne permet pas un 5e slot.
Les compteurs sont classifiés réellement (jamais count-1). La projection de budget
versionnée utilise le view/inbound existant si nécessaire ; pas de nouvel
inspecteur. Un résultat de génération ne suffit pas à qualifier sauvegarde,
réouverture/export ni à signer une recette pédagogique.

## 5. Finances, pannes et absence de fuite

reservation_totals/check_budget en Decimal gardent les trois réservations,
y compris l'UNKNOWN entier : max_calls racine14, <=0.14USD/appel, <=1.96USD au
cumul, fenêtre racine inchangée. max_new_operations=1 est une restriction.
L'observation acquise n'est pas un solde courant ; les préflights normaux lisent
le total frais. Le coût facturé reste NOT_ESTABLISHED. Borne requise non démontrée,
tarif/source/adoption divergents ou expiry interdisent l'effet, même avec accord
de risque. Aucun refund implicite, quota/namespace alternatif ou transfert G1.

Réutiliser le diagnostic efe4c8a et les catégories Application existantes :
étape et code disponibles seulement, jamais exception brute, clé, auth header,
corps ou passage privé. Le diagnostic peut échouer sans provoquer un 2e envoi.
Les crashs après réserve, réponse ou enregistrement gardent l'état réellement
écrit et son incertitude ; aucune réparation/suppression/checkpoint de base.

## 6. Qualification et livraison

Tests synthétiques déclarés : contrats/adoption et entrées fermées ; ancien
corps/intentions/objectifs identiques ou seuls IDs/titre/date/espaces modifiés ;
différence admise liée aux sources exactes ; mutation/replacement natif/omission
historique ; cinq slots/doublons/grant transféré ; limites Decimal et un seul
ajout ; concurrence/LOCK/expiry/read-set ; OFF refuse tout effet ; nominal du
chemin Application réel avec double jusqu'aux exports ; transport, traitement
après réponse, résultat et diagnostic en panne sans fuite ni second envoi.

Ruff/mypy/compilation et régressions par impact, gardes et hygiène du delta avant
livraison ; preuves inchangées réutilisées sans nouveau global. Les modules
historiques/diagnostiques/OFF restent byte-identiques sauf hooks explicitement
relus et nouveaux propriétaires de garde. Une revue de livraison distincte
contrôle le delta et ses preuves. Tout FAIL/ERROR/SKIP est conservé dans sa portée.

Tout futur effet exige adoption exacte des objets opérationnels et de leur
activation, préflights frais et deux consentements V2. Aucun de ces effets
n'est autorisé par la présente phase de développement. Recette enseignante
exclusivement dernière/non engagée. Aucun merge, release ou déploiement.
