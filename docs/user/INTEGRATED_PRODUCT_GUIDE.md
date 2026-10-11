# Projet V2 — utilisation de l’atelier local

Cette notice concerne le produit intégré LU-PRODUIT-01. La recette enseignante
reste à réaliser sur les documents et versions identifiés dans le dossier de livraison.

## Une configuration locale, puis un seul lanceur

La distribution contient `DEMARRER_NORMAL.cmd`, les sources et un installateur
hors ligne. Installer les dépendances avec `INSTALLER_HORS_LIGNE.ps1`, profil
`runtime`, et un Python 3.12 Windows AMD64 existant. Le script vérifie les octets
du package et les locks ; il refuse d’écraser un environnement existant.

Créer un fichier de configuration privé depuis `config/local-v2.example.json`.
Utiliser les trois valeurs du même reçu de provisionnement : `runtime_path`,
`data_root` et `runtime_sha256`. La seed originale n’est pas un runtime.
Indiquer un `saved_root` privé distinct pour les versions sauvegardées, et
`python_path` vers le Python 3.12 du package. `word_profile: "product-v7"`
sélectionne les exports avec tableaux natifs et médias validés.

Lancer `DEMARRER_NORMAL.cmd -ConfigPath 'CHEMIN/configuration.json'`, ou, depuis
les sources, `tools/launch-local.ps1 -ConfigPath 'CHEMIN/configuration.json'`.
Ouvrir l’adresse locale affichée. Garder le terminal ouvert ; `Ctrl+C` arrête le
serveur. Relancer la même commande pour reprendre. Fermer seulement l’onglet
du navigateur ne ferme pas le serveur.

## Demander une ressource

1. Sur l’accueil, décrire la famille, le public, les notions et les objectifs.
2. Confirmer la proposition : enseignement exact, version du programme ou
   référentiel, question/activité et capacités/compétences, notions et profondeur.
   L’année BTS correspond à la progression locale.
3. Consulter les sources exactes de la notion ou la bibliothèque. Lire le passage,
   sa provenance, sa version et son statut. Une présence dans SQLite ou une
   identité canonique n’atteste pas une autorité officielle. Les passages non
   éligibles au contexte restent consultables, avec leur motif de refus.
4. Confirmer et préparer. La préparation ne fait aucun appel fournisseur.
5. Si un profil normal explicitement adopté est configuré, lire l’aperçu exact
   des données à transmettre, la destination, la borne de coût et les limites.
   Confirmer les deux consentements dans l’interface avant la création.

Avec les admissions locales de passages complets, sélectionner le contenu ou
la méthode proposé pour le contexte exact. Changer la question, l’activité,
les capacités, la profondeur ou l’année locale peut rendre ce passage indisponible
pour la préparation. Les libellés de notions servent alors au cadrage et restent
consultables. « Utilisation locale admise » ne signifie ni source officielle,
ni validation scientifique ou pédagogique du contenu.

Le mode livré sans `p0_normal_profile` permet la consultation et les parcours
locaux sur des productions conservées ; le bouton de génération indique son
indisponibilité. Il ne fabrique pas de résultat de démonstration.

L’activation normale nécessite une décision propriétaire sur le package,
le runtime, les sources admises, le tarif et le tokenizer vérifiés, la délégation
à l’opérateur Windows et le budget exacts. Ces pièces sont privées et ne sont
ni une clé dans le navigateur ni un ancien grant Boréal/MEGA réutilisable.
Après cette adoption, le consentement de chaque demande se donne dans V2 ;
Codex n’intervient pas dans chaque opération ordinaire. La clé, si requise,
est saisie masquée dans le terminal du lanceur après réservation. Une fenêtre
PowerShell affichant sa propre invite n’est pas l’invite de saisie de la clé.

À la première création de la session, revenir au terminal laissé ouvert par le
lanceur si l’invite « Credential OpenAI P0 » apparaît. Aucun caractère ne
s’affiche pendant cette saisie masquée : coller la clé à cette invite, puis
appuyer sur Entrée. Ne pas la saisir à l’invite PowerShell ni dans le navigateur.
Elle reste en mémoire pour cette session ; arrêter le lanceur l’efface de ce
cache de session. Une console sans saisie masquée utilisable est refusée.

## Contrôler et modifier

Le panneau « Sources & contexte » distingue les références, les vérifications
de la version courante, les calculs et les revues effectivement réalisées.
Une réserve ou « non vérifié » demande une relecture ; un schéma valide
ne prouve pas à lui seul la qualité pédagogique. Une review fournisseur
indépendante n’est pas activée par la permission CREATE.

Dans « Mes productions », choisir une version exacte, « Rouvrir », puis
« Reprendre dans l’atelier ». Consulter séparément le sujet élève et la partie
enseignante. « Modifier » ouvre les champs permis. Conserver les changements
dans une nouvelle version avant sauvegarde/export ; le parent reste immuable.
Les réponses tardives sont refusées lorsque le contexte a changé. Les contrôles
du parent ne deviennent pas automatiquement ceux de l’enfant.

Les modifications locales sont bornées par les contrats existants. Une modification
touchant les données dont dépend un média peut exiger sa recomposition ; V2 refuse
un export périmé. Les opérations indisponibles affichent leur motif, sans appel
fournisseur de secours.

## Sauvegarder, fermer et reprendre

Conserver la version enfant, puis sauvegarder avec l’action proposée. Vérifier
l’identité et le message de confirmation. Les brouillons non conservés restent
signalés avant navigation ou fermeture ; les préférences du navigateur ne sont
pas la sauvegarde de référence.

Après arrêt/redémarrage du lanceur, ouvrir « Mes productions », choisir la version
sauvegardée et la rouvrir. Le titre seul ne distingue pas deux versions : utiliser
aussi leurs identités dans le panneau de traçabilité.

## Exporter

Choisir explicitement Sujet élève, Corrigé ou Barème selon les documents disponibles.
Télécharger le DOCX, accepter sa réception si le navigateur le demande, puis ouvrir
le fichier reçu. Le sujet élève conserve ses espaces de réponse et n’inclut pas
les réponses enseignantes. Un document requis manquant ou un média périmé bloque
l’export concerné.

Le DOCX est éditable dans Word. Le contrôle interne des tableaux, images, textes
et publics est distinct d’un contrôle visuel des pages Word. Les limites de rendu
de la livraison sont indiquées dans le dossier unique. Un PDF technique de contrôle
n’est pas un export PDF applicatif.

## En cas d’arrêt ou d’incertitude

Lire le motif affiché. Après un appel fournisseur incertain, ne pas relancer la même
demande : sa réservation et ses preuves sont conservées pour réconciliation.
Il n’y a aucun retry, fallback ou COUNT implicite. Ne pas changer une empreinte,
un chemin de base ou une autorisation pour contourner un refus.
