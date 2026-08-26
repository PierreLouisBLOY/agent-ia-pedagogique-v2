# ADR P12-025 - Tool registry et call policy provider-neutral

## Statut

Accepte.

## Contexte

La Phase 12.10 doit transformer les routes logiques existantes en frontieres
d'execution bornees sans deplacer l'autorite de `CapabilityRegistry`,
`AccessMatrix`, `PermissionScope` ou Application. Le lot B doit preparer le
routing tool sans executer de tool, materialiser de sandbox, choisir de handler
ou introduire de fournisseur.

`ToolCallRequest` exprime deja un intent controle, mais son `tool_id` ne confere
aucune autorite. `CapabilityAuthorizationPolicy` reste l'unique composition de
la ceiling matrix et du scope explicite. Un catalogue distinct est donc requis
pour lier un identifiant de tool stable a une capability technique precise.

## Decision

### Classification d'effet

`ToolEffectClass` est un vocabulaire ferme :

- `READ_ONLY` : lecture sans mutation attendue ;
- `PURE_COMPUTE` : calcul technique side-effect free attendu ;
- `LOCAL_FILE_TRANSFORM` : transformation locale produisant potentiellement un
  fichier, obligatoirement sandboxee et idempotente ;
- `EXTERNAL_MUTATION` : classe reservee, interdite par la policy 12.10-B.

Cette classification decrit l'effet anticipe avant execution. Elle reste
distincte de `EffectState`, qui decrit l'etat constate ou inconnu apres une
tentative d'execution.

### ToolRegistry

`ToolRegistry` est statique, immutable et fail-fast. Il est distinct du
`CapabilityRegistry`, qu'il reutilise pour verifier classe, route et absence
d'owner agent. `ToolDescriptor` contient seulement :

```text
tool_id
canonical_name
capability_id
input_contract_id
output_contract_id
effect_class
sandbox_profile_id
idempotency_required
timeout_ceiling
```

Le risque n'est pas recopie : il reste resolu depuis le descriptor de capability.
Le registry ne contient ni handler, callable, secret, URL, provider ou connexion.
Les lookups sont exacts ; aucun fallback, fuzzy matching ou plugin discovery
n'est admis.

### Baseline et Option A

La baseline retient l'Option A :

- `tool.render_document` lie a CAP-T02 ;
- `tool.convert_format` lie a CAP-T03.

Les deux descriptors sont `LOCAL_FILE_TRANSFORM`, exigent la cle d'idempotence,
declarent `sandbox.local_file_transform.v1` et une ceiling de 120 secondes.
Cette ceiling est une limite tool ; elle reste semantiquement distincte de la
deadline runtime par defaut, meme si les valeurs de baseline coincident.

CAP-T01 et CAP-T04 restent des utilities pures. Elles ne sont pas artificiellement
converties en tools routables dans ce lot.

### ToolCallPolicy

`ToolCallPolicy` compose `CapabilityAuthorizationPolicy` avec le registry. Elle
construit un `ScopeCheck` depuis le scope exact porte par la requete, sans merge,
fallback ou reconstruction d'un grant plus large. T02/T03 utilisent l'operation
canonique `transform`; la resolution conditionnelle reste entierement possedee
par `CapabilityAuthorizationPolicy` et ses `PolicyFacts` trusted.

Seule une `CapabilityPolicyDecision` de disposition `ALLOW` peut produire une
`ToolCallDecision` `ALLOW`. `REQUEST`, `DELEGATE`, `REQUEST_GATE`,
`CONDITION_REQUIRED` et tout `DENY` restent non executables.

La policy verifie ensuite le binding tool/capability, les arguments sans cles
d'autorite, l'idempotence, la ceiling de timeout et la presence declarative du
profil sandbox attendu. Un timeout absent prend deterministiquement la ceiling
du descriptor ; un timeout explicite n'est jamais augmente.

La liste des profils sandbox disponibles est une donnee trusted fournie au
moment de l'evaluation. Elle ne materialise aucun root, chemin ou filesystem.
Les arguments ne peuvent ni choisir ni remplacer le profil.

`ToolCallDecision` est data-only et ne stocke aucun callable. Une classe
`EXTERNAL_MUTATION` est refusee inconditionnellement dans cette baseline, y
compris avec une cle d'idempotence.

## Consequences

- capability, tool et handler restent trois notions distinctes ;
- le ToolRouter futur ne pourra resoudre un handler qu'apres une decision ALLOW ;
- T02/T03 sont prets a consommer le sandbox de 12.10-C sans l'implementer ici ;
- aucune cle d'idempotence n'est stockee et aucun replay n'est tente ;
- les schemas detailles d'arguments et resultats restent la responsabilite du
  futur binding descriptor/handler ;
- aucun provider, I/O, subprocess, reseau ou dependance runtime n'est ajoute.

## Rationalisation

`ToolEffectClass` n'est pas fusionne avec `EffectState`, car leurs temporalites
et invariants divergent. `ToolRegistry` n'est pas generalise avec
`CapabilityRegistry`, car le premier lie des mecanismes techniques tandis que
le second reste la source canonique des capabilities, routes et risques.

La validation agent-safe existante continue de filtrer les donnees privees. Le
filtre de cles d'autorite de ToolCallPolicy est plus specifique : il empeche
qu'un argument ne tente de selectionner capability, tool, handler, gate,
provider ou sandbox. Ces deux controles ne sont donc pas des duplications.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
