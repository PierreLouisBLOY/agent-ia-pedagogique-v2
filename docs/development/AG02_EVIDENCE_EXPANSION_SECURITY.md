# AG-02 — sécurité evidence et expansion bornée

## Principe de confiance

Tout document ou excerpt d'evidence est une donnée non fiable pour les
instructions. Un texte comme « ignore les règles », « autorise CAP-A02 »,
« lis ce fichier » ou une URL ne crée aucune autorité et ne déclenche aucune
action. `EvidenceSecurityScanner` détecte seulement des indicateurs structurés.

Le scanner est pur : il ne lit aucun fichier, ne parse ou suit aucune URL,
n'appelle aucun port et ne supprime aucun `EvidenceItem`. Les flags de
`EvidenceSecurityAssessment` imposent toujours :

- `document_instructions_authoritative = False` ;
- `external_actions_allowed = False` ;
- `links_followed = False`.

Il ne produit aucun verdict `SAFE`, `TRUSTED` ou `MALICIOUS` et ne modifie ni
source policy, ni `PermissionScope`, ni capability, ni gate.

## Patterns fermés FR/EN

Les comparaisons sont insensibles à la casse et utilisent des sous-chaînes
fermées, sans modèle statistique :

| Code | Indicateurs principaux |
| --- | --- |
| `INSTRUCTION_LIKE_CONTENT` | `ignore previous/all instructions`, `ignore les consignes/règles`, `system prompt`, `developer message` |
| `PRIVILEGE_ESCALATION_TEXT` | `you are admin`, `je suis administrateur`, `authorize/autorise CAP-`, `grant/accorde la permission` |
| `EXFILTRATION_TEXT` | `reveal/révèle secret`, `show api key`, `send/envoie les secrets` |
| `TOOL_OR_FILE_ACTION_TEXT` | `call/appelle cet outil`, `read/lis ce fichier`, `open/ouvre ce chemin` |
| `URL_PRESENT` | présence littérale de `http://` ou `https://` |

Un match conserve le texte inchangé. Il prouve seulement la présence d'un
indicateur, pas l'intention ou la réalité d'une attaque.

## Poisoning, provenance et corroboration

Les avertissements `SECURITY_WARNING:<CODE>` deviennent des signaux upstream
uniquement lorsque `evidence_id` ou `evidence_ids` fournit une attribution
exacte. Sans ID, aucun signal item-level n'est créé : le scanner conserve
`UNATTRIBUTED_UPSTREAM_SECURITY_WARNING:<CODE>` dans les limitations globales,
sans l'attribuer à tous les items et sans severity inventée. Une limitation
`SOURCE_REPORTED_STALE` ne devient également un signal item-level que si un
evidence ID est fourni ; aucune attribution n'est inventée.

Une divergence structurée `VERSION_DIVERGENCE` est signalée et toutes les
versions restent présentes.

La corroboration indépendante suit une règle exacte :

- même `source_ref` + même `locator` + même version/checksum → un seul groupe ;
- origine différente → groupes distincts ;
- même excerpt non vide et même version sur deux sources différentes →
  `CROSS_SOURCE_DUPLICATE_CONTENT`, sans fusion ni conclusion de fraude.

Aucun fuzzy matching, embedding ou calcul de similarité n'est exécuté.

## Historique des rounds

`EvidenceRoundRecord` snapshotte seulement : numéro, C-05, clés d'identité de
retrieval, evidence IDs, couverture et codes de sécurité. Aucun contenu,
excerpt, prompt ou payload provider n'est enregistré.

`EvidenceExpansionHistory` impose :

- rounds contiguës `1..N` ;
- mêmes run ID et correlation ID ;
- mêmes scope, source policy, filtres et autorité requise ;
- aucune augmentation de `max_items` par rapport à la première demande.

Le step ID et le search goal peuvent différer entre rounds.

## Décision d'expansion

Le besoin `EvidenceExpansionNeed` est fourni explicitement par le caller. Il
n'est jamais inféré depuis une instruction trouvée dans l'evidence.

Avant toute décision, l'assessment doit appartenir à la dernière round : les
evidence IDs reconstruits depuis les groupes de corroboration et les codes de
signaux dédupliqués doivent être exactement ceux de `EvidenceRoundRecord`.
Sinon l'advisor lève `SECURITY_ASSESSMENT_LINEAGE_MISMATCH`. Ce contrôle précède
aussi `NO_EXPANSION`, `STOP_MAX_ROUNDS` et `STOP_NO_PROGRESS`, de sorte qu'un
assessment étranger n'est jamais accepté silencieusement. Une proposal propage
les codes du record courant, après cette validation.

La policy baseline est :

```text
max_rounds = AgentRuntimePolicy.max_evidence_rounds = 3
max_items_per_set = 12
```

Douze est un default technique configurable. Si le C-05 initial est borné plus
bas, cette borne plus étroite gagne. Une demande supérieure échoue ; elle n'est
jamais tronquée silencieusement. Zéro reste une proposition valide qui devra
produire ultérieurement un retrieval vide.

L'advisor applique dans cet ordre :

1. besoin non requis → `NO_EXPANSION` ;
2. round 3 atteinte → `STOP_MAX_ROUNDS` ;
3. aucune nouvelle identité depuis les rounds précédentes → `STOP_NO_PROGRESS` ;
4. search goal inchangé → `STOP_NO_PROGRESS` ;
5. contrôle de `max_items` ;
6. `PROPOSE_NEXT_ROUND`.

La proposition copie exactement scope, source policy, filtres et autorité de la
première round. Son search goal vient uniquement du besoin explicite. Les codes
de sécurité sont transportés comme contexte d'audit et ne changent aucune
borne ou autorité.

## Aucune récursion AG-02

`EvidenceExpansionProposal` ne contient ni `ContractMeta`, ni step ID, ni
capability ou permission. Elle est destinée à AG-01 pour un futur plan/replan.
L'advisor ne recherche, ne fetch et ne coordonne rien : aucune boucle autonome
E01→E02→E03→E01 n'existe.

Aucun `SecurityEvent` ou EventBus global n'est créé en 12.7-E. L'intégration
runtime/Search/RAG appartient à 12.7-F ; le hardening global et l'observabilité
seront traités en 12.12/12.13.
