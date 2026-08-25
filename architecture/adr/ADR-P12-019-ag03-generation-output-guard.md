# ADR-P12-019 — Guard de sortie pré-matérialisation AG-03

## Statut

Accepté pour la Phase 12.8-F.

## Contexte

Les chemins G01/G02/G03 produisent un `GenerationPortResult` technique puis
matérialisent C-08 et, pour G03, un `CorrectionResult`. La cohérence de lineage
est déjà revalidée, mais aucune frontière unique n'impose encore les contrôles
bornés de grounding déclaré, de structure et de contenu potentiellement hostile
avant cette matérialisation.

## Décision

`GenerationOutputGuard` est un composant pur et obligatoire entre le résultat
technique et toute matérialisation :

```text
PreparedGenerationCall / PreparedCorrectionCall
+ GenerationPortResult
+ GenerationGuardPolicy caller-supplied
+ GenerationClaimAttribution déclarées
→ GenerationGuardAssessment recomputable
→ matérialisation seulement pour ALLOW / ALLOW_WITH_WARNINGS
```

Le guard revalide les helpers exacts C/E pour le Prepared et le résultat. Son
assessment est lié à ces objets exacts puis recomputé avant construction de
`ProductionCandidate` ou `CorrectionResult`. `REPAIR_REQUIRED`, `ABSTAIN` et
`REJECT` bloquent toute sortie actuelle.

Une incohérence de lineage du Prepared ou du résultat lève
`GenerationGuardError` fail-closed avant assessment, avec les issues fermées
`PREPARED_LINEAGE_MISMATCH` ou `TECHNICAL_RESULT_MISMATCH`.

La règle `NO_EVIDENCE_NO_GROUNDED_CLAIM` est imposée structurellement : une
attribution `GROUNDED` ou `SYNTHESIZED` exige une référence, et cette référence
doit appartenir aux evidence refs réellement utilisées. Cette relation déclarée
ne prouve aucune adéquation sémantique. `SOURCE_MATCH` reste différé aux
mécanismes de review/validation indépendants.

Les contrôles structurés se limitent à la présence d'un payload, aux clés
top-level requises/autorisées et, si explicitement configuré pour G01/G02, à un
mapping de sections. Aucun JSON Schema général, CAP-T01 ou dépendance
`jsonschema` n'est introduit.

Le scanner applique des patterns FR/EN fermés et casefoldés au contenu et aux
feuilles string du payload. Il produit seulement un code et un chemin logique ;
il ne conserve pas le texte, ne suit aucune URL, ne lit aucun fichier et
n'appelle aucun outil. Ces signaux sont non autoritatifs et ajoutent des
warnings structurés sans déclarer la sortie sûre, fiable ou validée.

`GenerationRepairProposal` décrit uniquement une catégorie et des issues. Elle
n'exécute ni prompt, ni provider, ni retry et ne peut inventer une preuve.

## Rationalisation des contrôles

Le contrôle D sur `execution_metadata` reste un refus fail-closed de vocabulaire
d'autorité dans une surface metadata. Le scanner F reste un indicateur de
contenu pouvant conduire à `ALLOW_WITH_WARNINGS`. Ils ne sont pas fusionnés car
leurs réactions sont différentes. Le scanner AG-02 n'est pas importé afin
d'éviter une dépendance agent vers agent.

## Conséquences et limites

- priorité déterministe : `REJECT > ABSTAIN > REPAIR_REQUIRED >
  ALLOW_WITH_WARNINGS > ALLOW` ;
- les statuts `REFUSED` et `INSUFFICIENT_EVIDENCE` conduisent à `ABSTAIN` ;
- `PARTIAL` produit au minimum `ALLOW_WITH_WARNINGS` en l'absence d'un défaut
  plus fort ;
- les warnings techniques sont conservés et les signaux du guard sont ajoutés ;
- aucune review AG-04, validation, qualité, promotion, persistance ou gate n'est
  réalisée ;
- aucun provider, runtime, I/O, retry ou exécution de repair n'est ajouté.
