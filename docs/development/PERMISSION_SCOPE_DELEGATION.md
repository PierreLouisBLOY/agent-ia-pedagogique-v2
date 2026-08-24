# Delegation bornee de PermissionScope

`DelegationScopePolicy` evalue uniquement la transmission d'un scope AG-01 vers
AG-02, AG-03 ou AG-04. Elle ne consulte pas `AccessMatrix`, ne verifie pas que la
capability appartient au target et ne cree aucun `DelegationEnvelope`. Le controle
owner/matrice sera effectue par la combinaison finale de Phase 12.4-D.

Le scope parent doit etre valide, actif, porter le principal agent `AG-01` et
avoir `delegable=True`. Le principal enfant doit correspondre exactement au target.
Le scope enfant conserve ou reduit les capabilities, operations, ressources,
fenetres temporelles et budgets ; il conserve ou renforce les contraintes, gates
et denies parent. Le changement de principal attendu est la seule exception a la
relation generale de narrowing.

AG-02, AG-03 et AG-04 ne peuvent pas redeleguer dans la baseline : le scope enfant
doit garder `delegable=False`. Une capability R3 ou R4 est refusee comme droit
direct delegue. Les risques R0, R1 et R2 passent ce filtre si les autres regles de
scope sont respectees, sans que cela constitue une autorisation finale.

Les codes fermes couvrent l'autorisation, les scopes invalides, un parent non
delegable ou non AG-01, un target invalide, un principal enfant incoherent, un
parent inactif, un scope enfant plus large, un risque non delegable et une
tentative de redelegation.

La policy ne modifie aucun scope et n'execute ni retry, fallback, provider,
scheduler, gate engine ou use case. Un deny herite ne peut donc pas etre efface
ou contourne par reroutage.
