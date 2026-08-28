# ADR-P12-056 — Intégration SQLite seed/runtime dans la composition

## Statut

Accepté pour la Phase 12.15-C0.

## Contexte

La Phase 3 livre un seed SQLite immuable identifié par taille et SHA-256. La
Phase 7 a ensuite versionné une migration corrective SHA-256 et fermé les
contrats OP-01 à OP-13. Exiger que le binaire Phase 3 contienne déjà cette
migration est contradictoire : toute migration change son identité binaire.

## Décision

1. Le seed Phase 3 et la base runtime sont deux concepts distincts.
2. Le seed est authentifié et ouvert exclusivement en lecture seule. Il n'est
   jamais migré, écrasé, utilisé comme fixture mutante ou suivi par Git.
3. Le bootstrap copie le seed vers une destination runtime configurable, puis
   applique les migrations SQL Phase 7 par version et checksum.
4. Le checksum `001` porte sur l'octet exact récupéré du commit historique
   `98d8464232f3cea21f7ac911c268b1ad8e675e0d`.
5. La migration et son entrée de ledger sont atomiques. Une version déjà vue
   avec un autre checksum bloque le démarrage.
6. Le fichier runtime reçoit un checkpoint WAL après bootstrap afin que son
   hash de preuve et ses copies incluent effectivement le schéma migré.
7. Les connexions mutables activent les clés étrangères, un busy timeout borné
   et WAL. OP-10 ouvre `BEGIN IMMEDIATE`; les stores ne commitent jamais.
8. Les neuf stores restent propriétaires. Un Data Mapper transforme les rows
   SQLite en records simples ; aucune row ne traverse l'adapter.
9. OP-11 est une lecture FTS5 dérivée et retourne des candidats non
   autoritatifs avec une `passage_ref` logique.
10. OP-12 reste une projection dérivée. OP-13 retourne seulement des fragments
    et références logiques, jamais URL, chemin, handle ou identifiant provider.
11. La composition root connaît les chemins seed/runtime. Les agents et le
    cœur Application ne connaissent ni `sqlite3`, ni table, ni chemin local.
12. PostgreSQL reste une cible de portabilité Phase 7 ; SQLite n'est pas
    redécidé ici.

## Conséquences

Le hash runtime est une preuve d'instance dérivée, pas une nouvelle identité
canonique Phase 3. Deux tables techniques préfixées `_runtime_` portent le
ledger et les marqueurs d'opération ; l'inventaire métier demeure celui des 98
tables du seed. C1 peut utiliser OP-11 puis résoudre la `passage_ref` inline par
OP-13 sans provider ni accès filesystem métier.
