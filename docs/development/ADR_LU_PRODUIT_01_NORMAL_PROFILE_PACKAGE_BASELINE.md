# Addendum ADR LU-PRODUIT-01 — baseline normale sans checkout Git

Statut : PROPOSE POUR REVUE PREALABLE. Successeur limité au binding source/package
du chargeur P1. Aucun profil actif, téléchargement, grant ou appel fournisseur.

## Défaut concret

Le chargeur précédemment qualifié exige `git rev-parse HEAD` dans l'application.
Une distribution extraite sans `.git` ne peut donc pas utiliser sa composition
normale, bien que son archive et chaque fichier source soient déjà liés à la
décision propriétaire. Le mode local sans profil demeure inchangé.

## Successeur fermé

Le manifeste de source admis devient `P0-NORMAL-SOURCE-MANIFEST-2.0`, avec
exactement `schema`, `source_commit` (SHA Git 40 caractères hexadécimaux minuscules),
`source_tree` (SHA Git 40 caractères) et `files` (couverture source exacte déjà
prévue par le contrat 1.0). `source_commit` doit égaler `profile.baseline_commit`.
`source_tree` désigne l'arbre Git de fabrication attesté dans le dossier de
qualification ; il ne prétend pas être recalculé depuis le seul sous-ensemble
applicatif. L'empreinte SHA-256 du manifeste complet reste celle liée à P1/G1 et
à la décision propriétaire. Aucun simple texte de commit n'est accepté sans ce
binding binaire et cette couverture.

L'archive exacte admise doit embarquer une et une seule copie canonique identique
octet pour octet de ce manifeste, nommée `P0_NORMAL_SOURCE_MANIFEST.json`, au même
préfixe racine que les fichiers applicatifs. La comparaison source extraite /
mapping / archive reste exhaustive sur le périmètre déjà défini. Un manifeste
1.0 n'active pas silencieusement ce successeur ; il doit être réadmis avec les
autres nouvelles identités exactes du profil.

Si `.git` existe **dans la racine applicative exacte**, le chargeur vérifie en
plus le HEAD et `HEAD^{tree}` réels contre le manifeste. Toute erreur, lien
symbolique/reparse ou discordance est un refus fermé ; aucun fallback vers le
manifeste après une erreur Git. En absence de `.git` à cette racine, il n'invoque
pas Git et n'utilise pas un dépôt parent : l'archive, le manifeste adopté et les
empreintes exhaustives qualifient le binding. Il ne crée pas de `.git`.

## Contrôles / limites / retour arrière

Positif : copie extraite synthétique sans `.git`, archive/manifeste exacts, aucune
invocation Git, zéro secret/transport ; checkout exact avec HEAD/arbre concordants.
Mutations : commit ou arbre mal formés, commit du profil divergent, manifeste
embarqué absent/dupliqué/divergent, préfixe divergent, fichier source ou package
modifié, checkout dont HEAD/arbre diffèrent ou commande Git échoue. Les décisions
et tarifs des tests restent synthétiques.

Le successeur ne change ni la admission des sources pédagogiques ni les règles
financières, les réservations ou la sécurité HTTP. L'archive est une preuve de
fabrication admise, pas une signature cryptographique de personne. Une nouvelle
version impose un nouveau manifeste et de nouvelles identités adoptées. Retour
arrière : retirer le profil normal ; aucune donnée métier ni preuve historique
n'est modifiée. La reprise confirmée conserve ses exigences attestées.
