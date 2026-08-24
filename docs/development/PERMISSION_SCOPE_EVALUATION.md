# Evaluation de PermissionScope

La Phase 12.4-C ajoute un evaluator pur du contrat data-only `PermissionScope`.
Il verifie un `ScopeCheck` sans consulter `AccessMatrix` et ne produit donc pas la
decision d'autorisation finale du systeme. La Phase 12.4-D combine desormais la
ceiling matrix statique et le scope dynamique dans une couche distincte. Le scope
evaluator C reste independant d'`AccessMatrix`.

## Ordre fail-closed

L'evaluation suit un ordre deterministe : configuration du scope, principal,
revocation, fenetre temporelle, denies explicites, capability, operation,
ressources, contraintes, gates, budget, puis `ALLOW`. Un deny explicite precede
toujours les grants et ne provoque aucun reroutage.

`valid_from` est inclusif et `expires_at` exclusif. L'`Instant` est fourni par le
caller ; aucun clock global n'est introduit. `revoked` et les gates satisfaites
sont des facts de confiance injectes par le runtime/policy layer, jamais derives
d'une sortie agent ou d'un document non fiable dans ce lot.

## Grammaire deny v1

Une deny rule accepte uniquement `capability_id`, `operation`, `resource_scope`
et `reason_code`. Les trois premiers champs sont des selecteurs ; `reason_code`
est informatif. Tous les selecteurs presents doivent matcher. Une regle vide ou
contenant seulement `reason_code` est globale. Une cle inconnue, un type invalide
ou une operation hors du vocabulaire ferme invalide le scope. Le premier deny
matche est retourne par son index.

## Relations conservatrices

Le resource narrowing autorise le check a selectionner moins de cles ou moins
d'elements d'une allowlist tuple que le grant. Il interdit toute nouvelle
ressource, wildcard ou coercition numerique implicite.

Le constraint narrowing suit la relation inverse : toutes les contraintes du
scope parent doivent rester presentes, tandis que le check peut en ajouter. Une
allowlist effective doit etre un sous-ensemble de l'allowlist parent. Les noms
`max_*`, regex, intervalles et nombres n'ont aucune semantique implicite.

Le budget est compare comme une enveloppe uniquement. Chaque limite demandee doit
etre inferieure ou egale a la limite accordee ; retirer une limite parent elargit
le scope et est refuse. Il n'existe ici ni consommation, reservation, remaining
budget, ni `BudgetState`.

Les codes fermes sont `ALLOW`, `INVALID_SCOPE`, `PRINCIPAL_MISMATCH`, `REVOKED`,
`NOT_YET_VALID`, `EXPIRED`, `EXPLICIT_DENY`, `CAPABILITY_NOT_GRANTED`,
`OPERATION_NOT_GRANTED`, `RESOURCE_OUT_OF_SCOPE`, `CONSTRAINT_OUT_OF_SCOPE`,
`GATE_REQUIRED` et `BUDGET_OUT_OF_SCOPE`.
