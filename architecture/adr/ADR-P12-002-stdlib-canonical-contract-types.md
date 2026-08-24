# ADR-P12-002 : types canoniques du coeur avec la bibliotheque standard

- Statut : accepte
- Date : 2026-08-24
- Phase : 12.3-B

## Contexte

Le Shared Kernel et `core_contracts` portent des primitives et contrats transverses. Ils doivent
rester generiques, immuables, transport-agnostiques et independants des frameworks, fournisseurs et
modules metier. Les contrats de validation `ValidationIssue` et `ValidationResult` appartiennent a
M09 (`validation_control`) et ne peuvent pas devenir une dependance du coeur transverse.

## Decision

Les value objects et contract objects de ce lot utilisent `dataclass(frozen=True, slots=True)`. Les
vocabulaires fermes utilisent `StrEnum`; les contrats parametriques utilisent les generiques de
`typing`. La validation locale se limite aux invariants canoniques, notamment les chaines non vides,
les dates et instants valides, les donnees structurees sures et la coherence de `ApplicationOutcome`.
Les donnees diagnostiques suivent une politique fail-closed : les cles techniques ou sensibles sont
refusees, les valeurs sont profondement figees et seules les references canoniques sont admises en
plus des scalaires et collections data-only. Aucune redaction silencieuse n'est effectuee.
La politique distingue les secrets et tokens d'authentification des compteurs de tokens et des
metadonnees de recherche provider-neutral necessaires au diagnostic et a la remediation.

`ApplicationOutcome` parametre le type de son `validation_result`. Il peut donc recevoir le contrat
proprietaire de M09 sans que `core_contracts` importe M09. `BusinessError`, `ApplicationFailure` et
les futurs `ValidationIssue`/`ValidationResult` restent trois concepts distincts.

Pydantic, JSON Schema et les schemas propres aux API ou fournisseurs pourront adapter ces objets aux
frontieres. Ils ne definissent pas leur representation canonique et ne sont pas introduits comme
dependances du coeur.

## Consequences

- Le coeur depend uniquement de Python 3.12 et du Shared Kernel selon sa couche.
- Les objets sont simples a typer, tester et adapter sans semantique HTTP, ORM ou SDK.
- La serialisation n'est pas une responsabilite de ces contrats.
- `ApplicationOutcome.correlation_id` est obligatoire et ses side effects utilisent les memes donnees
  structurees sures que les diagnostics.
- Une fitness function controle les directions de dependance et l'absence de packages tiers.

## Criteres de reexamen

Cette decision sera revue si un besoin canonique exige une validation de schema partagee impossible a
exprimer clairement avec la bibliotheque standard, si plusieurs frontieres dupliquent une adaptation
identique et stable, ou si des contraintes mesurees de performance ou d'interoperabilite le justifient.
Toute evolution devra conserver l'ownership M09 et faire l'objet d'un ADR avant implementation.
