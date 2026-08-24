# AgentRuntimePolicy

`AgentRuntimePolicy` regroupe des garde-fous techniques immuables et
configurables. La baseline fixe 24 steps par run, 6 versions de plan, 4 steps
paralleles, une profondeur de delegation de 2, 8 tool calls par step, 2 retries,
2 cycles de review et 3 rounds d'evidence.

La compression de contexte commence a `Decimal("0.70")` et l'utilisation
maximale vaut `Decimal("0.80")`. Les deadlines par defaut sont de 600 secondes
pour le run et 120 secondes pour un step. L'attente d'une gate met en pause la
deadline du run. Aucun budget de cout n'est impose par defaut.

Ces chiffres sont configurables et ne sont pas des regles Domain. La structure
ne contient ni `BudgetState`, ni consommation, ni scheduler, ni retry/stop reel.
`RuntimeMode` et `AutonomyLevel` ne derivent et ne modifient aucune permission.

La policy composite de `ToolCall`, le routing concret, le sandbox et les gates
d'execution restent differes a 12.10. Aucun fournisseur ou LLM reel n'est requis.
