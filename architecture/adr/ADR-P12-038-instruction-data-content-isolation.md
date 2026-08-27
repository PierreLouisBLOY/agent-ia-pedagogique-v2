# ADR-P12-038 — Frontière instruction/data et isolation du contenu

## Statut

Accepté pour la Phase 12.12-C.

## Contexte

La baseline 12.12-B a introduit un vocabulaire commun de provenance, de
confiance et d'événements sans aucun comportement de détection. Les agents
Evidence, Generation et Review possédaient déjà des scanners partiellement
redondants. Ils associaient parfois une même forme lexicale à trois enums
distincts et pouvaient ainsi faire diverger le sens d'une menace identique.

L'audit produit la matrice suivante :

| Code existant | Sémantique | Menace générique | Propriétaire final | Action |
| --- | --- | --- | --- | --- |
| instruction-like | texte de forme impérative ou d'override | oui | commun | consolider |
| privilege escalation | revendication de privilège | oui | commun | consolider |
| exfiltration | demande d'extraction ou d'envoi | oui | commun | consolider |
| tool/file action | texte décrivant une action tool/fichier | oui | commun | consolider |
| URL | URL présente dans le contenu | oui | commun | consolider |
| authority claim | revendication d'autorité dans le texte | oui | commun | consolider |
| upstream warning | avertissement de sécurité déjà établi | oui | commun | consolider |
| duplicate corroboration | qualité de corroboration evidence | non | Evidence | conserver |
| cross-source duplicate | duplication inter-source | non | Evidence | conserver |
| version divergence / stale | qualité et fraîcheur de source | non | Evidence | conserver |
| locator / lineage / scope | intégrité d'un résultat Review | non | Review | conserver |
| grounding / structure / repair | qualité de génération | non | Generation | conserver |

Les quatre critères de consolidation — sémantique, invariants, autorité et
cycle de vie identiques — sont réunis uniquement pour les menaces génériques.
Les dispositions et guards de domaine ne sont pas fusionnés.

## Décision

### Vocabulaire et contrats communs

`ContentThreatSignalCode`, `ContentThreatSignal`, `LabeledContent`,
`ContentSecurityDisposition` et `ContentSecurityAssessment` vivent dans
`backend/agent_runtime/contracts/security/`. Le signal référence un contenu et
une position logique sans copier de texte brut. Les modèles sont frozen et
slotted.

Le vocabulaire commun contient exactement les signaux confirmés par l'audit,
plus `ROLE_CONFUSION` pour une contradiction structurelle entre frontière et
rôle. Il ne remplace ni les codes Evidence de qualité/provenance, ni les codes
Review de locator/lineage/scope, ni les codes Generation de qualité.

`ContentSecurityDisposition` décrit uniquement le traitement d'un contenu :

```text
PASS_AS_DATA
ISOLATE_AS_DATA
QUARANTINE
REJECT_CONTENT
ESCALATE_REVIEW
```

Ces valeurs ne constituent jamais une permission, une gate ou une délégation.

### Policy pure et séparation instruction/data

`InstructionDataBoundaryPolicy` est l'unique propriétaire commun de
l'isolation. Elle reçoit un `LabeledContent`, un contexte structurel et des
signaux, puis retourne un assessment data-only. Elle n'appelle ni LLM, tool,
Application, provider, réseau, base ou filesystem métier.

Le contenu reste non autoritaire quelle que soit sa formulation :

```text
CONTENT != AUTHORITY
```

Un signal lexical isolé produit au plus une isolation comme donnée. Une
contradiction de rôle ou un pseudo-champ structurel d'autorité sur les
frontières Document/Evidence produit une quarantaine. Les clés contrôlées sont
permission, permission_scope, gate, gate_decision, policy_facts, capability,
capability_id, owner, target, route, handler et provider. Cette liste est
locale à C et ne traite aucun payload Tool/Application.

### Provenance et monotonie de confiance

Le texte utilisateur reste `USER_INPUT` et ne dépasse jamais
`STRUCTURALLY_VALIDATED`. Un document est `DOCUMENT/DATA`. Un evidence est
`EVIDENCE/EVIDENCE`. La classe de confiance reste strictement limitée à :

```text
UNTRUSTED
STRUCTURALLY_VALIDATED
```

`TRUSTED_INTERNAL` et toute fonction de promotion restent absents. Une
validation structurelle ne confère ni permission ni autorité d'exécution.

L'intégration Evidence adopte l'option B : `LabeledEvidenceItem` enveloppe
l'`EvidenceItem` canonique, son `LabeledContent` et son assessment. Ses
invariants imposent la conservation exacte de l'excerpt, de l'identité et de
la provenance. Les prepared inputs Generation et Review transportent ces
wrappers sans augmenter la confiance. Les résultats Generation et les cibles
Review portent des labels d'output `UNTRUSTED` et conservent leur origine.

### Propriétaires de domaine

`GenerationOutputGuard` demeure propriétaire du grounding, de la structure et
des réparations de génération. `ReviewSecurityGuard` demeure propriétaire des
locators, lineage, scope et dispositions Review. Ils consomment le vocabulaire
commun sans céder leur autorité à la policy d'isolation.

Les heuristiques lexicales Review sont non bloquantes par défaut. Une policy
Review explicite peut conserver un mode strict. Les formulations pédagogiques,
citations, URLs et exemples de code restent donc exploitables comme données et
ne provoquent pas automatiquement un rejet.

### Mapping SecurityEvent

Le mapping pur ne crée aucun événement pour `PASS_AS_DATA` ou
`ISOLATE_AS_DATA`. Une confusion de rôle peut produire
`TRUST_BOUNDARY_VIOLATION`, un pseudo-champ d'autorité
`AUTHORITY_SMUGGLING`, et une propagation hostile explicitement escaladée
`HOSTILE_CONTENT_PROPAGATION`. L'événement ne contient que labels, refs et
reason codes ; aucun texte brut, payload, secret, sink ou logger n'est ajouté.

## Invariants

```text
CONTENT_NEVER_CONFERS_CONTROL_AUTHORITY
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

## Portée différée

C ne modifie pas `ToolCallPolicy`, `ToolRouter`, `UseCaseRouter`,
`ApplicationInboundPort`, la délégation, le recovery ou le runtime global.
La sécurité Tool/Application reste en D, les handoffs multi-agent en E, le
scan de valeurs secrètes et les limites globales en F, l'intégration runtime en
G et l'observabilité en 12.13.

## Conséquences

Les menaces réellement identiques ont désormais un vocabulaire unique, tandis
que les décisions de qualité et d'intégrité restent chez leurs propriétaires.
Le coût assumé est un wrapper Evidence explicite et des labels propagés aux
frontières ; ce coût rend la provenance vérifiable sans modifier
`EvidenceItem` ni créer d'autorité textuelle.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
