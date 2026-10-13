# ADR — Continuité versionnée de la permission produit P1

Date : 13 octobre 2026. Lot : LU-PRODUIT-01. Statut : proposition source préalable à la revue distincte. L'adoption de l'implémentation locale, la revue, le rattachement du package/profil et l'autorisation d'effet sont des décisions séparées, conservées dans le dossier privé du lot.

## Objet et invariants

Une permission courante liée à un nouveau code/package/schéma ne peut remplacer silencieusement la permission qui a créé le LOCK et les anciens slots. Ajouter un successeur explicite permet de vérifier chaque slot selon son origine, sous un verrou et un budget communs, sans rejouer ni transférer ses grants.

Le mécanisme est désactivé par défaut. Les profils/décisions 1/2, formats P1/G1, scanners et politiques financières partagés restent dans leur portée. La permission de campagne, ses ancêtres, le LOCK, les slots, réservations, grants et reçus restent conservés. Aucun namespace de remplacement, reset, remboursement présumé, réconciliation automatique, migration ou effet sur une base n'est introduit.

Les contrats sont purs, sans SDK, HTTP, ORM ou accès filesystem. Les lectures protégées, identités natives et handles Windows restent dans les adaptateurs. L'agent accède au statut exclusivement par l'inbound Application existant.

## Graphe exact des preuves

Le graphe est acyclique :

1. Ancêtres exacts et preuves historiques conservés.
2. Ancre privée locale de campagne, contenant les identités et réservations minimales attestées.
3. Manifeste fermé des seuls ancêtres, racine → parent du futur tip.
4. Profile3 lié au manifeste et à l'ancre.
5. Politique P1 courante excluant uniquement son propre owner_decision_sha256.
6. Decision3 liée au profil, à cette politique, au manifeste, à l'ancre et au parent.
7. Permission complète courante et enveloppe exactes.

Le manifeste ne contient jamais le SHA du tip/profil/décision courants. Les ancêtres sont uniques, ordonnés, sans trou, cycle, branche, plage Git, wildcard ou sélection du plus récent. Une permission non présente dans cette chaîne est refusée. Le plafond de 14 ancêtres borne ce contrat ; il ne crée aucun slot ou appel.

L'ancre fermée P0-PRODUCT-CONTINUITY-ANCHOR-1.0 contient schema, implementation_decision et conditions (descriptors), root_permission_sha256, campaign_namespace_sha256 et required_historical_reservations (liste non vide). Aucun SHA de campagne, namespace d'opération, requête, réserve consommée, octet de ledger ou chemin métier réel n'est codé dans Git. Seule la factory de confiance lit ces pièces privées exactes et leurs preuves, liées aux descriptors/profil/manifeste/décision ADOPTED. Leur omission, changement ou incohérence impose STOP. Ni HTTP ni une commande agent n'accepte cette ancre ou un grant. L'ancre est une preuve historique et de configuration, jamais un droit live.

Le manifeste P0-PRODUCT-CONTINUITY-MANIFEST-1.0 est fermé : schema, implementation_decision_sha256, conditions_sha256, root_permission_sha256, root_lock_sha256, parent_permission_sha256, campaign_namespace_sha256, campaign_window, campaign_limits, common_identities, ancestors, historical_reservations, continuity_anchor. Chaque ancestor est fermé : permission_sha256, parent_permission_sha256 (null pour la racine seulement), permission, profile_envelope, owner_decision (descriptors pour les trois derniers). La factory vérifie les bytes protégés, leurs SHA, contrats et liens ; la seule présence du fichier n'atteste pas son adoption.

## Profil et admission source

Profile3 ajoute à Profile2 exactement continuity_manifest, continuity_anchor, source_admission_owner_decision (descriptors) et continuity_enabled (bool explicite). Decision3 ajoute à Decision2 exactement continuity_manifest_sha256, continuity_anchor_sha256, parent_permission_sha256 et source_admission_owner_decision_sha256. Le statut utilisable est ADOPTED ; une proposition ou la décision d'implémenter ne vaut pas adoption d'une nouvelle permission live. continuity_enabled=false n'installe pas la génération et ne résout aucune clé.

