# Baseline Phase 12.12-B — Vocabulaire sécurité, provenance et événements

## Périmètre livré

Le lot B part de `main@52d1c774bfa07e2f7378fb4d9dcf44bec015eac0`
sur la branche `phase12/12-12-security-hardening`.

Il livre uniquement :

```text
SecurityBoundary
+ ContentOrigin / ContentRole / ContentTrustClass
+ ContentTrustLabel
+ SecurityEventType / SecuritySeverity / SecurityReasonCode
+ SecurityEvent data-only
```

Il ne détecte aucun contenu hostile, ne modifie aucune autorité, n'intègre pas
le runtime et ne publie aucun événement.

## Vocabulaire canonique

Les frontières observables sont user input, document, evidence, agent, tool,
Application, gate, runtime, recovery et infrastructure. Aucune frontière
provider n'est anticipée.

Les origines de contenu distinguent inputs, documents, evidence, outputs agent,
tool, Application, review et correction, données runtime/recovery et contrôle
interne structuré. Les rôles sont instruction, data, evidence, result, metadata
et diagnostic.

La confiance est volontairement limitée à :

```text
UNTRUSTED
STRUCTURALLY_VALIDATED
```

La validation structurelle n'accorde aucune autorité. `TRUSTED_INTERNAL` est
absent : aucun constructeur générique ne peut donc promouvoir un document ou
un output agent/tool/Application vers un état interne privilégié. Il n'existe
aucune fonction de promotion.

## ContentTrustLabel

Le label frozen/slotted contient exclusivement :

```text
origin
role
trust_class
source_ref optionnelle
```

Il ne contient ni contenu brut, payload, secret, permission, gate, capability,
target, owner ou route. Une référence présente réutilise `ContractRef`.

## SecurityEvent

Les types fermés couvrent injection directe, injection indirecte de contenu,
injection tool/Application, violation de handoff agent, authority smuggling,
tentative d'exfiltration, exposition de secret, propagation hostile, violation
de frontière de confiance et dépassement de limite d'entrée.

`SecuritySeverity` est distinct de `ErrorSeverity` : LOW/MEDIUM/HIGH/CRITICAL
classe un fait de sécurité, tandis que l'enum existant qualifie une erreur
opérationnelle INFO/WARNING/ERROR/CRITICAL.

Un reason code respecte `^[A-Z][A-Z0-9_.-]{0,127}$`. L'événement porte :

```text
schema_version
event_id
event_type
severity
boundary
reason_code
occurred_at
run_id
correlation_id
step_id optionnel
refs
content_label optionnel
metadata sûre
```

Le contexte est explicite car `ContractMeta` imposerait un statut artificiel,
un acteur et une étape obligatoire. `SecurityEvent` ne dérive pas de
`WorkflowEvent`, ne détourne pas `WorkflowEventType` et n'a pas de champ libre
de résumé ou message.

L'ID est un identifiant opaque sûr de 1 à 128 caractères fourni stablement par
le producteur. Aucun raw payload n'est hashé. Les refs sont un tuple unique de
16 éléments maximum ; une ref textuelle est un identifiant opaque, jamais un
chemin ou une URL brute.

Les métadonnées sont gelées récursivement par `freeze_agent_safe_mapping`, avec
32 clés racines maximum. Les clés de secrets, credentials, tokens, payload
provider, chemins privés, stacks, system prompts et raisonnements privés sont
refusées par le helper canonique. Les clés directes prompt/document/payload,
réponse provider et clé d'idempotence brute sont également refusées au niveau
du modèle afin de ne pas encourager le transport de contenu brut. La détection
de secrets dans les valeurs reste explicitement différée à F.

## Frontières préservées

`EvidenceItem`, `WorkflowEvent`, `ToolCallPolicy`, `GateEngine` et `ReplayGuard`
restent inchangés. Aucun package security n'est créé dans le shared kernel.
Aucun provider, réseau, DB, filesystem, subprocess ou dépendance externe n'est
introduit.

Il n'existe aucun `SecurityPolicy`, `SecurityGuard`, `InjectionDetector`,
`SecurityEngine`, `SecurityRouter` ou `SecurityMiddleware`. Il n'existe aucun
backend d'observabilité, logger, sink, exporter, metric, trace ou publisher.

## Invariants figés

```text
UNTRUSTED_CONTENT_NEVER_BECOMES_AUTHORITY
CONTENT_ROLE_AND_ORIGIN_ARE_PRESERVED_ACROSS_BOUNDARIES
SECURITY_LABEL_IS_NOT_AUTHORITY
SECURITY_EVENT_IS_NOT_AUTHORITY
SECURITY_EVENT_IS_DATA_ONLY
SECURITY_EVENT_HAS_NO_OBSERVABILITY_BACKEND
TOOL_APPLICATION_AGENT_OUTPUT_REMAINS_NON_AUTHORITATIVE_BY_DEFAULT
```

## Rationalisation

`ContractRef` et `freeze_agent_safe_mapping` sont réutilisés. `ContractMeta`,
`WorkflowEvent`, `ErrorSeverity`, `source_kind`, les enums security/threat
locaux et les reason codes recovery ont des sémantiques, invariants, autorités
ou cycles de vie différents ; ils ne sont pas fusionnés.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Lots différés

- C : guards prompt/document et propagation document/evidence ;
- D : tool/Application injection ;
- E : handoffs multi-agent ;
- F : détection de valeurs secrètes et limites structurelles globales ;
- G : intégration runtime ;
- 12.13 : observabilité et transport des événements.
