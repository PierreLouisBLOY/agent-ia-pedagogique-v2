# Phase 12.17.1 — Recommandation de sous-étape suivante

## Recommandation

`NEXT_RECOMMENDED_SUBSTEP = 12.17.2 — AUDIT MYPY / QUALITÉ STATIQUE`

La dette historique est reproductible, bornée et suffisamment structurée pour un lot dédié. La prochaine sous-étape devrait classifier puis disposer les huit findings `TYP-*`, sans ouvrir simultanément la rationalisation métier, l'API ou les migrations.

## Ordre proposé pour 12.17.2

1. Verrouiller les deux commandes mypy et leurs périmètres respectifs.
2. Séparer erreurs racines et erreurs en cascade.
3. Prouver les corrections purement statiques qui conservent les bytes/checksums historiques.
4. Soumettre à décision propriétaire tout changement touchant une identité de corpus, matrice, budget ou carry-forward.
5. Exécuter les tests ciblés des helpers concernés, mypy backend et la traversée calibration import-driven.
6. Rapporter la dette résiduelle explicitement acceptée ou différée.

## Priorité initiale suggérée

- `TYP-002` : annotation fail-closed du scorer Anthropic;
- `TYP-004` : sept erreurs en cascade dues au réemploi d'une variable;
- `TYP-005` : narrowing du plafond budgétaire dupliqué;
- `TYP-008` : union d'identités carry-forward;
- puis cardinalité, observation union et casts obsolètes.

Ce document n'autorise aucune correction. Les audits 12.17.3 à 12.17.6 restent nécessaires après disposition de la dette statique.
