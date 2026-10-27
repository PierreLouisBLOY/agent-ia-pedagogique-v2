# Addendum LU-PRODUIT-01 — couverture source Windows exacte

Statut : PROPOSE POUR REVUE PREALABLE. Correctif borné d'un défaut confirmé par
la revue distincte, sans permission, fournisseur ou changement de périmètre.

Le témoin synthétique `UPPERCASE_SOURCE_COVERAGE_PROBE.json` montre qu'une source
`backend/unmanifested.PY`, absente du mapping, est ignorée par la sélection
actuelle tout en étant importable via `.py` sur Windows. La qualification ne
peut donc pas annoncer une couverture exhaustive dans cet état.

## Règle commune au mapping, à l'archive et à la copie extraite

Les quatre racines applicatives backend/frontend/tools/config et les six suffixes
.py/.js/.css/.html/.ps1/.json sont sélectionnés par `casefold`. Les noms relatifs
Posix **exacts** effectivement présents restent les clés du mapping ; aucune
normalisation ou résolution silencieuse d'une collision. Les répertoires
__pycache__ sont exclus par `casefold`, le helper empêchant séparément la lecture
de leurs bytecodes non vérifiés.

Deux chemins du mapping ou de l'archive égaux après `casefold` sont refusés,
même si un répertoire Windows sensible à la casse permet de les conserver.
La couverture copy/mapping/ZIP reste exactement égale avant tout effet : une
source .PY/.JS/.JSON ou une racine BACKEND ajoutée après la fabrication ferme
le binding. Une variante explicitement incluse et admise est vérifiée avec ses
octets et son orthographe exacte, sans être ignorée. Le fichier metadata source
canonique unique et le binding commit/tree restent ceux de l'addendum 2.0.

## Contrôles / retour arrière

Positif : orthographe exacte incluse dans manifeste/ZIP/copie, y compris une
variante de suffixe ou de racine. Négatif : variante ajoutée hors manifeste,
collision de clés ou de chemins ZIP après casefold, archive divergent de la
copie. Probes synthétiques uniquement ; aucune pièce d'autorité ou source métier
modifiée. L'assembleur et le chargeur doivent adopter la même règle après revue.
Retrait de l'option normale ferme P1 ; aucun contournement par une exception.
