# ADR P12-016 — Préparation et coordination déterministes AG-03

## Statut

Accepté.

## Contexte

La boundary 12.8-B sépare les contrats agentiques du mécanisme outbound de
génération. Elle ne définit volontairement ni la préparation de
`GenerationPortRequest` depuis C-07 `ProductionRequest`, ni les contrôles de
cohérence entre capability, requête préparée et résultat technique.

Sans une couche déterministe dédiée, un caller pourrait associer une operation à
la mauvaise capability, perdre la lineage du step ou de la cible, élargir les
références d’evidence, ou appeler plusieurs fois le port sous couvert de retry.

## Décision

`GenerationCoordinator` fournit deux opérations explicites :

```text
GenerationPreparationRequest
→ prepare()
→ PreparedGenerationCall
→ execute()
→ GenerationPortResult techniquement cohérent
```

Le mapping local et fermé est :

```text
CAP-G01 → GenerationOperation.GENERATE
CAP-G02 → GenerationOperation.TRANSFORM
CAP-G03 → GenerationOperation.CORRECT
```

Ce mapping n’est pas un router : il ne choisit aucun agent, ne consulte pas la
registry et n’accorde aucune permission. Pour C-07, CAP-G01 interdit une cible,
CAP-G02 exige une cible et CAP-G03 échoue avec
`CORRECTION_REQUEST_REQUIRED`. Le branchement C-11 est ajoute en 12.8-E par les
methodes distinctes `prepare_correction` et `execute_correction`.

`prepare()` copie exactement le step source, le type de production, le brief,
le format, `ProductionRequest.pedagogical_context`, les contraintes, les
références d’evidence, la cible et les sections attendues. Le contexte canonique
est profondément immutable, non autoritaire et distinct de `resolved_inputs`.
Seuls `resolved_inputs` et `output_contract` sont fournis séparément par le
caller. Le coordinator ne lit ni ne résout aucune donnée.

```text
GenerationPreparationRequest
→ PreparedGenerationCall.preparation_request (objet exact)
→ lineage resolved_inputs/output_contract exacte
→ revalidation avant l'appel outbound
```

`PreparedGenerationCall` est immutable et conserve par identité la préparation
caller-supplied d'origine, mais il n’est pas trusted par sa seule construction.
`execute()` revalide capability, requête canonique, `resolved_inputs`,
`output_contract`, operation, step, type de production, objectif, format,
contexte pédagogique, contraintes, evidence, cible et sections avant tout appel
outbound. Cette défense couvre aussi un objet forgé ayant contourné le
constructeur.

G01/G02 et G03 appliquent désormais le même pattern de snapshot de préparation.
Aucun second mécanisme de lineage caller-supplied n’est conservé.

Le port est appelé au plus une fois. Il n’existe aucun retry, fallback, repair,
replan ou traduction de `GenerationPortError`. Un résultat d’un autre step ou
d’une autre operation est refusé. `evidence_refs_used` doit être unique et former
un sous-ensemble de `ProductionRequest.evidence_refs`; zéro référence utilisée
reste valide. CAP-G02 conserve la même `target_ref` de bout en bout, sans charger
la cible.

Un « validated technical result » désigne exclusivement un résultat dont la
lineage et la cohérence technique ont été vérifiées. Il ne constitue jamais un
`ValidationResult` métier, une approbation, une promotion ou une décision de
gate.

## Frontières maintenues

- aucun `ProductionCandidate`, `CorrectionResult` ou `EvidenceSet` n’est
  construit ;
- aucun `CorrectionRequest` n’est importé dans le coordinator C ;
- aucune recherche, lecture directe, validation, review, promotion ou
  persistance n’est effectuée ;
- aucun runtime, orchestration, provider, modèle, prompt renderer, HTTP, SQL,
  repository ou filesystem n’est introduit ;
- les contrats, la registry et l’access matrix restent inchangés.

## Conséquences

- 12.8-D pourra assembler une `ProductionCandidate` à partir d’une sortie dont
  la lineage technique est inspectable ;
- le chemin C-07 demeure fail-closed pour CAP-G03 ; le mapping C-11 explicite
  utilise le chemin de correction separe ajoute en 12.8-E ;
- les erreurs de coordination déterministes restent distinctes des erreurs
  techniques du port ;
- les statuts `REFUSED`, `PARTIAL` et `INSUFFICIENT_EVIDENCE` restent nominaux et
  ne sont pas transformés en succès.

## Alternatives rejetées

- mapper dynamiquement via la registry : inutile et assimilable à un router ;
- faire confiance à un dataclass préparé : insuffisant contre une entrée forgée ;
- dédupliquer silencieusement les evidence refs : cela masquerait une réponse
  incohérente ;
- retry sur erreur de port : responsabilité différée à la résilience ;
- assembler immédiatement un `ProductionCandidate` : responsabilité de 12.8-D.
