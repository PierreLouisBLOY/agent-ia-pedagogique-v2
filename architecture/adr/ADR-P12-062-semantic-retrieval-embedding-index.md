# ADR-P12-062 — Retrieval sémantique par embeddings et index dérivé

## Statut

Accepté — Phase 12.16-F2B.

## Contexte

Le corpus F1 immuable établit 25 gaps de paraphrase sémantique après le
découplage d'admissibilité F2A. STRUCTURED et LEXICAL ne suffisent pas à traiter
ces formulations, mais les frontières AG-02, l'identité canonique et le gate
d'admissibilité doivent rester souverains.

La comparaison live contrôlée de `text-embedding-3-small` et
`text-embedding-3-large`, à dimension 256 sur les mêmes 26 848 passages et 60
requêtes, a donné 14/25 gaps récupérés par Small contre 17/25 par Large. Large
est donc le gagnant lexicographique avant examen du coût.

La comparaison initiale révélait une perte F2A sur la requête `SI`. Le seed
authentifié prouve qu'il s'agit d'un alias actif de la notion canonique
`Système d’information`. La finalisation R2 généralise le traitement à tous les
alias actifs, sans modifier le corpus ou RRF, et obtient exact-label 100 %,
16/16 récupérations F2A et 17/25 gaps SEMANTIC.

## Décision

`text-embedding-3-large` est sélectionné comme modèle d'embedding. Il est
configuré par un `EmbeddingProfileConfig` dans l'owner provider existant et par
le workload technique `SEMANTIC_EMBEDDING`. Aucun capability ou registre
runtime supplémentaire n'est créé.

Le canal SEMANTIC reste une implémentation interne de l'actuel
`EvidenceSearchPort`. Chaque hit devient un `RetrievalCandidate` canonique et
passe le même `EvidenceAdmissibilityPort` que STRUCTURED et LEXICAL avant la
fusion RRF existante.

La projection déterministe v3 contient :

```text
canonical_object_ref
chunk_type
texte CURRENT
alias canoniques ACTIVE éventuels
contexte pédagogique canonique lié et borné éventuel
```

Une requête qui correspond exactement à un unique alias compact actif est
enrichie par son libellé canonique avant embedding. Les alias multi-mots restent
présents dans la projection v3 mais ne sont pas réécrits côté query dans ce lot.
Les alias et libellés proviennent du seed et sont ordonnés de manière
déterministe ; aucune query ou expected ref F1 n'est codée dans le mécanisme.
Le score SEMANTIC reste le cosine du vecteur réellement retourné et ne
constitue jamais une autorité.

## Stockage

L'index est un sidecar SQLite distinct, local, dérivé, non autoritatif,
reconstructible et non suivi par Git. Les vecteurs sont des BLOB float32
little-endian avec dimension explicite et norme pré-calculée. Une recherche
cosine exacte standard-library est retenue à l'échelle actuelle.

Le manifest lie au minimum :

- version de schéma et version de projection ;
- SHA-256 du seed canonique ;
- provider, modèle et dimension réellement obtenue ;
- nombre de passages et checksum du corpus projeté.

Le builder explicite écrit un fichier temporaire transactionnel, valide les
vecteurs, exécute `quick_check`, relit le manifest puis remplace atomiquement le
sidecar final. Aucun build n'a lieu à l'import ou dans un chemin de requête.

## Options rejetées

- Une base vectorielle externe ou une nouvelle dépendance : non justifiée pour
  26 848 vecteurs ; le scan local mesuré reste fonctionnel.
- Un embedding model représenté par `ModelProfileConfig` de génération : il
  imposerait de faux concepts comme `reserved_output_tokens`.
- Un tuning de `rrf_k`, `channel_limit` ou `final_limit` sur F1 : il déplacerait
  la frontière F2A et sur-ajusterait le benchmark.
- Une exception codée pour `SI` : la résolution d'alias doit rester canonique,
  générale et reproductible.

## Staleness et dégradation

Tout mismatch seed, modèle, dimension, schéma, projection, nombre de passages
ou checksum ferme le canal avec
`SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE`. L'index n'est jamais reconstruit dans la
requête.

SEMANTIC reste optionnel. Index absent ou stale, timeout, rate limit,
authentification ou indisponibilité provider deviennent une limitation explicite
du canal ; STRUCTURED et LEXICAL continuent. Le SDK est configuré avec
`max_retries=0` et aucune boucle de retry complexe n'est ajoutée.

## Revalidation

Le choix du modèle doit être réévalué si le corpus, les exigences de qualité,
le coût, la disponibilité régionale ou les capacités officielles changent
matériellement. Les prix sont des facts volatils documentés dans le rapport de
phase et ne sont pas des invariants de cet ADR.

## Conséquences

AG-02 dispose d'un signal sémantique réel sans second moteur métier, sans
élargissement d'autorité et sans mutation du seed. Le coût du run final Large
est supérieur à Small, mais le choix est justifié par le gain empirique sur les
gaps résiduels. L'index est un artefact d'exploitation à reconstruire et jamais
une source de vérité.
