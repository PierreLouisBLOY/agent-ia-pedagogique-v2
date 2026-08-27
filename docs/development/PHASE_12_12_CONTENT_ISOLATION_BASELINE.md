# Baseline Phase 12.12-C — Isolation du contenu et frontière instruction/data

## Périmètre livré

Le lot C part de la baseline B
`fee299c60c23a4cd800af722a4ba475be9031387` sur la branche
`phase12/12-12-security-hardening`.

Il livre :

```text
vocabulaire commun des menaces de contenu
+ LabeledContent / LabeledEvidenceItem
+ InstructionDataBoundaryPolicy
+ ContentSecurityDisposition / ContentSecurityAssessment
+ propagation Evidence -> Generation / Review
+ mapping SecurityEvent pur et minimisé
```

Il n'implémente ni sécurité Tool/Application, ni handoff multi-agent, ni scan
de secrets, ni intégration runtime/recovery globale, ni observabilité.

## Rationalisation des scanners

Les variantes Evidence, Generation et Review de
`INSTRUCTION_LIKE_CONTENT`, `PRIVILEGE_ESCALATION_TEXT`,
`EXFILTRATION_TEXT`, `TOOL_OR_FILE_ACTION_TEXT`, `URL_PRESENT`,
`AUTHORITY_CLAIM_TEXT` et `UPSTREAM_SECURITY_WARNING` utilisent désormais
`ContentThreatSignalCode`.

Evidence conserve exclusivement les codes de qualité/provenance :

```text
DUPLICATE_CORROBORATION
CROSS_SOURCE_DUPLICATE_CONTENT
VERSION_DIVERGENCE
SOURCE_REPORTED_STALE
```

Review conserve ses codes locator, lineage, scope et metadata interdite.
Generation conserve ses décisions de grounding, structure et réparation.

## Contrats et policy

`ContentThreatSignal` contient un code, une ref de contenu et une position
logique ; jamais le texte détecté. `LabeledContent` peut transporter le texte
de travail avec un `ContentTrustLabel` explicite.

`InstructionDataBoundaryPolicy` est pure, déterministe et sans I/O. Elle rend
l'une des dispositions non autoritaires suivantes :

```text
PASS_AS_DATA
ISOLATE_AS_DATA
QUARANTINE
REJECT_CONTENT
ESCALATE_REVIEW
```

Un signal lexical seul mène à `ISOLATE_AS_DATA`, pas à un rejet. Une
contradiction structurelle de rôle ou un pseudo-champ d'autorité Document ou
Evidence mène à `QUARANTINE`. Les pseudo-champs couverts sont ceux de
permission, gate, policy facts, capability, ownership, target, route, handler
et provider définis par la baseline C.

## Provenance et confiance

Les frontières imposent :

```text
USER_INPUT -> USER_INPUT / non-authoritative
DOCUMENT   -> DOCUMENT / DATA
EVIDENCE   -> EVIDENCE / EVIDENCE
GENERATION -> AGENT_OUTPUT ou CORRECTION_OUTPUT / RESULT
REVIEW     -> origine d'output conservée / RESULT
```

La confiance reste exactement `UNTRUSTED` ou
`STRUCTURALLY_VALIDATED`. Aucun code C ne définit `TRUSTED_INTERNAL`, aucune
conversion implicite ne produit `INTERNAL_CONTROL`, et aucun label ne confère
une autorité.

## Intégration Evidence, Generation et Review

L'option B de l'intégration Evidence est retenue : `LabeledEvidenceItem`
enveloppe sans mutation l'`EvidenceItem`, son contenu labellisé et son
assessment. L'excerpt, l'identité, la source et le rôle EVIDENCE sont validés
ensemble.

`GenerationPreparationRequest` et `ReviewPreparationRequest` acceptent les
evidences labellisés dans leur scope canonique. Leurs invariants refusent une
ref étrangère ou une provenance altérée. `GenerationPortResult` et
`ResolvedReviewTarget` portent des labels d'output non fiables conservés dans
les fingerprints et contrôles de lineage.

`EvidenceSecurityAssessment` maintient :

```text
document_instructions_authoritative = False
external_actions_allowed = False
links_followed = False
```

## Anti-faux-positifs pédagogiques

Les impératifs pédagogiques, citations de prompt injection, URLs, extraits de
code et descriptions d'actions peuvent produire un signal, mais restent des
données exploitables. Les tests couvrent notamment la TVA, les instructions
d'un manager, une citation « ignore previous instructions », `open('file.txt')`,
une URL institutionnelle et la proposition d'une action.

Les policies strictes Generation/Review restent la responsabilité explicite de
leurs propriétaires ; la présence lexicale seule n'est pas une preuve
d'attaque et n'accorde jamais une autorité au texte.

## SecurityEvent

Le mapping d'assessment est pur. Les contenus passés ou isolés comme données
ne créent pas d'événement. Les violations structurelles peuvent être mappées
vers `AUTHORITY_SMUGGLING`, `TRUST_BOUNDARY_VIOLATION` ou
`HOSTILE_CONTENT_PROPAGATION` selon leur cause. Aucun événement ne transporte
de texte brut, payload ou secret, et aucun sink/exporter/logger n'existe.

## Frontières préservées

`ToolCallPolicy`, les routers Tool/Application, la délégation et le recovery
ne dépendent pas de la policy C. Aucun provider, réseau, DB, filesystem métier,
subprocess, scanner de secrets ou dépendance runtime n'est introduit.

Les lots suivants restent différés : D Tool/Application, E handoffs agents, F
secrets et limites globales, G intégration runtime/recovery, puis 12.13 pour
l'observabilité.

## Invariants figés

```text
CONTENT != AUTHORITY
UNTRUSTED_CONTENT_NEVER_BECOMES_AUTHORITY
STRUCTURAL_VALIDATION_NEVER_PROMOTES_AUTHORITY
DOCUMENT_INSTRUCTIONS_REMAIN_DATA
EVIDENCE_REMAINS_NON_AUTHORITATIVE
CONTENT_ROLE_AND_ORIGIN_ARE_PRESERVED_ACROSS_BOUNDARIES
LINKS_ARE_NOT_FOLLOWED
TOOL_OR_FILE_TEXT_IS_NOT_EXECUTED
LEXICAL_SIGNAL_ALONE_IS_NOT_AN_ATTACK_DECISION
SECURITY_EVENT_NEVER_CARRIES_RAW_CONTENT
```

## Dépendances et rationalisation

`[project].dependencies` reste vide. Les contrats communs réutilisent
`ContractRef`, `ContentTrustLabel`, `SecurityEvent` et
`freeze_agent_safe_mapping`. Aucun autre type existant ne satisfait
simultanément la sémantique, les invariants, l'autorité et le cycle de vie de
l'isolation de contenu.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
