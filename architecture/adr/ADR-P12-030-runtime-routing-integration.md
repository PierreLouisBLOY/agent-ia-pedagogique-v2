# ADR-P12-030 — Intégration du routing runtime trusted

## Statut

Accepté — Phase 12.10-G.

## Contexte

Les frontières B–F définissent déjà les registries, policies, sandbox, routers
Application/outil et le moteur de gate. Le runtime déterministe possède un unique
`PlanExecutor`, avec `PreLaunchGuard` et `StepRunner` comme points d’injection. Les
`StepSpec` ne portent que des références : leur résolution doit donc rester trusted,
typée et séparée de toute décision d’autorité.

## Décision

Le package `backend.agent_runtime.runtime.routing` compose les frontières existantes :

- `RuntimeRoutingResolverPort` expose quatre résolutions explicites — use case,
  outil, gate et agent — sans méthode générique ni implémentation I/O ;
- `RoutingPreLaunchGuard` valide la forme statique, mappe les gates, effectue le dry
  authorization outil et contrôle la délégation agent sans exécuter de frontière ;
- `RoutingStepRunner` route exactement selon `StepKind`, sans réflexion ni fallback ;
- `AgentStepRouter` lie uniquement AG-02, AG-03 et AG-04 à des ports opaques ;
- `RuntimeControlStepRunnerPort` conserve JOIN/DECISION sous autorité runtime.

Tous les composants partagent la même instance de
`CapabilityAuthorizationPolicy`. Aucun second executor, scheduler ou moteur de
policy n’est créé et `PlanExecutor` reste inchangé.

## Autorités préservées

- TOOL exige `ToolCallPolicy.ALLOW`, puis le sandbox et le binding exact du
  `ToolRouter` ;
- USE_CASE exige `CapabilityAuthorizationPolicy.REQUEST` via `UseCaseRouter` ;
- AGENT exige `DELEGATE` depuis AG-01 vers le propriétaire exact ;
- GATE exige une décision externe `APPROVED`, qui ne devient qu’un fait de policy ;
- JOIN/DECISION exigent une capability et un executor runtime.

Le mapping agent est fermé : E01/E02/E03→READ, G01→CREATE, G02/G03→TRANSFORM,
V01/V02→REVIEW. E03 reste READ conformément à sa responsabilité d’évidence et au
vocabulaire existant.

## Gates et CAP-A02

Au prelaunch, WAITING/DEFERRED deviennent `WAITING_GATE`, REJECTED/EXPIRED deviennent
`DENY`, et APPROVED devient `ALLOW` de lancement uniquement. Le runner réévalue la
gate. Pour CAP-A02, il ignore tout `matrix_gate_satisfied` du resolver et construit
les faits exclusivement depuis la résolution du `GateEngine`; `UseCaseRouter`
réévalue ensuite capability et scope avant l’unique appel inbound. Une approbation
n’est jamais une promotion automatique.

## Effets et erreurs

Les refus connus avant effet deviennent des `StepExecutionResult.FAILED` sûrs avec
`EffectState.NONE` et sans retry. Les erreurs outil possibles après l’executor, les
erreurs Application après l’inbound et les exceptions des ports agent/runtime sont
propagées au `PlanExecutor`, qui conserve son traitement canonique
`RECONCILIATION_REQUIRED`/effet inconnu. Les sorties runtime ne contiennent que les
références reçues des frontières.

## Conséquences

- Aucun adapter provider, HTTP, réseau, DB, filesystem OS ou persistence n’est ajouté.
- Aucun polling, retry automatique, import dynamique, découverte de plugin ou
  dispatch textuel n’est introduit.
- La double lecture gate prelaunch/runner est un security re-check, jamais une boucle.
- Les agents gardent leurs responsabilités et retournent un résultat runtime opaque.
- Les workflows existants ne sont pas modifiés pour injecter des outils implicitement.

## Alternatives écartées

- Un router universel : il confondrait ALLOW, REQUEST, DELEGATE et APPROVED.
- Un resolver `resolve(ref) -> object` : il permettrait le type smuggling.
- Une gate mise en cache : elle rendrait possible une autorité devenue obsolète.
- Une conversion des erreurs post-effet en échec connu : elle masquerait les effets.
- Une modification de `PlanExecutor` : les points d’injection existants suffisent.

## Rationalisation

`NO_SAFE_CONSOLIDATION_REQUIRED`.
