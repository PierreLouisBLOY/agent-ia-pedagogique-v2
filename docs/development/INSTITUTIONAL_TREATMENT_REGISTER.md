# Registre courant des notions institutionnelles

Le registre est une projection en lecture seule de la qualification deja
versionnee. Il ne publie pas de nouvelle qualification et n'accorde aucune
admission, promotion, recette enseignante ou autorisation fournisseur.

Entree : `InstitutionalCatalogInbound.treatment()`, composee par
`inspect_institutional_catalog(target, treatment=True)`. La cible appartient
a la configuration serveur et est authentifiee avant et apres la lecture.
Aucun chemin de base fourni par le frontend n'est accepte.

Sortie `INSTITUTIONAL-NOTION-TREATMENT-1.0` :

- toutes les identites CANONICAL presentes dans le catalogue, une fois chacune ;
- dispositions exactes de leurs preuves : VERIFIED_EXPLICIT, VERIFIED_IMPLICIT,
  SOURCE_GAP, HUMAN_REVIEW_REQUIRED ou NO_APPLICABLE_FRAMEWORK ;
- relations admises avec version de cadre, element, ancetres, capacites ou
  competences dans leur portee explicite, document, pages et locator ;
- empreintes de qualification et decision d'admission, type EXPLICIT/IMPLICIT ;
- contextes historiques separes, sans autorite institutionnelle implicite ;
- profondeur pedagogique et progression BTS locales distinctes de la source ;
- autorite disciplinaire a etablir par ses preuves propres, recette non realisee.

Le nombre de notions et les liens sont lus de la cible authentifiee ; aucun
scenario M01-M07, libelle de demonstration ou alias ne definit la couverture.
Les identites MERGED historiques restent conservees et sont exclues de
l'univers CANONICAL. Sans qualification versionnee, des lignes ACTIVE ou
VALIDATED seules ne deviennent jamais admises.

La matrice STMG reutilise cette projection de preuve pour annoncer
RESOLVED_ADMITTED uniquement lorsqu'un rattachement verifie appartient a ce
cadre exact. Elle preserve les relations contextuelles non admises et n'etend
pas Management a SGN, ni une prescription de Premiere a Terminale.
Une relation admise ne valide pas toutes les connaissances d'une notion.
Une source manquante ne constitue pas la preuve d'absence de cadre applicable.

Les consommateurs doivent afficher les limites des sources et ne pas utiliser
ce registre comme une attestation du fond disciplinaire, des calculs ou de
l'acceptation pedagogique. Les tests synthetiques verifient le mecanisme de
preuve ; ils ne fournissent aucune nouvelle source officielle.
