# Phase 12.17.4E-B02 — Implémentation des contrats actifs

## Surface créée

| Couche | Fichiers | Responsabilité |
|---|---|---|
| package | `calibration_tooling/__init__.py` | version du tooling, surface minimale |
| contracts | `contracts/{errors,models,parser,policy}.py` | erreurs fermées, specs discriminées, schéma/parser actif, policy durable |
| application | `application/{ports,service}.py` | ports transport/parser/ledger/clock et invocation unique |
| runtime | `runtime/{authorization,budget,ledger,runner}.py` | allowlist one-shot, budget Decimal, ambiguïté, moteur actif unique |

Les `__init__.py` de sous-packages ne publient qu'une surface bornée.

## Contrat runner

- input : `CalibrationPlan`, version `calibration-tooling.v1` ;
- observations : union discriminée `AbsoluteObservationSpec | PairwiseObservationSpec` ;
- output : `CalibrationRunOutput` typé et terminal ;
- transport : `ProviderTransportPort` injecté ;
- parser : `CalibrationOutputParserPort` injecté ;
- aucune sélection de provider, résolution de credential ou lecture implicite ;
- aucun retry, rerun, fallback ou boucle non bornée ;
- appel suivant interdit dès le premier échec ;
- état provider inconnu laissé `STARTED`, donc ambigu et bloquant.

## Contrat parser

- cible unique : `calibration_tooling.contracts.parser.v1` ;
- schéma unique exposé par `active_output_schema` ;
- version de payload : `calibration-output.v1` ;
- champs exacts et `additionalProperties = false` ;
- limite totale : 8 192 octets UTF-8 ;
- troncature : erreur `RESPONSE_TRUNCATED` ;
- JSON, type, identité ou variante invalides : erreur fermée ;
- aucune normalisation ou troncature silencieuse ;
- texte brut exclu du `repr` de `RawProviderResponse` et des exceptions.

## Invariants durables

`DurableCalibrationPolicy` impose : blind scoring, `STRONG` seul livrable,
autorisation one-shot, fail-closed, retry count zéro et
`release_threshold = None`.

`AnchorTriplet` encode exactement strong/mixed/weak avec trois projections
distinctes. `ApprovedBudget` exige un plafond `Decimal` non optionnel, une
précision maximale de six décimales et un nombre d'appels borné.

Le lot ne crée ni adapter Anthropic, ni composition, ni CLI : ces éléments
appartiennent respectivement à B03 et B04.