Le témoin d'admission documentaire est séparé de la nouvelle décision live. Dans cette branche minimale, il doit être un ancêtre exact avec les mêmes manifests de source/admission et de contexte local. La validation des reçus Profile3 attend ce SHA explicitement lié ; les branches 1/2 conservent leur égalité historique avec leur propre décision. Aucune nouvelle source/contexte transmissible ou autorité institutionnelle n'est créée. Les choix locaux M02–M04 ne deviennent pas transférables par cette continuité. De nouvelles admissions peuvent nécessiter un contrat/une décision distincts même après consentement V2 ; aucune autorité supplémentaire n'est ajoutée implicitement.

## Identités conservées et identité courante

Conserver namespace, receipt_root et saved_root (chemins et identités natives), runtime complet (path/data_root/sha256), opérateur SID/profil, descriptors opérateur/tokenizer/tarif/preuve du tarif et catalogue institutionnel. Les SHA tokenizer/tarif/catalogue du profil correspondent aux communs de la permission.

Seuls baseline_commit, source_tree_sha256, package_sha256, profile_sha256, output_schema_sha256 et owner_decision_sha256 peuvent évoluer après adoption exacte ; issued_at peut être plus tardive. Scopes family/level ne peuvent que rester dans les ensembles racines. Chaque nouveau corps, schéma, borne et consentement est exact et frais ; ils ne sont pas hérités d'une ancienne requête.

La fenêtre et les plafonds sont ceux de la permission racine : aucune prolongation ni nouveau quota. Les restrictions P1 restent simultanées : au plus 14 CREATE, 0,14 USD par appel et 1,96 USD cumulés pour cette campagne ; COUNT/REVIEW/MODIFY 0, retry 0, fallback NONE, parallélisme 1, modèle et paramètres exacts déjà admis. Un grant ancien est vérifié à sa date d'origine et doit aussi respecter permission.issued ≤ grant.issued < grant.expires ≤ permission.expires. L'effet nouveau emploie le tip exact et l'heure courante.

## LOCK et comptabilité

Le successeur exige le LOCK original : absence = STOP, jamais création/remplacement. Ses bytes restent le binding à la permission racine. La comparaison se fait au travers du handle exclusif conservé après acquisition, avec identité native avant/après, racine et absence de reparse/link. Le même LOCK sérialise metadata, preview, accept et le transport/consignation de generate, y compris entre anciennes et nouvelles versions. Contention = refus, sans retry ni attente cachée. Aucun ACL/privilège/réglage Windows n'est changé.

Tous les slots du préfixe commun sont validés avec le format historique fermé, leur nom, permission d'origine, G1, hashes et réserve positive. Toutes les réservations de la chaîne sont comptées. NOT_ESTABLISHED ne signifie pas zéro ; la somme est une somme de réserves, sans prétendre donner un coût facturé. Aucun ancien relevé daté ne devient un solde actuel.

Chaque historical_reservations est fermé : permission_sha256, namespace_sha256, request_sha256, reserved_usd, metadata_evidence (descriptor). Les minima attestés de l'ancre doivent exister et correspondre exactement. Les témoins des ancêtres ne peuvent être retirés. Les slots supplémentaires présents sont tous vérifiés et comptés.

L'adaptateur identifie les namespaces de reçus normaux. Un DISPATCH dont le grant correspond exactement à une origine de cette campagne, mais qui n'a pas de slot P1, est un orphelin : STOP. Capture manquante, format ambigu ou campagne non identifiée = STOP sans imputer arbitrairement le coût d'une autre campagne. Un dossier n'est pas une preuve d'attribution. Cela ne promet pas une détection universelle d'une suppression totale de toutes les preuves hors Application.

## Lifecycle, transition propre et récupération

