# ADR — projection bornée des preuves vers AG-03

Entrée : d10e521a245d316c662e4d601be6a8c2a406c32a.
Le préflight local des quatre scopes résolus révèle P0_PROVIDER_INPUT_SIZE :
la résolution complète est transmise deux fois, avec des métadonnées d'inventaire.

Décision : le contexte fournisseur de contenu devient une vue explicitement
versionnée. Application conserve le contexte complet, sa résolution, ses preuves
et son SHA. La vue transmet sélection exacte, objectifs, progression, notions,
éléments/capacités/compétences/limites retenus, liens et locators, version et SHA
du document, statut A et engagement SHA sur la résolution complète. Elle n'envoie
pas les scopes candidats d'autres programmes, ni la copie intégrale de l'inventaire.
La sortie demeure du contenu seul ; bind_p0_content réattache les bindings locaux
originaux. Le fournisseur ne peut pas changer la sélection ou une identité locale.

Les paragraphes généraux du thème et les justifications explicites répétées
restent dans la preuve complète engagée par SHA ; la question sélectionnée et
les compétences/capacités/limites gardent leurs prescriptions. Chaque lien porte
son engagement SHA. La justification IMPLICIT est transmise intégralement.

La limite de 12 288 octets, le modèle et les paramètres restent inchangés.
L'admission B/C demeure séparée et les données locales restent locales. Une preuve
implicite conserve sa justification ; aucun claim officiel n'est créé par la vue.

Relecture : changement ordinaire d'une projection outbound pure, sans transport,
SQL, secret, nouvelle autorité ou changement de garde partagé. Les tests doivent
prouver présence des prescriptions et engagements, sortie liée au contexte complet,
refus des substitutions et de dépassements, ainsi que les préflights des scopes
M01/M05/M06/M07. Successeur de pins et comparaison globale sur le HEAD final.
