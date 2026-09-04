# Phase 12.17.4 — Mapping des 15 diagnostics mypy

## Cible vérifiable

```text
BACKEND_MYPY_TARGET = 0
ACTIVE_IMPORT_DRIVEN_MYPY_TARGET = 0
NEW_DIAGNOSTICS_TARGET = 0
MAPPED_DIAGNOSTICS = 15/15
HISTORICAL_SOURCE_FILES_MODIFIED = 0
```

L'ancienne commande import-driven démarre explicitement dans
`pairwise_output_contract_v5_2_4.py`, un artefact historique immuable. Elle
reste une reproduction informative attendue à `15 erreurs / 10 fichiers` et
n'est pas maquillée par un ignore, un exclude ou un stub. La gate active future
partira du nouveau package `calibration_tooling` et de ses tests. C'est cette
isolation de graphe, autorisée explicitement par le prompt, qui rend la cible
import-driven `0` possible sans casser les preuves.

## Changements racines

Les neuf changements racines du design sont ceux du bundle :

| ID | Changement racine |
|---|---|
| `RC-01` | provider Anthropic actif hors `tests/` |
| `RC-02` | frontière calibration active/historique |
| `RC-03` | runner/parser actif unique |
| `RC-04` | graphe actif sans import V4/V5.x |
| `RC-05` | contrats typés du tooling actif |
| `RC-06` | vocabulaires par bounded context |
| `RC-07` | chemins de données portables |
| `RC-08` | cycle seed/runtime explicite |
| `RC-09` | trace legacy rétrospective |

`ROOT_CHANGE_COUNT = 9`.

## Registre 15/15

| Error ID | Fichier historique | RC | Correction architecturale prévue dans le graphe actif | Historique modifié | Disparition active attendue | Test ciblé futur |
|---|---|---|---|---|---|---|
| `MYPY-001` | `tests/providers/anthropic/transport.py:88` | `RC-01`, `RC-04`, `RC-05` | nouveau transport typé, sans cast redondant ; aucune dépendance active vers l'ancien | NO | TRUE | `tests/unit/calibration_tooling/test_anthropic_transport.py` + hash guard historique |
| `MYPY-002` | `tests/providers/anthropic/scorer.py:198` | `RC-01`, `RC-05` | helper d'erreur commun annoté `NoReturn`; branche provider affinée | NO | TRUE | `tests/unit/calibration_tooling/test_anthropic_scorer.py` |
| `MYPY-003` | `tests/providers/anthropic/scorer.py:208` | `RC-01`, `RC-05` | configuration résolue en type non optionnel avant lecture du modèle | NO | TRUE | même test, cas configuration absente/incomplète |
| `MYPY-004` | `tests/providers/anthropic/scorer.py:215` | `RC-01`, `RC-05` | value object `ResolvedScorerConfiguration` non optionnel transmis au transport | NO | TRUE | même test, assertion de type et erreur fermée |
| `MYPY-005` | `tests/providers/anthropic/scorer.py:216` | `RC-01`, `RC-05` | même résolution atomique provider/modèle | NO | TRUE | même test, matrice provider/modèle |
| `MYPY-007` | `tests/calibration/pedagogical/catalog.py:489` | `RC-02`, `RC-03`, `RC-05` | nouveau `AnchorTriplet` valide exactement trois tiers à la construction | NO | TRUE | `tests/unit/calibration_tooling/test_anchor_contracts.py` |
| `MYPY-008` | `tests/calibration/pedagogical/anchor_corpus_v2.py:681` | `RC-02`, `RC-05` | V2 reste historique ; les entrées actives sont converties à la frontière vers `AnchorTriplet` | NO | TRUE | test de projection/parité sans import actif de V2 |
| `MYPY-009` | `tests/calibration/pedagogical/anchor_corpus_v3.py:453` | `RC-02`, `RC-05` | V3 reste historique ; même contrat actif à cardinalité fixe | NO | TRUE | test de projection/parité V3 hors graphe actif |
| `MYPY-017` | `tests/calibration/pedagogical/anchor_corpus_v4.py:459` | `RC-02`, `RC-05` | V4 reste historique ; un loader d'input explicite produit le contrat actif | NO | TRUE | test de projection/parité V4 et hash guard |
| `MYPY-018` | `tests/calibration/pedagogical/call_plan.py:607` | `RC-03`, `RC-05` | `ApprovedBudget` est requis avant calcul ; aucune arithmétique sur `None` | NO | TRUE | `tests/unit/calibration_tooling/test_budget.py` |
| `MYPY-019` | `tests/calibration/pedagogical/call_plan.py:609` | `RC-03`, `RC-05` | garde de plafond non optionnelle et résultat monétaire exact | NO | TRUE | même test, plafond égal/dépassé |
| `MYPY-021` | `tests/calibration/pedagogical/call_plan_v4_1.py:218` | `RC-02`, `RC-03`, `RC-05` | V4.1 reste historique ; le runner unique utilise le budget actif commun | NO | TRUE | test budget + hash guard V4.1 |
| `MYPY-022` | `tests/calibration/pedagogical/call_plan_v4_1.py:220` | `RC-02`, `RC-03`, `RC-05` | même suppression de duplication dans le graphe actif | NO | TRUE | même test, absence de second calcul V4.1 |
| `MYPY-023` | `tests/calibration/pedagogical/review_contract_v4_2.py:20` | `RC-02`, `RC-04`, `RC-05` | import direct de `AnchorTier` depuis son module propriétaire actif, aucun réexport implicite | NO | TRUE | `tests/architecture/test_calibration_tooling_imports.py` |
| `MYPY-033` | `tests/calibration/pedagogical/semantic_gate_v5_2.py:738` | `RC-03`, `RC-05` | specs absolue/pairwise discriminées ; variables/handlers séparés | NO | TRUE | `tests/unit/calibration_tooling/test_runner_dispatch.py` |

## Commandes de gate futures

```powershell
.\.venv\Scripts\python.exe -m mypy backend --no-pretty --no-color-output --show-error-codes
.\.venv\Scripts\python.exe -m mypy --strict --explicit-package-bases --no-pretty --no-color-output --show-error-codes calibration_tooling tests/unit/calibration_tooling tests/integration/calibration_tooling
```

La seconde commande ne remplace pas silencieusement la reproduction historique :
le rapport final doit publier les deux résultats, `0` pour le graphe actif et
`15/10` attendu pour l'ancien root tant que ses octets sont protégés.

## Interdictions

- pas de `# type: ignore`, exclude mypy, per-module ignore ou `.pyi` qui masque
  l'implémentation historique ;
- pas de réécriture des 40 chemins gelés ;
- pas de changement du hash logique d'un corpus, call-spec, projection ou
  contrat 12.16 ;
- pas d'annonce « corrigé » pour le diagnostic source historique : seule sa
  disparition du graphe actif est revendiquée.
