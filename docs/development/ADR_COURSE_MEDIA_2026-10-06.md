# Médias pédagogiques locaux dans COURSE

Décision fondée sur le mandat M01 programme et illustrations du 6 octobre 2026,
depuis db4b522. Revue locale préalable de la répartition des responsabilités :
les workers conversation et R3 coordonnent des appels existants, le writer COURSE
produit le DOCX, le store SavedProduction conserve les versions. Aucun service
média équivalent n'existe. Aucun agent, orchestrateur ou store supplémentaire
n'est créé. Les frontières Application, contrats, ports et adaptateurs restent
celles des phases 6 et 11.

VisualBrief est un contrat de contenu de pedagogical_design. AG-03 propose ce
contenu par sa transformation existante ; Application contrôle les liens vers
la production, le document et les capacités. MediaAssetWorker appartient à
materialization_export/Application et consomme un port de dessin. Le worker
ne décide ni de la prescription institutionnelle ni de l'acceptation pédagogique.

Le profil local Windows dessine en mémoire avec GDI et encode un PNG RGB borné
avec la bibliothèque standard Python. Il ne crée ni fenêtre ni processus et
n'installe aucune dépendance. La reproductibilité porte sur les mêmes polices
et le même environnement Windows ; l'identité du renderer est conservée.
Les médias fournis sont importés depuis des octets explicitement admis, jamais
depuis une URL ou un chemin choisi par l'agent. Les acquisitions externes et
générées restent des sources de médias possibles, soumises à une admission
distincte de leurs octets et droits ; aucun port réseau n'est ajouté ici.

COURSE-CHAPTER-MEDIA-2.0 conserve briefs, provenance, licence, SHA et PNG dans le
record versionné existant, sous les bornes de taille actuelles. Les projections
élève/professeur filtrent les variantes avant export. Le writer insère uniquement
des PNG validés, avec légende et texte alternatif, sans relation externe.
AG-04 reçoit la description structurée exacte du visuel, ses engagements SHA et
les cinq exigences de revue. Une revue textuelle ne certifie pas les pixels :
leur inspection reste une preuve séparée et l'acceptation reste humaine.

Le contexte institutionnel COURSE peut mobiliser jusqu'à 16 notions, comme son
contrat de sélection institutionnelle, afin de couvrir la question 1.1. Le
contrat historique et les autres familles conservent leur borne de huit sujets.
Les limites du transport, les contrôles financiers et les scanners restent
inchangés. Les douze notions sont résolues contre la qualification admise.

Tests requis : liens et mutations VisualBrief, PNG/CRC/taille/SHA, droits absents,
refus réseau implicite, reproductibilité locale, variantes sans fuite de réponse,
AG-03/AG-04 via doubles explicites, export/sauvegarde/réouverture et couverture M01.
La succession du garde actif porte sur les seuls owners du correctif ; anciens
pins et résultats conservés. Aucun live, promotion, push ou merge dans ce lot.
# Complément constaté lors de la sauvegarde réelle

La filiation M01 contient déjà trois versions. Le quatrième enfant illustré est
refusé par `R4_VERSION_LIMIT` après la sauvegarde des ancêtres. Le successeur
`COURSE-CHAPTER-MEDIA-2.0` admet au plus 32 versions par production dans le même
magasin R4. Le plafond de trois reste inchangé pour les contrats historiques ;
les limites de 300 enregistrements et 16 Mio restent actives. Aucun ancêtre n'est
supprimé, réécrit ni privé de son contrôle d'identité. Ce complément reste dans
la responsabilité de persistance existante ; tests du quatrième enfant et du
refus au-delà de 32 exigés, ainsi que la non-régression du plafond historique.
