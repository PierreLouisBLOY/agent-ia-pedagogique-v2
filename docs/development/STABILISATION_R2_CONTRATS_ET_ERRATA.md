# Contrats actifs et errata R2

## Pointeur de reprise au 7 octobre 2026

Entrée inspectée : `85caccd778ca148bd061830546b85bcc0f041e85`.
Premier correctif publié : `629fabb6e49c258dd866c43c781172145777b2fc`,
branche `codex/stabilisation-20261007`. Qualification globale et intégration
technique en cours. Aucun nouveau live n'est autorisé par cette stabilisation.
Les notes de septembre restent des états datés ; les résultats de populations
de tests différentes ne s'additionnent pas.

## Renvois et correspondances consommés

| Objet | Contrat ou mapping actif | Garantie et limite |
|---|---|---|
| Identités et états SQLite | `backend/adapters/outbound/persistence/vocabulary.py` | Mappings typés par propriétaire ; aucune enum globale commune imposée. Une valeur inconnue ne devient pas fausse. |
| Source consultée | `SEARCH-SOURCE-STATUS-1.0`, `search_source_status.py` | Passage CURRENT, identité, cycle de vie et validation séparés. RESOURCE exige sa version exacte ; aucune preuve A/B/C déduite. |
| Contexte institutionnel | `InstitutionalQualification`, `ReadSTMGAlignment`, `ReadBTSAlignment` | Notion, enseignement, version, élément, preuve et admission liés ; pas d'année officielle BTS déduite d'une progression locale. |
| Validation déterministe | `AssessmentValidation`, `ValidateAssessmentCommand`, `ValidateP0Command` | Résultat lié à la version et à l'empreinte ; les homonymes de résultats ne fusionnent pas leurs responsabilités. |
| Revue P0 | `P0-REVIEW-1.0` et `P0-REVIEW-1.1` | 14 ou 15 champs exacts ; incertitudes conservées par le successeur explicitement sélectionné, sans autorité de validation/promotion. |
| Dispatch P0/R3 | `OPERATION-IDENTITY-1.0` | Identité réservée, étape et corrélation traversent les ports. Non-rejeu Application inchangé. |
| Assemblage et sauvegarde | `AssessmentBundle`, `P0Production`, `SavedProduction` | Bundle immuable ; enfant distinct, historique exact, aucune review héritée par la nouvelle version. |
| Présentation de cours | `COURSE-EXPLAINED-1.0`, `COURSE-CHAPTER-1.0`, `COURSE-CHAPTER-MEDIA-2.0` | Voies distinctes. Le chapitre riche local M01 ne qualifie pas le standard fournisseur général. |
| Sécurité et compensation | Frontières Phase 6/11, scanner partagé, ports de transactions | Délimiteurs = réduction de confusion, sans garantie absolue. Compensation limitée aux effets prévus ; atomicité promise vérifiée séparément. |

Les champs SQL `primary`, l'importance et la profondeur officielle ne sont pas
normalisés en une notion principale unique sans décision de domaine. Les
waivers sont des dispositions identifiées, jamais des résultats PASS.

## Errata documentaires reliés aux originaux

P09, étapes 9.6–9.8 : la restitution privée R2 conserve les 269 blocs dans
l'ordre, dont 250 paragraphes et 19 tableaux. Les trois originaux restent
inchangés ; les 18 pages de la restitution ont été inspectées. Le manifeste
privé lie XML, texte, tableaux et fichiers. La restitution complète contenant
les pièces privées n'entre pas dans Git.

P10, QL01 : l'édition originale contient 230 occurrences et 222 codes
distincts, paragraphes et cellules compris. Les répétitions de codes dans des
attendus `FAIL / ...` sont des références au catalogue. La répétition n'établit
pas une collision sémantique, ni une panne runtime. L'original est conservé.

P01/P02 : la destination actuelle des concepts est décrite dans
`REPOSITORY_STRUCTURE.md` et les mappings ci-dessus. Les textes originaux
manquants de 1.21-G/H et le mapping exhaustif des 363 règles historiques ne
sont pas reconstitués comme citations certaines. Cette matrice couvre les
contrats consommés par les parcours actuels ; elle ne prétend pas réparer
toutes les annexes historiques.

## Qualification conservée

Les 210 formules approuvées, admissions institutionnelles A01/A02/A03/A04B,
Boréal et ses sept critères inchangés restent acquis dans leurs portées.
L'autorité A ne valide pas automatiquement les qualités B/C. La recette
enseignante des exports et la décision de release restent humaines.
Les résultats et autorisations historiques sont conservés sans rejeu.
