# Delegation bornee de PermissionScope

`DelegationScopePolicy` evalue uniquement la transmission d'un scope AG-01 vers
AG-02, AG-03 ou AG-04. Elle ne consulte pas `AccessMatrix`, ne verifie pas que la
capability appartient au target et ne cree aucun `DelegationEnvelope`. Le controle
owner/matrice est effectue par la combinaison finale de Phase 12.4-D, sans changer
la responsabilite de narrowing portee par C.

Le scope parent doit etre valide, actif, porter le principal agent `AG-01` et
avoir `delegable=True`. Le principal enfant doit correspondre exactement au target.
Le scope enfant conserve ou reduit les capabilities, operations, ressources,
fenetres temporelles et budgets ; il conserve ou renforce les contraintes, gates
et denies parent. Le changement de principal attendu est la seule exception a la
relation generale de narrowing.

La revocation et l'expiration sont deux causes distinctes. `parent_revoked` est un
fait trusted injecte explicitement par la couche runtime/policy. Lorsqu'il vaut
`True`, le parent ne peut plus creer de grant enfant, meme s'il reste dans sa
fenetre temporelle ou si une autre regle aurait produit un refus different.
`PARENT_INACTIVE` reste reserve a `valid_from` et `expires_at`. Aucune persistance,
propagation transitive ou registry mutable de revocations n'est implementee ici.

AG-02, AG-03 et AG-04 ne peuvent pas redeleguer dans la baseline : le scope enfant
doit garder `delegable=False`. Une capability R3 ou R4 est refusee comme droit
direct delegue. Les risques R0, R1 et R2 passent ce filtre si les autres regles de
scope sont respectees, sans que cela constitue une autorisation finale.

Les codes fermes couvrent l'autorisation, les scopes invalides, un parent non
delegable ou non AG-01, un target invalide, un principal enfant incoherent, un
parent inactif, un scope enfant plus large, un risque non delegable et une
tentative de redelegation. `PARENT_REVOKED` identifie separement la revocation
opposable a toute nouvelle delegation.

La policy ne modifie aucun scope et n'execute ni retry, fallback, provider,
scheduler, gate engine ou use case. Un deny herite ne peut donc pas etre efface
ou contourne par reroutage.

La policy finale D exige en plus que la capability soit `DELEGATE` pour AG-01,
que le target soit l'owner exact et que sa rule soit `ALLOW`. Un refus C reste
compose dans `SCOPE_DELEGATION_DENY`; un mauvais owner produit `OWNER_MISMATCH`.
