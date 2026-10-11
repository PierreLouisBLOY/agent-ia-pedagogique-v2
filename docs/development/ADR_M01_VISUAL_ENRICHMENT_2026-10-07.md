# ADR — Enrichissement visuel local de M01

Statut : décision locale relue avant implementation, dans le mandat propriétaire
PROJET_V2_ENRICHISSEMENT_VISUEL_M01 (go). Entrée : b6466778e196f7c4164778a2503b0bcdecd63edd.

## Décision et limites

Réutiliser CourseMediaInbound et MediaAssetWorker. Aucun nouvel agent, port réseau,
SDK, accès SQL, seed ou fournisseur. Les documents, questions, réponses professeur,
capacités et rattachements institutionnels sont repris à l'identique par Application.
Le parent et ses quatre médias originaux restent conservés. Trois schémas peuvent
être redessinés avec les seuls exemples et circuits déjà décrits dans le cas.

Étendre explicitement VISUAL-BRIEF-1.0 par le profil fermé
COURSE_LOCAL_ILLUSTRATION_V2 : LIBRARY_SCENE (trois personnages), CHARACTERS
(trois vignettes dans un même média), TIMELINE (cinq étapes) et WORKSPACE
(trois zones à compléter). Les anciens types restent disponibles ; le profil V1
et ses octets de rendu demeurent inchangés. Le renderer V2 déclare une identité
distincte pour les nouveaux dessins. Une scène est une illustration locale du
cas fictif, jamais une photographie ni une preuve institutionnelle.

AFTER_CONTEXT est une nouvelle position réservée à la section CONTEXT et au type
SCENARIO_ILLUSTRATION. Le contrôle de production, de capacité et de notions reste
obligatoire avant rendu et export. Toutes les autres positions conservent leurs
ancres Document/Concept. Les plafonds existants restent huit médias, PNG 64 KiB
et chapitre 128 KiB. Provenance, licence, hash, légende et alt sont exigés.

La revue reçoit six axes explicites, dont la qualité de lecture. Son routage est
qualifié avec un double déclaré, sans appel AG-04 fournisseur ; l'inspection de
tous les pixels et pages est une preuve locale distincte, pas une acceptation
pédagogique. Les portraits ne donnent pas les réponses aux questions ; le plan
de transfert contient des champs vides, sans solution imposée.

## Vérifications exigées

Contrats positifs et mutations des types, profils, ancres et identités ; répétition
du rendu ; limite de taille ; projection élève sans corrigé ; intégrité OOXML et
absence de liens externes ; huit médias reçus par la review ; sauvegarde et
réouverture par Application. Comparaison exhaustive des champs non visuels au
parent ; contrôle des deux exports et de toutes les pages ; lint, typecheck et
tests applicables. Les échecs historiques sont consignés sans skip ajouté.

## Relecture préalable

Le profil est additif, borné et sans déplacement de frontière. Les données
institutionnelles ne sont pas déduites des images. Les quatre fonctions visuelles
initiales restent couvertes. Le successeur de garde conserve les pins et preuves
historiques et couvre le delta courant. Verdict local : compatible avec le mandat,
implémentation autorisée hors live ; recette propriétaire toujours en attente.

## Complément après qualification du checkpoint 62890e4

Le scanner partagé classe un appel via indice de dictionnaire comme dynamique
non résolu. La sélection de dessinateur emploie donc des branches explicites pour
les seuls layouts fermés du profil. Aucun scanner ni frontière ne change.
Les tests vérifient le positif et rejettent la réintroduction d'un appel par
indice ou d'un serveur HTTP. Les pixels et exports existants doivent rester
identiques avant livraison du correctif.
