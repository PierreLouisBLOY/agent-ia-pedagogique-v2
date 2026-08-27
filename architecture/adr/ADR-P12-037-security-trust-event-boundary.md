# ADR-P12-037 — Frontière de provenance, confiance et événement de sécurité

## Statut

Accepté pour la Phase 12.12-B.

## Contexte

Les lots 12.12-C à G doivent durcir plusieurs frontières sans créer une
taxonomie différente pour chaque agent, outil ou adaptateur. La baseline
possède déjà des contrats de workflow, d'erreur, d'evidence et des signaux de
sécurité locaux aux domaines generation, evidence et review. Aucun de ces
types ne constitue cependant un vocabulaire cross-boundary de provenance et de
faits de sécurité.

L'audit des primitives existantes conclut :

- `ContractRef` convient aux références opaques et reste réutilisé ;
- `freeze_agent_safe_mapping` est le propriétaire exact du gel des données
  structurées et du rejet des clés sensibles ou de raisonnement privé ;
- `ContractMeta` impose un statut propriétaire, un acteur et une étape non
  optionnelle ; l'utiliser exigerait un `SecurityEventStatus` artificiel ;
- `WorkflowEvent` décrit le cycle opérationnel, exige un `WorkflowStatus` et
  un `summary` libre ; il ne représente pas un fait de sécurité minimal ;
- `ErrorSeverity` décrit l'urgence d'une erreur opérationnelle avec
  `INFO/WARNING/ERROR/CRITICAL`, alors que la sévérité sécurité requiert
  `LOW/MEDIUM/HIGH/CRITICAL` et peut exister sans erreur runtime ;
- `EvidenceItem.source_kind` est une chaîne spécialisée de provenance evidence
  et ne garantit ni origine cross-boundary ni rôle de contenu ;
- les enums security/threat existants sont des signaux ou assessments locaux,
  et non des types d'événements partagés ;
- les validateurs de reason codes spécialisés ne doivent pas devenir une
  dépendance entre contrats ; leur forme canonique est reprise localement.

Les quatre critères de consolidation — sémantique, invariants, autorité et
cycle de vie identiques — ne sont donc satisfaits par aucun candidat autre que
`ContractRef` et le safe-mapping helper.

## Décision

Le vocabulaire commun vit exclusivement dans
`backend/agent_runtime/contracts/security/`. Aucun concept métier spécialisé
n'est déplacé vers `backend/shared_kernel/`.

### Provenance, rôle et confiance

`SecurityBoundary`, `ContentOrigin` et `ContentRole` sont trois enums fermés et
orthogonaux. `DIAGNOSTIC` est un rôle distinct parce que les erreurs et faits
de sécurité transportent des diagnostics structurés qui ne sont ni un résultat
fonctionnel ni de simples métadonnées.

`ContentTrustClass` ne contient que :

```text
UNTRUSTED
STRUCTURALLY_VALIDATED
```

La classe `TRUSTED_INTERNAL` est volontairement différée. En B, son exposition
permettrait à un caller générique de promouvoir un output externe ou généré par
simple construction. `STRUCTURALLY_VALIDATED` signifie uniquement que forme et
safe-data ont été vérifiées ; cela ne rend jamais le contenu autoritaire.
Aucun helper de promotion n'est créé.

`ContentTrustLabel` est frozen/slotted, sans mapping libre. Il contient
seulement origine, rôle, classe de confiance et `ContractRef` optionnelle. Le
label n'expose ni permission, gate, capability, target, owner, route ou
décision.

### SecurityEvent

`SecurityEvent` reste distinct de `WorkflowEvent`. Le premier est un fait de
sécurité descriptif ; le second représente une transition du workflow. Les
faire hériter l'un de l'autre mélangerait les taxonomies et imposerait au fait
de sécurité un statut opérationnel et un résumé libre.

`ContractMeta` n'est pas réutilisé, car il impose précisément ces éléments. Le
contexte canonique nécessaire est porté explicitement : version du contrat,
run, étape optionnelle, `CorrelationId` et `Instant` UTC. Cette duplication est
limitée aux coordonnées cross-boundary et évite tout faux statut de sécurité.

L'événement est frozen/slotted et data-only. Il contient un ID opaque borné, un
type fermé, une sévérité fermée, la frontière observée, un reason code fermé,
le contexte de corrélation, des refs opaques bornées et uniques, un label
optionnel et des métadonnées sûres.

Le format d'ID reste compatible avec la convention souple de `WorkflowEvent` :
un identifiant opaque, stable pour le producteur, de 1 à 128 caractères sûrs.
B n'impose pas de hash d'un contenu potentiellement secret.

Il n'existe aucun champ libre `summary`, `message`, `description`, `prompt`,
`document` ou `payload`. Les métadonnées réutilisent
`freeze_agent_safe_mapping`, sont limitées à 32 clés racines et refusent aussi
les noms de champs qui inviteraient au transport direct de contenu brut. Cette
interdiction locale complète la minimisation du modèle ; elle ne remplace pas
le futur scanner de valeurs secrètes F et ne crée pas un second framework de
safe mapping.

Les refs réutilisent `ContractRef`, doivent former un tuple unique d'au plus 16
éléments et les refs textuelles doivent rester des identifiants opaques. Un
chemin ou une URL brute n'est pas une ref de sécurité valide.

### Absence d'autorité et de comportement

Le vocabulaire n'expose jamais `ALLOW`, `REQUEST`, `DELEGATE`, `APPROVED` ou
`PROMOTE`. Un événement n'autorise, ne bloque et ne route rien. B ne crée aucun
detector, policy, guard, engine, router ou middleware de sécurité.

Il n'existe aucun logger, sink, exporter, metric, tracing, publisher, bus,
queue, webhook ou event store. Le transport et l'observabilité appartiennent à
12.13.

## Invariants

```text
UNTRUSTED_CONTENT_NEVER_BECOMES_AUTHORITY
CONTENT_ROLE_AND_ORIGIN_ARE_PRESERVED_ACROSS_BOUNDARIES
SECURITY_LABEL_IS_NOT_AUTHORITY
SECURITY_EVENT_IS_NOT_AUTHORITY
SECURITY_EVENT_IS_DATA_ONLY
SECURITY_EVENT_HAS_NO_OBSERVABILITY_BACKEND
TOOL_APPLICATION_AGENT_OUTPUT_REMAINS_NON_AUTHORITATIVE_BY_DEFAULT
```

## Compatibilité et suites

`EvidenceItem` et `WorkflowEvent` ne sont pas modifiés. C définira la
propagation document/evidence et les guards d'injection. D traitera les sorties
tool/Application, E les handoffs agents, F les secrets et limites structurelles,
et G l'intégration runtime. Aucun de ces comportements n'est anticipé en B.

## Conséquences

Les prochains lots disposent d'un vocabulaire partagé, fermé et non
autoritaire. Le coût assumé est une sévérité et un contexte d'événement dédiés,
car les cycles de vie existants ne sont pas sémantiquement exacts.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
