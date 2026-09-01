# Phase 12.16-G2-V5 — Des causes V4 aux exigences V5

## Périmètre

Ce lot transforme le diagnostic V4.3 en contrat de calibration provider-neutral et strictement offline. Il ne modifie aucun fichier V4.1, V4.2 ou V4.3, aucune route runtime et aucun artefact historique.

## Audit mécanistique du contrat V4

| Mécanisme | Observation V4 | Effet établi | Exigence V5 |
|---|---|---|---|
| Prompt générique | « Score one bounded synthetic pedagogical calibration observation » sans définition de niveau | Le juge doit inventer son barème | Définition mesurée/non mesurée et quatre contrôles observables par critère |
| Critère opaque | Seule une ref comme `scn-06.quality.assessment-clarity` est transmise | Le sens précis du critère reste implicite | Rubrique complète et versionnée dans chaque observation |
| Échelle absente | Le schéma accepte un rationnel `[0,1]`, mais ne décrit aucun niveau | 47/48 résultats aux extrêmes 0 ou 1; un seul 1/2 | Échelle ordinale fermée 0–4 avec descripteurs vérifiables |
| Pas d'examples étalonnés | Un seul candidat isolé par call | Aucun point de comparaison intra-call | Contrôles observables communs et fixtures couvrant les cinq niveaux |
| Sortie sans preuve | Trois champs seulement : statut, numérateur, dénominateur | Aucune justification individuelle des inversions | Evidence, défauts, score, confidence et rationale courte |
| Schéma fermé | `additionalProperties = false` interdit toute rationale | Audit causal impossible après exécution | Schéma V5 fermé mais explicitement evidence-first |
| Pairwise post-hoc | Deux scores absolus sont comparés après deux calls distincts | Une égalité de scores saturés devient un tie | Contrat A/B direct, indépendant des scores absolus |
| Tie arithmétique | Égalité exacte de deux `Fraction` | 6/6 ties; aucun epsilon en cause | `TIE` valide seulement sans différence matérielle sur le critère |
| Métrique trinaire | `Strong > Mixed > Weak` exigé | Cible plus forte que la gate V4 `Strong > each negative` | Séparer métrique primaire et diagnostic Mixed/Weak |

## Pourquoi les scores V4 sont quasi binaires

La concentration 0/1 n'est pas produite par le parser. `NormalizedScore` accepte tout rationnel exact dans `[0,1]` et le réduit par PGCD. Il n'existe ni arrondi, ni cast booléen, ni conversion d'un PASS/FAIL en score dans la chaîne V4 auditée. L'agrégation compare ensuite des `Fraction` exactes et ne réduit pas la granularité.

La quasi-binarité provient donc du jugement en amont : le prompt demande un score sans donner de niveaux sémantiques. Les règles fail-closed concernent la forme, `INCONCLUSIVE` et la validité du rationnel ; elles n'imposent pas 0 ou 1. Les 48 scores d'anchors analysés sont conclusifs, donc `INCONCLUSIVE` n'explique pas la distribution.

## Exigences fonctionnelles V5

1. Chaque critère possède exactement quatre contrôles observables et indépendants.
2. Chaque rubrique dit explicitement ce qui est mesuré et ce qui ne l'est pas.
3. Le niveau vaut le nombre de contrôles étayés, de 0 à 4, sauf contradiction matérielle qui force 0.
4. Tout contrôle satisfait possède une evidence localisée.
5. Tout contrôle non satisfait possède un défaut localisé et une sévérité.
6. Le parser rejette un niveau non supporté par les preuves.
7. Les niveaux 1, 2 et 3 doivent être atteignables par construction.
8. Le pairwise compare simultanément A et B et ne contient aucun champ de score absolu.
9. Une différence hors critère n'autorise pas une préférence.
10. Les tiers, modèles, providers et scores attendus restent absents des observations.
11. Le corpus V4 reste byte-equivalent et n'est utilisé que comme entrée aveugle.
12. Toute exécution live V5 reste fail-closed.

## Exigences non fonctionnelles

- Version du contrat Scorer : `12.16-g2-v5-scorer-contract-v1`.
- Version de l'échelle : `12.16-g2-v5-ordinal-scale-0-4-v1`.
- Version pairwise : `12.16-g2-v5-pairwise-v1`.
- Hash logique du contrat : `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`.
- Aucun SDK fournisseur, credential ou transport dans les nouveaux modules.
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.

## Critère de clôture de ce lot

Le lot peut être `PASS` si le contrat, le corpus synthétique, les parsers, le pairwise, le blinding et le fail-closed passent offline. Cela n'atteste pas qu'un modèle sémantique réel scorera les anchors V4 conformément aux humains ; cette validation exige une étape propriétaire ultérieure et n'est pas simulée ici.
