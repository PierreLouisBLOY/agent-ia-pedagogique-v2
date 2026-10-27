# ADR ciblé — diagnostic privé d'échec du CREATE normal
Date : 15 octobre 2026. LU-PRODUIT-01, même lot.
Statut : PROPOSITION, revue distincte requise avant implémentation.
Baseline source : 500d39c094e4d5309d029ccc162961bc11a3b99b.

## Mandat et fait historique
La continuation humaine autorise seulement le correctif hors fournisseur et ses doubles.
Une opération a atteint UNKNOWN sans RESULT/RESPONSE_CAPTURED. Ses reçus et données
runtime restent dans le dossier privé hors Git. La cause n'est pas reconstruite.
Les imports préflight sont attestés dans leur processus distinct, pas une capture mémoire du serveur.
Aucun reçu réel/LOCK/slot/store/runtime n'est ouvert ou modifié par le développement.

## Décision proposée
1. Conserver les neuf noms/flags et les schémas des reçus lifecycle V1, leur ordre et le refus UNKNOWN.
   Aucun champ ajouté aux anciens événements, aucun événement historique réécrit.
2. Ajouter uniquement un diagnostic privé immuable de cette opération, sur la même racine
   privée injectée et sous les protections existantes, nommé p0-diagnostic.<namespace64>.json.
   Cette écriture n'est ouverte qu'après le retour réussi de reserve() pour ce generate
   autorisé. authorize(), un préflight refusé, un doublon ou une réserve incomplète
   ne déclenchent aucun writer diagnostique ni accès historique supplémentaire.
   Ce nom ne ressemble pas à un événement lifecycle ni à un slot P1. L'inventaire fermé
   existant ignore déjà les documents non-lifecycle ; aucune nouvelle admission UNKNOWN.
   Publication exclusive atomique existante, pas de réécriture ni de retry.
3. Schéma fermé P0-NORMAL-FAILURE-DIAGNOSTIC-1.0 : timestampUTC, namespace/grant/request/
   preflightSHA, provider_attempts0/1, étape fermée réellement courante, famille/code
   technique bornés ou null si non disponibles, état lifecycle concerné et indication
   du succès/échec d'écriture de son marqueur. Jamais message, args, traceback, payload,
   secret, headers, texte pédagogique ou donnée réseau arbitraire.
4. Classification réutilisée : OpenAITransportError.code seulement si membre exact
   OpenAITransportErrorCode ; LocalFileSecurityError.code seulement si membre exact
   LocalFileSecurityCode ; OSError.errno entier borné ; sinon code null.
   Les codes locaux connus explicitement levés à ce point peuvent être conservés par
   une petite liste exacte de littéraux existants, jamais regex acceptant tout message.
   Pas de nouveau classifieur général d'exception ni lecture de str(error).
5. Étapes bornées du CREATE : résolution credential, revalidation, construction transport,
   dernier préflight, écriture tentative, appel transport, métadonnées réponse,
   publication RESULT, publication RESPONSE_CAPTURED, validation réponse, confirmation,
   parsing/guard/binding, publication PARSED, publication CONSUMED.
   TRANSPORT_CREATE couvre l'appel et la normalisation internes du transport existant ;
   aucune preuve de retour HTTP n'est inférée si create n'est pas revenu.
6. L'échec primaire reste prioritaire : le marqueur UNKNOWN est essayé comme auparavant,
   puis diagnostic privé best effort sans retries. Une panne du diagnostic, ou du marqueur
   secondaire, ne masque pas P0_NORMAL_OUTCOME_UNKNOWN, n'introduit aucun envoi et laisse
   RESERVED protecteur. Une panne de stockage peut empêcher la preuve d'être persistée :
   on ne la déclare pas produite. Après capture, conserver PARSING_REJECTED et l'erreur
   publique bornée existante ; diagnostic premier échec seulement.
   Le parcours nominal n'écrit pas de diagnostic d'échec.
   Matrice obligatoire des frontières :
   - avant capture : UNKNOWN essayé une fois ; erreur publique constante
     P0_NORMAL_OUTCOME_UNKNOWN, même si exists/publish du marqueur échoue ;
   - après capture, validation/parsing/guard : PARSING_REJECTED comme auparavant,
     erreur primaire existante préservée si le marqueur secondaire échoue ;
   - publication PARSED ou CONSUMED : diagnostic UNCONFIRMED seulement,
     aucun UNKNOWN/PARSING_REJECTED nouveau, erreur primaire existante préservée ;
   - panne du diagnostic : aucune deuxième publication de diagnostic dans le même
     generate, même après propagation au catch externe. Un booléen local au port
     marque la panne traitée avant toute écriture secondaire. Aucun retry de stockage.
7. Lecteur privé borné explicite pour ce nouveau document, dans le même adaptateur de reçu,
   validation fermée avec rattachement namespace/grant/request/preflight. Aucun endpoint
   public ou outil agent d'accès direct supplémentaire. Absence du nouveau diagnostic
   dans les historiques est normale ; elle ne modifie ni confirmed() ni l'issue.
8. La copie live et le package500 restent gelés. Correctif seulement dans le worktree
   source de développement, nouvelle candidate hors live. Futur rattachement exact,
   fenêtre P1, slots/réservations et consentements doivent être recontrôlés avant effet.

## Tests par impact obligatoires
Doubles déclarés avec transport compté, resolver synthétique, racine temporaire système :
- enum transport (tous codes) et erreur non typée hostile : UNKNOWN, cause bornée/null,
  aucun secret/texte/header/exception brut ni second envoi après nouvel essai refusé ;
- réponse retournée puis métadonnées impossibles, et parsing/guard impossible après capture ;
- publication RESULT impossible et publication RESPONSE_CAPTURED impossible ;
- diagnostic lui-même impossible, marqueur UNKNOWN impossible, les deux impossibles :
  erreur utilisateur stable, RESERVED reste protecteur, pas de faux succès/slot libre ;
- nominal : PARSED/CONSUMED et aucune preuve d'échec ; récupération historique inchangée ;
- ancien UNKNOWN V1 et preuve absente : octets inchangés, refus toujours actif ;
- champs/valeurs injectés invalides et lecteur de diagnostic substitué refusés ;
- régressions P0normal, continuité/rejetP1, HTTP, transport, sécurité/hygiène concernés ;
  Ruff/mypy/compilation applicables, pas de global complet ni live.

## Alternatives écartées
Enrichir UNKNOWN V1, ajouter un événement lifecycle ou desserrer l'inventaire :
affecte inutilement les preuves historiques. Logger exception/SDK brut : fuite possible.
Ajouter une réponse/consommation ou rembourser le slot : contraire au mandat.
