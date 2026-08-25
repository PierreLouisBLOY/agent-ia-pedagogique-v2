# ADR-P12-021 — Préparation et coordination déterministes AG-04

## Statut

Accepté pour la Phase 12.9-C.

## Contexte

La frontière provider-neutral 12.9-B définit `ReviewPortRequest`,
`ReviewPortResult` et l'unique `ReviewPort`, sans relier C-09 `ReviewRequest` à
une opération technique. Cette liaison doit préserver la cible et le contexte
canonique, empêcher toute falsification du Prepared et borner l'usage des
evidence, sans introduire l'agent, un provider ou C-10.

## Décision

`ReviewPreparationRequest` capture la capability, le `ReviewRequest` canonique,
une `ResolvedReviewTarget` caller-supplied, les `resolved_inputs` et
`output_contract`. `PreparedReviewCall` conserve exactement cet objet de
préparation, la capability, la requête canonique, la cible et la requête du port.
Ces modèles sont frozen, slotted et profondément immutables.

Le mapping local fermé est :

```text
CAP-V01 → ReviewOperation.SEMANTIC_REVIEW
CAP-V02 → ReviewOperation.ASSESS_FINDINGS
```

Ce mapping construit uniquement l'opération outbound. Il ne consulte pas la
registry, ne route aucun agent et n'accorde aucune permission. Toute autre
capability échoue avec `UNSUPPORTED_CAPABILITY`.

La cible résolue porte le même `ObjectVersionRef` que C-09 et son contenu et/ou
payload déjà résolu. Le coordinator ne charge pas la production. Le step, la
capability, la cible, les dimensions, critères, evidence et budget viennent
exactement du snapshot. `severity_policy`, `context_slice` et
`independence_requirements` restent trois sous-contextes explicites et distincts
de `coverage_context`, sans perte ni fusion sémantique. Pour CAP-V02, les
findings déjà résolus restent opaques dans `resolved_inputs`.

```text
ReviewRequest C-09
+ target déjà résolue
+ resolved inputs
+ output contract
        |
        v
ReviewPreparationRequest
        |
        v
ReviewCoordinator.prepare()
        |
        v
PreparedReviewCall
        |
        v
ReviewCoordinator.execute()
        |
        v
ReviewPort.review()  [1 appel]
        |
        v
ReviewPortResult technique
        |
        v
revalidation
        |
        v
retour technique non canonique
```

Avant l'appel, `execute()` revalide complètement le Prepared contre la
préparation originale : capability, C-09, cible, représentation, step,
opération, dimensions, critères, evidence, les trois sous-contextes, budget,
inputs et contrat de sortie. Après l'unique appel, il exige le type exact
`ReviewPortResult`, le même step et la même opération, des références utilisées
uniques et incluses dans le scope C-09.

Il n'existe aucun retry, fallback, boucle ou traduction de `ReviewPortError`.
Les erreurs de coordination sont fermées et leurs raisons sûres n'exposent ni
contenu cible ni evidence.

## Frontières d'autorité

Le coordinator ne construit ni `Finding`, ni `ReviewResult`, ni
`CorrectionRequest`. Il ne décide ni correction, validation, promotion ou gate.
Il ne recherche aucune evidence, ne résout aucune référence, ne persiste rien et
n'importe ni runtime, orchestration, provider, SDK, HTTP, SQL, vector store ou
filesystem métier. La registry, l'access matrix et les workflows restent
inchangés.

Le `ReviewPortResult` retourné demeure une sortie technique non canonique. Sa
revalidation de lineage ne constitue pas une approbation métier.

## Conséquences

- les appels V01 et V02 ont un binding déterministe et inspectable ;
- une falsification échoue avant le port et une dérive du résultat échoue après
  un unique appel ;
- les inputs V02 restent disponibles pour la future agrégation sans créer un
  contrat parallèle ;
- la similarité avec `GenerationCoordinator` ne prouve pas une équivalence
  sémantique et ne justifie pas une abstraction commune.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```

## Responsabilités différées

- 12.9-D : `ReviewerAgent` et matérialisation canonique C-10 ;
- 12.9-E : assessment de findings et handoff de correction ;
- 12.9-F : sécurité complète et lineage locator/evidence ;
- 12.9-G : intégration workflows et fitness ;
- 12.9-H : audit cumulatif et clôture.
