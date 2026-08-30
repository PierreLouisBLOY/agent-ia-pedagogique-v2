# ADR-P12-065 — Corpus d'anchors versionné et prévalidé humainement

- Statut : Accepté
- Date : 2026-08-30
- Phase : 12.16-G2-ANCHOR-CORPUS-REMEDIATION-A

## Contexte

Le corpus `12.16-g1-v1` a fourni une baseline diagnostique reproductible, mais
la calibration finale et sa réconciliation humaine ne démontrent pas une
différenciation pédagogique suffisante. La revue humaine observe `0/16` ordres
stricts, `16/16` ordres faibles, `28` égalités et `0` inversion. Neuf critères
demandent une révision d'anchors et sept restent soumis à une décision
propriétaire.

Modifier v1 détruirait la traçabilité de la calibration déjà clôturée. Recalibrer
le juge avant de disposer d'anchors humainement différenciables confondrait un
défaut de corpus avec un défaut du scorer. La décision propriétaire est donc de
réviser d'abord le corpus, sans appel fournisseur ni changement de route.

## Décision

Le corpus `12.16-g1-v1` reste immuable et prend le statut
`CLOSED_DIAGNOSTIC_BASELINE`. Un nouvel owner test-only établit le corpus
`12.16-g1-v2` sous `tests/calibration/pedagogical/`, sans import depuis le
runtime ou vers le runtime.

V2 conserve les huit scénarios, leurs niveaux, intentions, sections et deux
critères. Il crée 24 nouveaux IDs opaques, trois anchors par scénario et 48
couples anchor/critère. Les attentes ordinales restent dans une table d'analyse
séparée. La projection destinée à un éventuel scorer ne contient ni ID d'anchor,
ni tier, fournisseur, modèle, score attendu, secret ou chemin.

Chaque critère possède une matrice de différenciation pré-déclarée. Le contenu
fort vise l'exploitabilité immédiate, le contenu intermédiaire conserve une
insuffisance bornée et le contenu faible reste structurellement valide tout en
portant un déficit pédagogique perceptible. Les gates statiques détectent les
doublons, écarts triviaux, différences cosmétiques, sections manquantes,
défauts non déclarés et contradictions de détail. Elles ne remplacent pas le
jugement humain.

Avant toute nouvelle calibration fournisseur, v2 doit passer une
prévalidation humaine aveugle sur 24 IDs nouveaux. L'objectif de design est
`16/16` ordres humains stricts, avec `24/24` structures valides, aucune
inversion et aucune relation non évaluable. Toute égalité restante reçoit une
disposition explicite. Le paquet reste non rempli par le code et sa clé de
réconciliation demeure locale et ignorée par Git.

La politique Anthropic explicite `adaptive / low / 2048` est conservée
provisoirement. La recalibration du juge est différée jusqu'à la prévalidation
humaine v2. Aucun seuil de release ou changement de route n'est autorisé par
cet ADR, et aucun appel live n'est permis dans ce lot.

## Conséquences

- Les preuves et checksums v1 restent comparables byte-for-byte.
- V2 dispose d'une identité, d'un checksum et d'un paquet humain distincts.
- Une révision future de v2 produit une nouvelle version et un nouveau checksum.
- La réussite des gates statiques signifie seulement « prêt pour revue humaine ».
- La calibration fournisseur reste interdite avant décision propriétaire après
  prévalidation.
- ADR-P12-063 continue de définir la séparation test-only et le protocole
  aveugle; ADR-P12-064 continue de définir la policy du scorer.

## Options écartées

- Modifier `12.16-g1-v1` : rejeté, car la baseline diagnostique deviendrait
  irréproductible.
- Recalibrer immédiatement le juge : rejeté, car les égalités humaines montrent
  d'abord un défaut de différenciation du corpus.
- Rendre l'anchor faible structurellement invalide : rejeté, car structure et
  qualité pédagogique sont des responsabilités distinctes.
- Réutiliser les IDs aveugles v1 : rejeté, car ils permettraient de rapprocher
  la nouvelle revue des résultats antérieurs.
- Lancer une matrice exploratoire v2 : rejeté, car aucune prévalidation humaine
  n'est encore disponible.
