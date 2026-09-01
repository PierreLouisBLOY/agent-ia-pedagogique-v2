# Phase 12.16-G2-V4.2 — Preuve d'exécution de la repair tranche

## Run unique

- run id : `12.16-g2-v4-2-live` ;
- début du premier appel : `2026-09-01T12:34:43+00:00` ;
- fin du dernier appel : `2026-09-01T12:37:15+00:00` ;
- exécution : strictement séquentielle ;
- appels réseau tentés : 39/39 ;
- retries automatiques : 0 ;
- reruns : 0.

| Provider | Completed | Failed | Skipped | Total |
| --- | ---: | ---: | ---: | ---: |
| OpenAI | 20 | 0 | 0 | 20 |
| Anthropic | 19 | 0 | 0 | 19 |
| Total | 39 | 0 | 0 | 39 |

Répartition OpenAI : 8 generation, 2 transformation, 3 correction et 7 Review.
Répartition Anthropic : 1 nouvelle exécution de l'ancien scoring server-error et 18
scorings des nouvelles sorties OpenAI.

Les 7 Reviews sont `COMPLETED`, avec structured validation `PASSED` et classification
de troncature `OTHER`. Aucune n'a atteint une condition de troncature confirmée ou
suspectée.

Le stockage local contient 39 sorties brutes JSON sous le dossier ignoré du run V4.2.
Le safe report n'embarque pas ces contenus : il conserve uniquement les statuts,
mesures, hashes et éléments de provenance nécessaires.

Les artefacts historiques V4.1 restent inchangés et aucun call carry-forward n'a été
réémis.
