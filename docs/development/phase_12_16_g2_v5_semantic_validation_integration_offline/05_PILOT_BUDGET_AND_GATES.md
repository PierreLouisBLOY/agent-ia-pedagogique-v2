# Phase 12.16-G2-V5 — Budget pilote et gates

## Source pricing

`PRICING_SHA256 = 31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`.

Le modèle planifié est `claude-sonnet-5` : 2 USD/M tokens input et 10 USD/M tokens output. L'estimation de base applique `bytes / 4` à l'input et `max_output_tokens / 2` à l'output. Le maximum technique applique `bytes / 1` et tout le budget output. La marge est 25 %.

| Pilote | OpenAI | Anthropic | Base estimée USD | Max avant marge USD | Marge USD | `PROPOSED_PILOT_CEILING_USD` |
|---|---:|---:|---:|---:|---:|---:|
| Minimal | 0 | 4 | 0.058960 | 0.153920 | 0.038480 | 0.192400 |
| Robuste | 0 | 21 | 0.311040 | 0.814080 | 0.203520 | 1.017600 |

Pour les deux options : `APPROVED_PILOT_CEILING_USD = NONE`.

## Gates d'acceptation diagnostique

Un rapport complet ne peut être `V5_SEMANTIC_PILOT_PASS` que si :

1. chaque nouvel appel prévu a une réponse parsée par le schéma V5 attendu ;
2. aucun score absolu n'est `INCONCLUSIVE` ;
3. chaque triplet couvert respecte strictement `Strong > Mixed > Weak` ;
4. aucune inversion Mixed/Weak n'est observée ;
5. au moins un niveau intermédiaire 1, 2 ou 3 est réellement utilisé ;
6. les résultats ne sont donc pas exclusivement extrêmes 0/4 ;
7. chaque pairwise correspond à son verdict de contrôle et n'est pas dégénéré ;
8. la provenance V4.2/V5 et le carry-forward de 20 records sont intacts ;
9. les canaries passent avant tout fanout.

Une exécution partielle ou un outcome sémantique `INCONCLUSIVE` produit `V5_SEMANTIC_PILOT_INCONCLUSIVE`. Une exécution complète qui viole une gate produit `V5_SEMANTIC_PILOT_FAIL`.

## Préflight avant credential

Les identités suivantes sont validées avant toute autorisation de call :

- baseline commit `a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b` ;
- matrice `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c` ;
- pricing `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` ;
- manifest offline V5 `2b86d0de9a3da8db87a8d55a6a3bfeb60fcdb0eead46b52178bdb6a9323d74c2` ;
- contrat scorer `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`.

Les doublons, reruns implicites, plafonds absents ou insuffisants et fanout précoce sont interdits. Le live reste fermé par défaut.

