# Phase 12.16-G2-V5 — Live readiness

## Décision

`V5_LIVE_READINESS = GO_FOR_OWNER_REVIEW`

Cette décision signifie que le contrat offline est assez cohérent et discriminant pour être soumis au propriétaire. Elle ne signifie pas `LIVE_READY`, ne crée aucune matrice live et n'autorise aucun provider call.

## Gates d'entrée

| Gate | Preuve | Verdict |
|---|---|---|
| Aucune inversion synthétique | 0 sur 16 triplets | PASS |
| Monotonie recommandée | 16/16 | PASS |
| Niveaux intermédiaires | niveaux 1, 2 et 3 atteints 16 fois chacun | PASS |
| Distribution non quasi binaire | 48/96 scores intermédiaires | PASS |
| Pairwise contrôlé | 64/64 correct | PASS |
| Tie strict | 0 faux tie; tie matériel rejeté | PASS |
| Parser/schema | round-trip et cas invalides couverts | PASS |
| Anchor blinding | 0 fuite sur 48 observations | PASS |
| Corpus historique | hash V4 inchangé | PASS |
| Fail-closed live | constante false et exception dédiée | PASS |

## Limite avant toute proposition live

Le lot ne démontre pas le classement sémantique des 24 anchors par un modèle réel. Cette démonstration n'est pas remplaçable par un score manuel dérivé des tiers, qui serait circulaire.

Avant toute préparation de live, le propriétaire doit donc :

1. revoir les 16 rubriques et leurs quatre contrôles ;
2. confirmer que les niveaux 4/2/1 représentent bien les rôles Strong/Mixed/Weak souhaités ;
3. prévalider aveuglément les 48 projections anchor/critère avec le contrat V5 ;
4. confirmer ou réviser séparément les anchors historiquement ambigus, sans muter V4 ;
5. versionner tout nouveau corpus sous V5 ;
6. approuver une future implémentation de mapping provider distincte ;
7. approuver matrice, pricing, plafond, transferts et autorisation live dans des actes séparés.

## Dette historique non bloquante pour la revue propriétaire

Le mypy ciblé V5 est PASS. Le suivi complet des imports expose 13 erreurs préexistantes dans cinq modules V2–V4 non modifiés. Cette dette est déclarée, mais elle n'altère ni les tests V5 ni les invariants du nouveau contrat. Une correction éventuelle doit faire l'objet d'un lot séparé afin de respecter l'interdiction de modifier silencieusement l'historique.

## Interdictions maintenues

- aucun seuil de release adopté ;
- aucun changement de route provider ;
- aucun mapping Anthropic ou OpenAI V5 ;
- aucun pricing ou plafond ;
- aucune autorisation de transfert ;
- aucune résolution de credential ;
- aucun live, retry ou rerun.

`LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`

## Prochaine gate proposée

`NEXT_GATE = 12.16-G2-V5-OWNER-RUBRIC-AND-ANCHOR-PREVALIDATION_READY`

Cette prochaine gate est une recommandation de gouvernance, pas une décision propriétaire déjà prise.
