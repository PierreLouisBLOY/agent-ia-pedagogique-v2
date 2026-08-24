# Instructions persistantes pour les agents de code

Ces regles s'appliquent a tout agent de code intervenant dans ce depot.

1. Les livrables canoniques V2 priment sur les preferences de code, d'outil ou de framework.
2. Aucun element de V1 n'est herite implicitement. Toute reutilisation suit le processus explicite decrit dans le README.
3. Les frontieres validees en Phases 6 et 11 ne sont jamais modifiees silencieusement.
4. Un agent ne dispose d'aucun acces direct a SQL, aux repositories, aux secrets ou au filesystem metier. Il consomme les use cases Application via une frontiere inbound.
5. Generation, validation, evaluation de la qualite et promotion sont des responsabilites distinctes.
6. Chaque lot reste minimal, coherent et limite a son objectif declare.
7. Les tests, le lint et le typecheck applicables sont executes avant toute declaration de reussite.
8. Aucune donnee runtime, base binaire, sortie generee ou secret ne doit entrer dans Git.
9. Toute deviation architecturale exige un ADR explicite, relu avant implementation.
10. Un test ne peut etre annonce PASS que s'il a reellement ete execute avec succes.

## Regles de dependance

- Le metier appartient aux modules sous `backend/modules/`.
- `backend/shared_kernel/` reste generique et ne contient aucun concept metier specialise.
- Les adaptateurs et l'infrastructure restent hors des modules metier.
- Les contrats ne dependent d'aucun type HTTP, ORM ou SDK fournisseur.
- Aucun framework, fournisseur externe ou dependance runtime n'est introduit sans decision canonique.
- Les outils agents entrent par `backend/adapters/inbound/agent_tools/` et n'acquierent aucune autorite metier.

## Discipline de livraison

Avant de conclure un lot, verifier le diff, l'absence de secrets et de donnees runtime, puis executer les validations documentees dans `docs/development/ENVIRONMENT.md`. Ne pas merger une branche de travail sans revue explicite.
