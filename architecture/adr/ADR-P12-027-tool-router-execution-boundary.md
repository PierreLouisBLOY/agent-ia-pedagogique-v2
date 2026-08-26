# ADR-P12-027 - ToolRouter et frontiere d'execution

## Statut

Accepte pour la Phase 12.10-D.

## Contexte

B a etabli ToolRegistry et ToolCallPolicy. C a etabli les profiles, la policy
sandbox et un port filesystem abstrait. Il manquait une unique frontiere capable
de composer ces decisions avant un appel technique, puis de refuser un resultat
ou une sortie forges.

Le depot ne contient aucun moteur canonique de rendu ou conversion. Introduire
LibreOffice, Pandoc, Word, un navigateur ou un provider en D elargirait le lot
sans decision canonique.

## Decision

### Placement

Le package `backend/agent_runtime/tools/` porte la frontiere technique
d'execution. Il reste separe de `registry`, `policy`, `sandbox`, des contrats et
du runtime scheduler.

### Ordre d'autorite

`ToolRouter.route` applique strictement :

```text
ToolCallPolicy
-> SandboxFilesystemPort resolve/inspect
-> SandboxPolicy pour chaque input/output
-> binding executor exact
-> un appel ToolExecutorPort.execute
-> revalidation ToolCallResult
-> reinspection et SandboxPolicy sur les sorties produites
```

Une decision non-ALLOW interrompt le pipeline. Le binding n'est resolu qu'apres
les preflights sandbox. Aucun retry, fallback ou second executor call n'existe.

### Port et bindings

`ToolExecutorPort` recoit uniquement un `PreparedToolExecution`. Les bindings
injectes contiennent exactement `tool_id` et le port executor. Ils sont
distincts de ToolDescriptor, utilisent un lookup exact, refusent les doublons
et ne possedent aucun import path, provider ou fallback.

Aucun executor production n'est livre. Les preuves utilisent des fakes
recording sous `tests/support/`.

### Routing context et preparation

`ToolRoutingContext` contient un `SandboxRootRef` trusted, des inputs deja types
`SandboxRelativePath` et des `SandboxOutputTarget` fermes WRITE/CREATE. Les
arguments du ToolCallRequest ne fournissent aucun path, root, profile ou
binding.

`PreparedToolExecution` lie exactement request, descriptor, decision tool
ALLOW, profile, root, paths, decisions sandbox ALLOW, timeout effectif,
idempotency key, run/step/correlation et contract IDs. Ses invariants rendent
incoherente toute substitution d'identite ou d'autorite.

### Outcome et revalidation

`ToolExecutionOutcome` enveloppe le ToolCallResult canonique et les seuls paths
produits. Un succes exige l'ensemble exact des outputs autorises ; les autres
statuts ne peuvent annoncer qu'un sous-ensemble, jamais un path supplementaire.

Le routeur revalide tool, run, step, correlation, statut, erreur, mappings
agent-safe et artifacts. Il reconstruit ensuite un ToolCallResult canonique afin
de ne pas accepter un objet forge ou mutable. Un statut FAILED reste FAILED ;
un SUCCEEDED portant une erreur est refuse.

Les outputs/metrics ne peuvent transporter de root, profile, permission,
capability, handler, provider, credential ou autre autorite technique.

### Sorties sandbox

Apres executor, chaque path produit est repris exclusivement depuis le contexte
trusted, puis resolu et inspecte de nouveau. La SandboxPolicy est appliquee en
WRITE avec les metadata observees : confinement, symlink, extension, MIME,
taille et contenu actif/executable sont donc revalides.

La policy C verifie maintenant les metadata observees d'un output existant en
plus des declarations pre-execution. Cette extension conserve sa frontiere
data-only et ne realise aucune I/O.

### Scope baseline

Seuls `tool.render_document` et `tool.convert_format` sont routables. CAP-T01 et
CAP-T04 restent des utilities sans ToolDescriptor. EXTERNAL_MUTATION reste
refusee par ToolCallPolicy avant tout acces au sandbox ou a un executor.

## Consequences

- Aucun handler n'entre dans ToolDescriptor.
- Aucun absolute path ou token fourni par l'executor n'est accepte.
- Le timeout et l'idempotency key sont transportes sans timer, ledger,
  deduplication, replay ou retry.
- Aucun adapter filesystem OS, provider, reseau, shell ou subprocess n'est
  introduit.
- UseCaseRouter, GateEngine, StepRunner et integration runtime restent differes.

## Rationalisation

Les ports AG-02/03/04 donnent une convention provider-neutral, mais transportent
des operations et contrats metier differents. ToolRegistry reste la source de
metadata et ne peut devenir un registry d'executors. Les patterns de prepared
calls confirment l'utilite des snapshots exacts, sans justifier un ProviderPort
commun ni le partage d'une autorite.

Les validations de resultat tool et d'arguments tool sont placees de part et
d'autre de l'executor ; leurs donnees et niveaux de confiance different. Leur
vocabulaire anti-smuggling reste donc local a chaque frontiere.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
