# Phase 12.17.4 — Rationalisation runners/parsers

## Inventaire des générations

La génération désigne ici une étape nommée ayant introduit un runner, parser,
gate ou contrat de sortie distinct. Les plans `semantic_integration`,
micro-canary et mini-pilot sont des orchestrations historiques, pas des
générations supplémentaires de runner/parser.

```text
RUNNER_PARSER_GENERATION_COUNT = 7
TARGET_ACTIVE_GENERATION_COUNT = 1
```

| Génération | Fichier | Active aujourd'hui | Rôle historique/compat | Doublon | Owner cible | Dépréciable | Immuable |
|---:|---|---|---|---|---|---|---|
| 1 | `tests/calibration/pedagogical/live_runner.py` | non, live clos | runner initial V4 | oui, orchestration | historique uniquement | oui comme point d'entrée actif | TRUE |
| 2 | `tests/calibration/pedagogical/live_runner_v4_1.py` | non, live clos | correction V4.1 | oui, orchestration/ledger | historique uniquement | oui comme point d'entrée actif | TRUE |
| 3 | `tests/calibration/pedagogical/semantic_parser_adapter_v5_1.py` | non | compatibilité parser V5.1 | oui, parsing provider | `calibration_tooling.adapters.anthropic` | oui comme implémentation active | TRUE |
| 4 | `tests/calibration/pedagogical/semantic_gate_v5_2.py` | non | gate mini-pilot V5.2 | oui, dispatch et gate | `calibration_tooling.application` | oui comme gate active | TRUE |
| 5 | `tests/calibration/pedagogical/pairwise_runner_v5_2_2.py` | non | fix runner pairwise | oui, parsing/dispatch | `calibration_tooling.runtime` | oui comme runner actif | TRUE |
| 6 | `tests/calibration/pedagogical/pairwise_output_contract_v5_2_3.py` | non | borne de sortie V5.2.3 | oui, output contract | `calibration_tooling.contracts` | oui comme contrat actif | TRUE |
| 7 | `tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py` | non | durcissement final V5.2.4 | version finale historique | `calibration_tooling.contracts` | oui comme contrat actif | TRUE |

« Dépréciable » signifie retiré du chemin actif futur, jamais supprimé ou
modifié sans une gate historique distincte.

## Mécaniques incidentielles archivées

Les éléments suivants restent consultables mais ne sont pas propagés dans le
nouveau runner : matrices V4/V4.1/V4.2, canaries consommés, tranches de repair,
carry-forward ponctuels, hashes d'autorisation live consommée, remédiations
HTTP 503 et contrats de sortie numérotés. Ils sont `HISTORICAL_EVIDENCE`.

Les invariants durables repris sont : blind scoring, strong-only,
one-shot/fail-closed, allowlist exacte, budget dur, zéro retry/rerun, lignée
certifiée, observation terminale non rappelée et `RELEASE_THRESHOLD = NONE`.

## Point d'entrée cible

`calibration_tooling.runtime.cli` est le seul point d'entrée humain. Il charge
une spécification versionnée, délègue à `runtime.runner`, puis ce runner appelle
des composants uniques :

```text
cli
  -> configuration + authorization + budget
  -> runner
       -> application.service
       -> provider scorer
       -> parser du provider
       -> ledger
       -> telemetry
```

Le parser n'est pas un second runner. Le score absolu et le choix pairwise sont
deux variantes discriminées d'un même `CalibrationObservationSpec`; le dispatch
utilise des branches et variables typées distinctes. Aucune union mutable de
micro-canary/mini-pilot n'est réutilisée.

## Stratégie de compatibilité

- Aucun wrapper historique n'importe le nouveau package : cela modifierait son
  hash ou son comportement.
- Aucun code actif n'importe les wrappers historiques.
- Les tests historiques continuent à cibler les fichiers V4/V5.x.
- Des tests de parité ne lisent que leurs sorties/fixtures publiques non
  sensibles et comparent les invariants durables au nouveau moteur.
- Les anciennes commandes sont documentées comme `HISTORICAL_ONLY`; elles ne
  sont pas aliasées vers le nouveau CLI.

## Dépréciation et suppression

Dans 12.17.4E, la dépréciation est architecturale et documentaire seulement.
Aucune des sept générations n'est supprimée. Une suppression ultérieure exige :

1. zéro import actif et zéro import de test non historique ;
2. copie de preuve indépendante ou décision propriétaire de rétention ;
3. vérification de tous les manifests/hashes ;
4. ADR de disposition ;
5. commit séparé et rollback possible.

La cible finale comporte donc une génération active et sept générations
historiques conservées hors graphe actif.
