# Addendum ADR LU-S5 — révision locale et fraîcheur média

Statut : PROPOSAL_NOT_SELECTED. LU-PRODUIT-01. Complément des ADR média et HTTP
déjà relus ; aucun contrat historique remplacé.

Disposition : la revue de coordination retient seulement un rebind pur lorsque
dependencies(parent) == dependencies(child), avec refus explicite de tout
changement de dépendance. L'invalidation null décrite ci-dessous n'est donc pas
implémentée ni adoptée ; elle reste une proposition tracée. Le rebind pur est
couvert par l'ADR média initial relu et ses tests de fraîcheur.

## Défaut et décision proposée

Le plan média lie une version exacte. La révision P0 change cette version :
conserver le plan brut du parent refuse actuellement même un titre modifié.
Introduire un helper du contrat média appelé par la révision Application avant
construction de l'enfant. Il n'effectue aucune opération I/O ni génération.

Si aucune dépendance d'une entrée ne change, copier son plan dans la version
enfant avec version_ref actualisé et mêmes asset/brief/empreintes de contenu.
Si une dépendance change, invalider explicitement l'asset de cette entrée :
asset=null, omission_reason décrivant DEPENDENCY_CHANGED, dépendances courantes
exactes. Le PNG historique reste seulement dans le parent immuable. La présence
requise reste vraie ; l'export de son public est alors bloqué par le contrôle
existant REQUIRED_MISSING. L'affichage et le contexte AG-04 montrent MISSING et
l'invalidation. Aucune image n'est régénérée ; la route locale média explicitement
appelée sur cet enfant peut préparer un nouvel asset après les contrôles.

La disparition d'une dépendance ou de l'ancre refuse la révision concernée avec
PRODUCTION_MEDIA_DEPENDENCY_REMOVED ; pas de rattachement silencieux ailleurs.
La décision NO_MEDIA vide conserve sa raison en actualisant la version, sans
produire d'image. Les contextes/références du parent restent sous le binding de
ReviseSavedP0Candidate ; les autres contrôles P0 et la séparation du public
demeurent applicables. Les sources d'une reprise restent RESERVE.

Objets S5 : helper production_media.py et tests. Raccord S2 dans _revise,
avant ReviseSavedP0Candidate/ReviseP0Candidate, coordonné avec le producteur S2.
Le plan privé consigne l'invalidation ; aucun nouveau champ fermé ni scanner,
permission, SDK, source ou admission.

Tests : titre sans dépendance conserve exactement le PNG ; modification de
section liée retire seulement son asset dans l'enfant et bloque son export
requis ; modification non liée conserve les autres assets ; suppression de
dépendance refusée ; NO_MEDIA transmis sans rendu ; réparation locale explicite
puis sauvegarde/réouverture via Application ; parent intact dans tous les cas.
Ces tests ne qualifient pas la sémantique du nouveau dessin ni une recette.

Retour arrière : ne plus appeler le helper ; les révisions de versions média
sont refusées comme périmées. Ne pas modifier les enfants historiques.
