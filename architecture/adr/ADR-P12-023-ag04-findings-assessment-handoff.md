# ADR-P12-023 — Assessment des findings AG-04 et handoff AG-01

## Statut

Accepté pour la Phase 12.9-E.

## Contexte

Le lot D matérialise CAP-V01 en C-10 `ReviewResult`. La capability canonique
CAP-V02 `assess_findings`, possédée par AG-04, doit maintenant évaluer les
findings existants sans créer de nouveaux findings, sans transformer
`OverallAssessment` en statut métier et sans usurper la décision d'AG-01.

Un finding de sévérité `BLOCKING` est un signal bloquant pour la promotion, mais
AG-04 ne possède ni `PromotionPolicy` ni autorité de gate. Lorsqu'une correction
est requise, AG-01 reste seul responsable de la décision ultérieure et de
l'éventuelle construction de C-11 vers AG-03.

## Décision

`FindingsAssessmentRequest` lie exactement :

- `CAP-V02` ;
- le C-09 `ReviewRequest` source ;
- le C-10 `ReviewResult` source ;
- la cible versionnée déjà résolue ;
- un `review_ref` caller-supplied ;
- les inputs additionnels caller-supplied ;
- un contrat de sortie technique fermé.

Le `ReviewerAgent.assess_findings()` construit un
`ReviewPreparationRequest` CAP-V02, puis réutilise le `ReviewCoordinator` et
l'unique `ReviewPort`. Il n'existe aucun nouveau port, coordinator ou mécanisme
d'exécution.

```text
ReviewResult C-10
      |
      v
ReviewerAgent.assess_findings()
      |
      v
ReviewCoordinator / ReviewPort CAP-V02
      |
      v
technical assessment
      |
      +--> deterministic aggregate recheck
      |
      v
ReviewAssessmentSignal
      |
      +--> CorrectionHandoffSignal (si requis)
      |
      v
AG-01 — décision ultérieure
      |
      +--> éventuellement C-11 vers AG-03
```

## Snapshot provider-neutral

Le port reçoit un snapshot immutable de chaque `Finding` C-10 avec uniquement
ses dix champs publics : identifiant, dimension, sévérité, description, locator,
rationale public, flag de correction, evidence, confiance et action suggérée.
Le snapshot inclut aussi la référence, l'identité, la cible et le résumé public
du C-10 source, ainsi que les inputs additionnels dans un namespace distinct.

Aucune chaîne de pensée, note interne, metadata d'autorité ou donnée AG-03 n'est
transmise. Les inputs additionnels caller-supplied sont eux aussi filtrés contre
le vocabulaire d'autorité. Le Prepared est comparé exactement à ce snapshot
avant l'appel.

## Schéma technique fermé CAP-V02

`technical_findings` doit être vide : CAP-V02 n'invente aucun finding.

Le `structured_payload` contient exactement :

```text
assessed_finding_ids
blocking_finding_ids
correction_finding_ids
overall_assessment
correction_required
confidence
```

Les trois tuples d'identifiants doivent correspondre exactement, dans l'ordre
source, aux agrégats recalculés depuis C-10 :

```text
all_finding_ids = tous les IDs C-10
blocking_finding_ids = severity == BLOCKING
correction_finding_ids = correction_required == true UNION blocking
```

Le provider ne peut donc ni masquer un blocking ou une correction explicite, ni
ajouter un finding, ni requalifier une sévérité.

## Assessment et signal de blocking

`ReviewAssessmentSignal` est frozen, slotted et non canonique. Il conserve la
lineage, les agrégats exacts, l'assessment déclaré, le statut technique, les
evidence utilisées, la confiance et les limitations/warnings.

`promotion_blocked_by_review` est recalculé par :

```text
bool(blocking_finding_ids)
```

Ce booléen transmet P11-REV-14 à AG-01/Application ; il ne modifie aucun statut,
n'ouvre aucune gate et ne constitue pas une décision de promotion.

Les invariants fermés interdisent `ACCEPTABLE` en présence de correction ou de
blocking, et interdisent également `ACCEPTABLE_WITH_RESERVATIONS` en présence de
blocking. Un résultat technique `PARTIAL` doit déclarer `INCOMPLETE` et conserve
tous les blocking connus. `REFUSED` et `FAILED` ne produisent aucun signal.
Aucun score, vote, consensus ou statut PASS/FAIL n'est introduit.

## Handoff AG-01

`CorrectionHandoffSignal` est construit uniquement lorsque
`correction_finding_ids` n'est pas vide. Il cible explicitement AG-01 et contient
les IDs exacts, les blocking, l'union ordonnée des evidence attachées aux
findings concernés et leurs actions suggérées non contraignantes.

Le handoff ne possède ni capability CAP-G03, handler, tool, permission, gate,
statut promoted/validated ou mutation de cible. Il ne remplace pas C-11 et ne
convertit pas les actions en `allowed_changes`, `forbidden_changes`,
`preserve_constraints` ou `expected_delta`.

## Frontières d'autorité

AG-04 n'appelle ni AG-03 ni CAP-G03, ne construit aucun `CorrectionRequest`, ne
valide pas canoniquement et ne décide aucune promotion. Aucun runtime,
orchestration, provider, réseau, SQL, vector store, filesystem métier ou
persistence n'est ajouté. Il n'existe aucun retry, fallback ou replan.

La validation géométrique des locators, le scanner hostile complet et le
hardening global evidence/lineage restent différés à F.

## Rationalisation

Les snapshots CAP-V01 et CAP-V02 portent des sémantiques différentes : le
premier parse une sortie provider en C-10, le second sérialise un C-10 existant
pour en recalculer les agrégats. Une abstraction commune déplacerait leurs
frontières d'autorité et n'est pas sûre.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```

## Responsabilités différées

- 12.9-F : sécurité complète, locator et lineage evidence renforcés ;
- 12.9-G : intégration workflows et décisions AG-01 ;
- 12.9-H : audit cumulatif et clôture.
