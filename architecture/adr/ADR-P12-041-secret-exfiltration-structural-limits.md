# ADR-P12-041 — Secrets, exfiltration et limites structurelles

## Statut

Accepté pour la Phase 12.12-F.

## Contexte

Les lots B à E ont fermé les types d'événements, isolé les instructions dans le
contenu, interdit les clés structurelles d'autorité et conservé la provenance
aux frontières Tool, Application et inter-agent. Le gel canonique des mappings
refuse aussi les noms de clés manifestement privés. Il restait néanmoins quatre
canaux transverses : une valeur de credential placée sous une clé neutre, le
texte libre d'une erreur, la metadata d'un événement, et une structure assez
grande ou profonde pour épuiser la frontière avant son refus.

F doit fermer ces canaux sans construire de gestionnaire de secrets, sans
modifier l'autorité C/D/E, sans intégrer le runtime/recovery global de G et sans
introduire d'observabilité ou de calibration fournisseur.

## Décision

`freeze_safe_mapping` reste l'unique propriétaire du gel récursif, du rejet des
types non transportables et du vocabulaire de clés privées. Un validateur
générique, pur et déterministe est exécuté avant le gel. Il borne profondeur,
cardinalité, chaînes et nombre total de nœuds, puis classe seulement des formes
de valeurs très caractéristiques. Il ne conserve ni match brut, ni extrait, ni
fingerprint.

`SensitiveValuePolicy`, sous `backend/agent_runtime/security/`, est l'unique
façade sécurité F. Elle retourne une évaluation composée exclusivement d'une
classe et d'une position logique normalisée. Elle ne décide aucune permission,
ne journalise rien, ne stocke rien et n'appelle aucun port.

```text
mapping key safety       -> freeze_safe_mapping / freeze_agent_safe_mapping
content threat signal C  -> InstructionDataBoundaryPolicy
authority key safety D   -> structural_keys.py + boundary owners
secret-like value F      -> SensitiveValuePolicy
resource bound F         -> StructuredDataLimits
```

Ces invariants sont complémentaires et ne sont pas fusionnés.

## Classification et isolation

Les classes fermées sont `SAFE_VALUE`, `CREDENTIAL_LIKE`,
`AUTH_TOKEN_LIKE`, `PRIVATE_KEY_LIKE`, `CONNECTION_SECRET_LIKE` et
`PRIVATE_PATH_LIKE`. Les signaux sont limités aux marqueurs de clé privée,
formes Bearer/JWT caractéristiques, préfixes génériques connus, URL de
connexion avec secret et chemins absolus/privés.

Les chaînes aléatoires ordinaires ne sont pas classées. SHA-256, UUID,
`ContractRef`, checksum, version, fingerprint d'idempotence et texte
pédagogique ou juridique parlant de mots de passe/API keys restent acceptés.
Les tests assemblent uniquement des formes synthétiques et non utilisables.

Une détection lève `SensitiveValueRejected`. L'exception ne contient que la
classe et la position logique sûre. Les valeurs ne sont ni copiées dans
`SecurityEvent`, ni placées dans les erreurs, ni transformées en fingerprint.

## Erreurs et événements

`ErrorEnvelope.message` est limité à 1 024 caractères et inspecté par valeur.
`details` utilise un profil plus strict : profondeur 8, 64 clés par mapping, 64
éléments par séquence, chaînes de 2 048 caractères et 1 024 nœuds. Les refs
associées restent opaques, sont inspectées et sont limitées à 16.

`SecurityEvent` conserve sa forme minimale B. Sa metadata applique profondeur
8, 32 clés, 64 éléments, chaînes de 512 caractères et 512 nœuds ; ses 32 clés
top-level et ses 16 refs historiques restent inchangées. Identifiants et refs
sont bornés et contrôlés. Une valeur sensible sous `note` est donc rejetée
aussi sûrement qu'une clé brute interdite.

Les mappings purs réutilisent les types B :

