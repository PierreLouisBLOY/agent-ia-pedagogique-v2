# Executor deterministe du plan

## Frontiere 12.5-D

`PlanExecutor` consomme une decision du `DeterministicScheduler`, applique les
controles pre-launch et confie chaque effet a un `StepRunner` injecte. Il ne lit
aucun repository, SQL, secret ou filesystem metier. Il ne selectionne ni agent,
provider, modele, use case ou tool concret.

Un `launch_candidate_id` du scheduler n'est pas un step lance. Le candidat est
seulement structurellement lancable et reste `READY`. Chaque candidat passe
obligatoirement par `PreLaunchGuard.check` avant toute transition `RUNNING`.
`ALLOW` signifie uniquement que les controles pre-launch necessaires a la route
preparee ont ete satisfaits ; ce vocabulaire local ne redefinit pas
`PolicyDisposition.ALLOW`. Le guard concret, la traduction des policies, gates,
scopes et budgets remaining sont differes.

`StepRunner` est un Protocol provider-neutral. D ne fournit aucune
implementation concrete. Le runner recoit un snapshot ou le step est deja
`RUNNING` et son numero d'attempt a deja ete incremente.

## Cycle et transitions

Un cycle appelle le scheduler exactement une fois, consomme ses signaux de
deadline puis traite les candidats dans leur ordre. Seule une decision ALLOW
produit `READY -> RUNNING`, fixe `started_at=now` et incremente
`attempt_count` exactement une fois. Le premier lancement reel produit
`PLANNED -> RUNNING` et fixe le `started_at` du run. Un resultat normal produit
ensuite `RUNNING -> SUCCEEDED`, `PARTIAL`, `FAILED` ou `CANCELLED`.

WAITING_GATE conserve le step READY, place le run en WAITING_GATE et arrete le
cycle. Si aucune execution n'avait commence, `started_at` reste `None`.
CONDITION_REQUIRED conserve le step READY et permet d'examiner un candidat
independant. DENY produit `READY -> BLOCKED` sans increment d'attempt et applique
ensuite la failure policy, sans jamais autoriser de retry.

Apres les resultats, `refresh_schedulable_state` peut propager READY/BLOCKED
dans le snapshot retourne. Ce refresh ne relance pas le scheduler et ne lance
jamais une seconde vague dans le meme cycle.

## Resultats, erreurs et failure policy

`StepExecutionResult` accepte seulement SUCCEEDED, PARTIAL, FAILED et CANCELLED.
Ses references et metriques sont immutables. FAILED exige une `ErrorEnvelope` ;
SUCCEEDED l'interdit. Les codes d'erreur utilises dans l'etat restent surs et
aucun payload provider ou texte brut d'exception n'est conserve.

Une `FailurePolicy` produit une directive, jamais une boucle : RETRY peut
produire RETRY_REQUIRED uniquement pour une erreur retryable, d'effet NONE et
d'une categorie sure. Aucun nouvel appel runner, backoff ou retry count complet
n'est execute. REPLAN produit REPLANNING sans construire de nouveau `Plan` ;
ESCALATE et STOP terminalisent explicitement le run.

Depuis 12.5-E, un `PlanRevisionEngine` separe peut adopter un replacement fourni
de l'exterieur. L'executor D ne le construit toujours pas et ne revise jamais le
plan dans son propre cycle.

`EffectState.UNKNOWN` est prioritaire : il produit
RECONCILIATION_REQUIRED et interdit tout replay automatique. Une exception du
runner laisse egalement le step RUNNING et exige une reconciliation, car un
effet a pu avoir lieu avant l'exception.

Toute violation contractuelle detectee apres l'invocation du runner est traitee
de la meme maniere comme un effet potentiellement inconnu : le step reste
RUNNING avec son attempt incremente et une reconciliation est obligatoire. Un
`ErrorEnvelope` retourne doit viser le `step_id` execute et exactement
l'`attempt` courant. Un mauvais type de resultat ou une erreur mal attribuee
n'est jamais applique et ne pilote jamais la `FailurePolicy`. Aucun contenu brut
du resultat fautif n'est recopie dans une directive ou le snapshot.

## Deadlines et succes global

Les signaux du scheduler sont consommes sans inventer l'absence d'effet :

- un RUNNING expire reste RUNNING et exige une reconciliation ;
- une deadline globale sans step RUNNING termine le run en FAILED ; avec un
  step RUNNING, elle conserve le run non terminal et exige une reconciliation ;
- un READY expire devient FAILED sans lancement ni increment d'attempt, puis sa
  failure policy est appliquee ; RETRY sans erreur produit STOPPED.

D ne deduit jamais le succes global du seul fait que tous les steps sont
terminaux. `Plan.success_criteria` reste declaratif et n'a pas encore
d'evaluateur canonique.

Un run deja terminal est un no-op strict apres validation scheduler : son
snapshot entrant est retourne sans refresh de steps PENDING vers READY.

## Hors scope

La validation et l'adoption versionnee d'un replacement externe appartiennent a
12.5-E ; sa generation par un planner concret reste 12.6. Le routing concret et
l'execution des gates appartiennent a 12.10. Les retries, backoff, budgets
consommes, reconciliation et recovery complets appartiennent a 12.11.