Requérir les formes réellement publiées RESERVED, DISPATCH, PROVIDER_ATTEMPTED, RESPONSE_CAPTURED, RESULT, PARSED et CONSUMED. Réutiliser la validation normale des captures/hashes/usage et vérifier aussi PARSED/CONSUMED, coûts, identités et timestamps ordonnés dans le grant. UNKNOWN, PARSING_REJECTED, manque, ambiguïté, résultat non completed ou divergence = STOP, sans restitution. Aucun résultat brut n'est exposé par le statut.

La seule transition partielle recevable est le slot fraîchement créé par accept dans la même instance pending vivante. Sous le LOCK : permission tip, command_id, grant, namespace, dispatch, corps et préflight sont identiques, le pending est vivant, aucune trace P0 n'existe encore. Cette capacité n'est pas reconstruite depuis un fichier et ne survit pas au redémarrage. Tout autre partial bloque. Le garde normal de réservation continue de refuser un replay.

La récupération courante construit un adaptateur uniquement pour un grant du tip courant. Un grant ancien demandé sous le successeur est explicitement refusé, même en recovery. Ses lecteurs/preuves d'origine restent conservés ; aucune parse/publication/autorisation implicite sous le nouveau code.

## Statut inbound, fichiers et retour arrière

Un callback facultatif du P0CreationEndpoint existant reçoit le relevé par composition → broker → ledger adapter. Pas de route/port/framework supplémentaire. Sans callback, metadata historique est conservée. Le relevé fermé indique état, date, identités de campagne/tip, slots, réserves et disponibilités, financial_basis=RESERVATIONS_NOT_BILLED_COST et live_enabled. Aucun texte fournisseur, clé, chemin, grant ou permission brute. CURRENT_VALIDATED suppose vérification complète sous LOCK. STOP ne fournit aucune disponibilité inventée ; expiration/OFF ferme l'effet.

Fichiers visés :

- p0_product_continuity_contract.py : contrats/chaîne/snapshots purs.
- p0_product_continuity_ledger.py : adaptateur FS/native versionné.
- p0_product.py : branche explicitement injectée, LOCK de preview/statut, transition propre, recovery current-only.
- p0_product_policy.py : témoin source Profile3 fermé ; P1/G1 et branches 1/2 conservées.
- factories/p0_normal_profile_contract.py et p0_normal_profile.py : binder3, chargement privé revalidé, default OFF, callback.
- inbound/api/p0_creation.py : seul callback facultatif de statut.
- Tests synthétiques ciblés et cet ADR ; aucun changement des guards partagés, pins/registry, frontend, dépendances ou bases.

Retour arrière : revenir explicitement à OFF/au profil d'origine choisi ne réécrit/supprime aucune preuve ou consommation. Une publication interrompue reste à réconcilier ; aucun rollback automatique de slot ou base.

## Vérification nécessaire et limites

Tests par impact : DAG exact et mutations ; ancre absente/vide/changée ; identités communs et fenêtres ; permissions d'origine et reserves communes ; témoins omis/orphelins ; lifecycle manquant/UNKNOWN/rejected ; pending propre/forgé/stale/redémarré ; concurrence crossversions ; ancien grant en recovery ; factory/enveloppes/source-owner ; callback sans donnée privée ; régressions P1/normal/profil 1/2. Ruff/mypy applicables doivent réellement passer.

La pré-revue utilise un prototype mémoire séparé. La qualification source exige ensuite un positif Windows synthétique avec les slots/événements réellement publiés par le protocole P0Product/P0Normal existant, transport et résolution doubles, factory/enveloppes/metadata, mêmes handles et fichiers dans un dossier neuf. Permissions/grants fixture sont datés à l'heure réelle ; event() n'est pas remplacé. Aucune constante réelle, option de bypass ou assertion affaiblie. Les preuves publiques sont entièrement synthétiques ; les preuves privées de campagne restent hors Git.

Cette qualification technique n'établit ni données réelles, coût facturé, nouvelle adoption live ou autorité pédagogique. La lecture réelle du cumul par Application, le rattachement exact du nouveau package/profil et les consentements opérationnels restent à faire avant tout envoi. Recette enseignante uniquement dernière étape. Aucun merge, release, déploiement, appel fournisseur/COUNT ou activation live implicite.
