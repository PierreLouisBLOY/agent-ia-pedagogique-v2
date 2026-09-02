# Phase 12.17.2A — Preuve `TYPE_SYSTEM_ONLY`

## Nature du diff final

Le diff final contient uniquement :

- la suppression de casts et d'un ignore que mypy démontre redondants;
- une annotation locale portant l'union exacte des deux types déjà construits;
- le renommage d'une variable locale entre deux boucles de dataclasses distinctes;
- la suppression de deux imports `cast` devenus inutilisés.

Aucune constante, donnée pédagogique, condition, branche, appel, montant, schéma, route, payload, règle métier ou accès SQLite n'est modifié.

## Preuve comportementale

- Les `146` tests ciblés passent après le diff final.
- Ces tests incluent les gates de hashes et identités V4.2/V5, les corpus, le protocole, les pilotes, les enveloppes de transfert et le contrat pairwise V5.2.4.
- Ruff et `compileall` passent sur les neuf modules modifiés.
- Le backend reste à `0 erreur / 659 fichiers`.
- Aucun appel provider et aucune résolution de credential n'ont été effectués.

## Rollback probant de MYPY-001

Le retrait initial du cast à la ligne 88 de `tests/providers/anthropic/transport.py` a fait échouer la gate V4.2 avec `RepairPlanError: MATRIX_MISMATCH` après `71` tests passés. L'analyse a confirmé que ce fichier appartient à `_ANTHROPIC_CONTRACT_PATHS` et que ses octets alimentent les identités de call-spec.

Ce changement a été intégralement annulé. Le lot final conserve ainsi les identités historiques et déclare `MYPY-001` à 12.17.4, où la relation entre identité, preuve historique et placement du provider tooling pourra être décidée explicitement.

`TYPE_SYSTEM_ONLY = TRUE`
