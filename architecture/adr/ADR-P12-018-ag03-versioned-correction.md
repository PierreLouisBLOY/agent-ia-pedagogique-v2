# ADR-P12-018 — Correction versionnee bornee AG-03

## Statut

Accepte pour la Phase 12.8-E.

## Contexte

C-11 `CorrectionRequest` est le mandat canonique d'une correction : il designe
une version exacte, une review, des findings et des changements permis ou
interdits. AG-03 ne dispose d'aucune autorite pour charger cette cible, elargir
le mandat, valider le resultat ou muter la version existante.

## Decision

La cible est resolue en amont puis fournie comme `ResolvedCorrectionTarget` avec
son `ObjectVersionRef` exact. Le `GenerationCoordinator` existant prepare une
requete `CORRECT` et utilise le meme `GenerationPort` que G01/G02. La reference
versionnee transite dans `target_version_ref`, jamais dans un mapping agent-safe.

Le port recoit le contenu cible deja resolu, les inputs caller-supplied et un
bloc de contraintes ferme derive exclusivement de C-11. Il emet un
`GenerationPortResult` technique. Son `operation_details` est un control block
ferme contenant les findings declares addressed/unresolved et un resume ; il ne
constitue pas encore un `CorrectionResult` et ces declarations ne sont pas une
review AG-04.

Le `PreparedCorrectionCall` conserve par identite le
`CorrectionPreparationRequest` d'origine. Avant l'appel outbound, le coordinateur
revalide les champs exposes ainsi que `caller_resolved_inputs` et
`output_contract` contre ce snapshot exact. Ces donnees restent caller-supplied
et non autoritatives, mais ne peuvent pas etre substituees entre prepare et
execute. Cette lineage n'ajoute aucun acces repository.

Une materialisation explicite, avec metadata, identite candidate et nouvelle
version fournis par le caller, construit ensemble :

- une nouvelle `ProductionCandidate` C-08 dans l'etat `CANDIDATE` ;
- le `CorrectionResult` existant, avec la version cible comme parent.

`CorrectionResult` conserve l'autorite sur les invariants de version : meme
identite d'objet et version differente. La cible n'est jamais mutee.

## Consequences et limites

- `SUCCEEDED` et `PARTIAL` peuvent materialiser les deux contrats.
- `REFUSED` et `INSUFFICIENT_EVIDENCE` ne materialisent aucune correction.
- Aucun retry ou boucle locale n'est introduit ; une repetition releve de WF-7.
- Aucune validation, promotion, persistance ou review reelle n'est effectuee.
- Le hardening general reste differe a 12.8-F et les workflows a 12.8-G.
- Aucun provider concret ou wiring runtime n'est ajoute.
