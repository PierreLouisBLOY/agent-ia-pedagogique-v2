# CapabilityRegistry et matrice d'acces

Le catalogue contient exactement 24 `CapabilityId` canoniques : trois lectures,
trois capabilities Evidence, trois Generation/Transformation, deux Review, trois
actions Application, quatre utilitaires techniques et six operations
d'orchestration.

Une capability exprime une aptitude logique. Elle n'est ni un tool ni un use
case. `CapabilityExecutionRoute` indique seulement la frontiere logique
`APPLICATION`, `AGENT`, `RUNTIME` ou `UTILITY` ; aucun provider, `tool_id` ou
handler concret n'est stocke dans le registry.

Les routes `AGENT` ont un owner explicite : AG-02 pour CAP-E*, AG-03 pour CAP-G*
et AG-04 pour CAP-V*. Les autres routes n'ont aucun owner agent. Les risques R0
a R4 classent la capability mais ne lui accordent aucune permission.

`AccessMatrix` contient exactement 96 regles, soit les quatre agents croises avec
les 24 capabilities. Elle constitue une ceiling policy statique et exhaustive.
Une cellule absente est une erreur de configuration, jamais un `DENY` implicite.

Les modes `ALLOW`, `DENY`, `REQUEST`, `DELEGATE`, `REQUEST_GATE`, et
`CONDITIONAL` decrivent cette ceiling. `CONDITIONAL` ne signifie pas `ALLOW`.
L'evaluator pur de `PermissionScope`, implemente en 12.4-C, ne consulte pas cette
matrice. La combinaison effective ceiling + scope reste reservee a 12.4-D.
