# Événements SQLite, provider et sécurité

La factory SQLite accepte une session d'observabilité optionnelle et émet les transitions bootstrap/migration. Les opérations de backup/restauration exposées par la composition émettent uniquement un digest d'artefact ou un code d'erreur fermé. Aucun chemin, row ou contenu SQLite n'est journalisé.

Le runtime de calibration émet autour de chaque appel autorisé les états started/completed/failed. Le parser Anthropic remonte les compteurs de tokens déjà présents dans la réponse structurée ; l'événement completed contient les compteurs et le coût mesuré, jamais la requête, la projection pédagogique ou la réponse brute. Les tests utilisent un client et un transport synthétiques ; aucun credential n'est résolu.

Les rejets de frontière filesystem et runtime disposent de codes fermés et d'un correlation id optionnel. Les messages techniques bruts ne franchissent pas cette frontière.

```text
SQLITE_FIXTURES = TEMPORARY_ONLY
CANONICAL_SEED_WRITES = 0
USER_RUNTIME_WRITES = 0
PROVIDER_CALLS = 0
```