```text
valeur sensible seule                 -> SECRET_EXPOSURE
demande d'exfiltration + valeur       -> SECRET_EXFILTRATION_ATTEMPT
limite structurelle dépassée          -> INPUT_LIMIT_EXCEEDED
confusion de frontière existante      -> TRUST_BOUNDARY_VIOLATION
```

L'événement ne contient que classification, position logique ou code de
limite. Le signal lexical `EXFILTRATION_TEXT` de C et la présence effective
d'une valeur sensible de F restent deux constats distincts.

## Frontières Tool, Application et Agent

La fonction D `assess_structured_boundary_content` compose désormais F avant
la classification structurelle et l'isolation textuelle. Les routers Tool et
Application et la boundary E conservent leurs responsabilités et leur
provenance. En complément, les contrats refusent tôt les valeurs sensibles :

- output/metrics/error/artifact refs de `ToolCallResult` ;
- data/validation/errors/side effects/refs de `ApplicationOutcome` et
  `UseCaseResult` ;
- payloads y compris dataclasses, warnings, metrics, erreurs, stop reason et
  refs de `AgentResult` ;
- contextes, contraintes, traces et Evidence refs de délégation ;
- contenu labellisé, provenance et locators Evidence.

Un chemin sandbox logique relatif reste sous le propriétaire sandbox. Un
chemin Windows, POSIX, UNC ou home privé ne peut pas être copié dans un contrat
agent-safe, un événement, une erreur ou une ref d'artifact.

## Profil de limites

Le profil générique est : profondeur 16, 256 clés par mapping, 512 éléments
par séquence, chaîne de 65 536 caractères et 4 096 nœuds au total. Le parcours
est itératif ; les cycles et bombes d'imbrication échouent avec une erreur
bornée avant récursion Python ou propagation externe.

Les limites spécialisées existantes ne sont pas absorbées : 24 steps/run et
profondeur de délégation 2 relèvent de la runtime policy ; 12 éléments par set
Evidence et extraits de 4 000 caractères relèvent d'Evidence ; 25/50 MiB, 20
fichiers et les chemins relèvent du sandbox ; 65 536 octets de fingerprint
relèvent du snapshot/recovery. Leurs unités, owners et effets sont différents.

## Recovery et infrastructure

`RetryFailureFacts`, checkpoints, snapshots et ledger sont audités et restent
des projections fermées ou des refs typées. Aucun module recovery et aucune
sémantique retry/replay/reconciliation/circuit n'est modifié.

Aucun `SecretStore`, Vault, KMS, credential loader, SDK fournisseur, client
réseau, DLP externe, logger, sink ou exporter n'est créé. La protection porte
sur les contrats et frontières, pas sur une infrastructure de secrets.

## Invariants

```text
FREEZE_SAFE_MAPPING_REMAINS_CANONICAL_FREEZE_AND_KEY_OWNER
SENSITIVE_VALUE_POLICY_IS_THE_UNIQUE_F_SECURITY_FACADE
RAW_VALUE_MUST_NOT_PROPAGATE
ERROR_ENVELOPE_AND_SECURITY_EVENT_ARE_VALUE_SAFE_AND_BOUNDED
TOOL_APPLICATION_AGENT_PROVENANCE_REMAINS_UNCHANGED
EXFILTRATION_REQUEST_AND_SECRET_VALUE_HAVE_DISTINCT_OWNERS
STRUCTURAL_BOMBS_FAIL_CLOSED
RECOVERY_SEMANTICS_REMAIN_UNCHANGED
NO_SECRET_INFRASTRUCTURE_OR_OBSERVABILITY
```

## Portée différée et rationalisation

L'intégration globale runtime/recovery reste en 12.12-G. Logging, tracing,
metrics et sinks restent en 12.13. Les seuils empiriques de modèles ou
fournisseurs restent en 12.16.

Les invariants de clés, valeurs, menaces textuelles, autorité et ressources ne
partagent ni la même sémantique ni le même owner. Au-delà de la validation
générique appelée par le gel canonique, aucune fusion supplémentaire n'est
sûre.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
