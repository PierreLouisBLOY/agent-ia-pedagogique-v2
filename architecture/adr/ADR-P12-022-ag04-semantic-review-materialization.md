# ADR-P12-022 — Agent AG-04 et matérialisation de semantic review

## Statut

Accepté pour la Phase 12.9-D.

## Contexte

Les lots B et C fournissent la frontière provider-neutral et la coordination
déterministe de review. Ils retournent volontairement un `ReviewPortResult`
technique qui n'est ni un `Finding` ni un `ReviewResult` C-10. Le lot D doit
exposer CAP-V01 `semantic_review` et matérialiser C-10 sans anticiper
l'agrégation CAP-V02, la correction C-11 ou une décision de validation.

## Décision

`ReviewerAgent` expose exactement deux méthodes publiques :

- `semantic_review()`, bornée à `CAP-V01`, qui délègue successivement à
  `ReviewCoordinator.prepare()` puis `ReviewCoordinator.execute()` ;
- `build_review_result()`, qui revalide une
  `ReviewResultMaterializationRequest` et construit les contrats canoniques
  existants `Finding` et `ReviewResult`.

```text
ReviewRequest C-09
      |
      v
ReviewerAgent.semantic_review()
      |
      v
ReviewCoordinator
      |
      v
ReviewPort [1 call]
      |
      v
ReviewPortResult technique
      |
      v
ReviewResultMaterializationRequest
      |
      v
ReviewerAgent.build_review_result()
      |
      +--> Finding*
      |
      v
ReviewResult C-10
```

CAP-V02 demeure utilisable seulement par la couche de coordination C. L'agent D
n'expose aucun `assess_findings` et le code de matérialisation ne contient aucun
mapping CAP-V02.

## Schéma technique fermé CAP-V01

Chaque élément de `technical_findings` possède exactement :

```text
finding_id, dimension, severity, description, target_locator,
rationale, correction_required, evidence_refs, confidence, suggested_action
```

`dimension` et `severity` acceptent uniquement les valeurs exactes des enums
canoniques `ReviewDimension` et `FindingSeverity`. Les identifiants et textes
sont non vides, les mappings restent agent-safe et profondément immutables, et
les identifiants de findings sont uniques. Aucune dimension ou sévérité
dynamique n'est créée.

Le `structured_payload` possède exactement :

```text
overall_assessment, correction_required, coverage, confidence
```

`overall_assessment` est converti depuis une valeur exacte de
`OverallAssessment`. D matérialise l'assessment déclaré par CAP-V01 ; il ne le
calcule, ne le pondère et ne l'agrège pas. Les limitations et warnings viennent
des champs techniques dédiés, et `execution_metadata` n'est jamais copié dans
C-10.

## Status et metadata

Le mapping fermé est :

| Statut technique | Statut C-10 | Matérialisable |
| --- | --- | --- |
| `SUCCEEDED` | `COMPLETED` | oui |
| `PARTIAL` | `INCOMPLETE` | oui |
| `REFUSED` | aucun | non |
| `FAILED` | aucun | non |

Le `ContractMeta[ReviewStatus]` et le `review_id` sont fournis par le caller. La
metadata doit conserver le schema, le run, le step et la corrélation C-09, et
identifier AG-04 comme acteur. Le résultat technique ne peut imposer aucune
identité canonique ni statut.

## Binding, scope et cohérences

La matérialisation revalide le Prepared complet, CAP-V01, `SEMANTIC_REVIEW`, la
cible versionnée, le step, le statut, l'unicité des evidence utilisées et leur
inclusion dans C-09. Chaque finding est borné aux dimensions demandées et à
l'intersection entre les evidence C-09 et les evidence déclarées utilisées par
le résultat. La coverage est unique, incluse dans les dimensions demandées et
contient toutes les dimensions des findings.

Seuls les invariants structurels déjà portés par C-10 sont appliqués : une
correction exigée par un finding ou par `CORRECTION_REQUIRED` doit être reflétée
par le résultat, `ACCEPTABLE` interdit toute correction requise, et
`INCOMPLETE` ne peut pas être `ACCEPTABLE`. Aucune règle `BLOCKING`, `MAJOR`,
score, seuil ou consensus n'est ajoutée.

## Frontières d'autorité

D ne crée ni `CorrectionRequest`, ni `CorrectionResult`, ni gate, validation,
promotion, persistence ou policy blocking. Il ne charge pas la cible, ne cherche
pas d'evidence et n'utilise aucun provider, SDK, réseau, SQL, vector store,
filesystem métier, runtime ou orchestration. Il n'introduit aucun retry,
fallback ou replan.

La validation géométrique ou sémantique de `target_locator` dans le contenu
reste différée. La construction de C-10 ne signifie ni approbation ni promotion.

## Conséquences

- CAP-V01 produit un C-10 canonique dont la lineage est inspectable ;
- les sorties techniques mal formées ou hors scope échouent avec des erreurs
  fermées et agent-safe ;
- l'identité canonique reste sous contrôle du caller ;
- aucune abstraction commune avec le materializer génération n'est retenue :
  les modèles, scopes et invariants diffèrent.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```

## Responsabilités différées

- 12.9-E : CAP-V02, agrégation de findings et handoff de correction ;
- 12.9-F : sécurité complète et validation locator/evidence ;
- 12.9-G : intégration workflows et fitness ;
- 12.9-H : audit cumulatif et clôture.
