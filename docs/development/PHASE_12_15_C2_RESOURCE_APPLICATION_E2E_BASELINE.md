# Phase 12.15-C2 — Baseline Resource/Application sur SQLite réelle

## 1. Baseline et portée

C2 a pour parent exact `3fb936c92037cc707065677aaaa4f4ad111b743e`.
Le lot ferme uniquement SCN-01 par le chemin WF-0/Application et s'arrête avant
les scénarios D/E/F/G. Il ne crée ni provider, ni scorer, ni accès réseau, ni
nouveau SQL.

## 2. Hard gate canonique

| Source | Contrat réutilisé | Conséquence C2 |
| --- | --- | --- |
| Phase 5 | `READ-15`, identifiant `getResource`, UC-RESOURCE / SM-03, entrée `resource_ref`, sortie `ResourceView` | le use case existe ; C2 ne crée ni capability ni opération |
| Phase 5 | `RES_NOT_FOUND`, R-READ-03, R-READ-06, R-READ-09 | référence exacte, erreur fermée, séparation Resource/Production et identité stable |
| Phase 6 | M03 `resource_library`, IP-03 `ResourceLibraryInbound`, OP-03 `ResourceStorePort` | Application possède la lecture et dépend d'un port sortant typé |
| Phase 7/C0 | `ResourceStore.load_resource` et composition SQLite migrée | le mapper C2 réutilise OP-03 sans dupliquer la requête SQL |
| Phase 8 | API v2 projetée vers Application, sans accès repository/SQL | `getResource` reste l'operationId de compatibilité ; C2 ne matérialise pas d'endpoint HTTP |
| Phase 11 | P11-CORE-01/02/03 et WF-0 Application/direct | aucun agent n'acquiert d'autorité métier ou d'accès stockage |
| Phase 12.10 | `application.read_canonical_resource`, CAP-R01, C-12/C-13 | le routeur et sa policy existants restent inchangés |

Le paquet Phase 8 livré contient le document final et le gate XLSX, mais pas les
annexes OpenAPI YAML/JSON qu'il référence. Cette lacune de packaging n'autorise
aucun renommage : Phase 8 est une projection de la surface canonique et Phase 5
fixe déjà l'identifiant exact `getResource`. C2 conserve donc cette identité et
n'invente aucun contrat de transport.

La slice C2 matérialise le champ obligatoire `resource_ref`. Les variantes
optionnelles `version_ref` et `include` de READ-15 ne sont ni simulées ni déclarées
supportées par ce lot SCN-01.

## 3. Graphe de dépendance livré

```text
UseCaseRouter / CAP-R01 / C-12
  -> ResourceLibraryUseCaseInbound
       -> IP-03 ResourceLibraryInbound
            -> GetResourceQuery (M03 / UC-RESOURCE / READ-15)
                 -> OP-03 ResourceStorePort
                      -> SQLiteResourceStoreAdapter
                           -> ResourceStore.load_resource (C0) -> SQLite
  <- ApplicationOutcome<ResourceView> -> C-13 UseCaseResult
```

`backend/modules/resource_library` ne connaît ni SQLite, ni adapter, ni harness.
Le bridge C-12/C-13 ne connaît ni connexion, ni table, ni chemin. Le mapper
outbound transforme le dictionnaire C0 en `ResourceRecord` M03 et ne contient
aucune instruction SQL.

## 4. Contrat Application minimal

- `GetResourceRequest` porte une référence logique non vide ;
- `ResourceRecord` et `ResourceView` exposent seulement référence, type, titre
  canonique et statut d'identité ;
- une absence OP-03 retourne `ApplicationOutcome(REJECTED)` avec l'erreur métier
  fermée `RES_NOT_FOUND`, bloquante et non retryable ;
- un succès retourne un `ResourceView` typé, puis le bridge projette une mapping
  sûre C-13 ;
- aucun contenu documentaire brut, row SQLite, handle ou détail de connexion ne
  traverse la frontière.

La référence réelle stable de SCN-01 appartient au seed authentifié et vise un
`EXERCISE_SET` actif sur les fonctions du management. Le chemin privé du seed
n'est jamais inscrit dans Git.

## 5. SCN-01 full path

```text
CanonicalPedagogicalScenario SCN-01
-> EvaluationRunner
-> C2InputFactory / fixture déclarée
-> WorkflowSelector(application_action_required=True) -> WF-0
-> UseCaseRouter.route(CAP-R01)
-> CountingApplicationInbound -> ResourceLibraryUseCaseInbound
-> GetResourceQuery -> OP-03 -> runtime SQLite fraîche et migrée
-> UseCaseResult / ApplicationOutcome / ResourceView
-> EvaluationObservationSnapshot
-> 4 assertions hard -> Case/Suite PASS
-> JSON + Markdown en mémoire
```

Le compteur enveloppe l'inbound réel : il ne remplace ni le routeur ni le use
case. Une seule requête C-12 est observée et son objet est celui remis à IP-03.

## 6. Observations hard et minimisation

| Observation | Preuve |
| --- | --- |
| `scn-01.workflow` | sélection réelle et exclusive de `WF-0` |
| `scn-01.application-path` | `WF0_APPLICATION_GETRESOURCE_OP03_SQLITE` après résultat réel réussi |
| `scn-01.route-count` | séquence d'appels de longueur exacte 1 issue du wrapper d'inbound |
| `scn-01.resource-ref` | référence du résultat C-13 identique à celle de la requête |

Le titre réel lu par OP-03 n'entre dans aucune observation ni artefact de report ;
le gate vérifie son absence octet pour octet dans les sorties JSON et Markdown.
La rubric déclarative SCN-01 n'est pas exécutée : aucun scoring plan et aucun
scorer ne sont fournis.

## 7. Runtime réelle et fermeture

Chaque exécution réelle :

1. réauthentifie le seed Phase 3 immuable ;
2. crée une copie runtime neuve hors Git ;
3. applique la migration C0 et vérifie son ledger ;
4. ouvre OP-03 en lecture seule ;
5. exécute SCN-01 ;
6. ferme la connexion et supprime DB/WAL/SHM ;
7. réauthentifie le seed et compare l'évidence avant/après.

Le gate réel C2 a exécuté `1 passed` avec les quatre assertions PASS. Les gates
unitaires/intégration/fitness ciblés ont exécuté `7 passed`. La relance combinée
C0+C1+C2 sur le seed réel a exécuté `19 passed`.

La régression globale hors variable locale de seed a exécuté `3806 passed` et
`19 skipped` conditionnels ; ces 19 tests sont exactement ceux rejoués avec le
seed réel ci-dessus. `compileall backend`, Ruff global et mypy strict sur les
`638` sources backend passent également.

## 8. Décision ADR et handoff

`ADR_REQUIRED = NO`. C2 applique directement les décisions durables déjà figées
par les Phases 5, 6, 7, 8, 11, 12.10 et l'ADR C0 P12-056. Il n'introduit ni
nouvelle autorité, ni nouveau stockage, ni nouvelle sémantique de routing. Créer
un ADR supplémentaire ne ferait que dupliquer ces décisions.

Le statut historique `SCN_01_EXECUTION = DEFERRED` de la baseline C1 reste exact
pour C1. Le statut courant devient `SCN_01_EXECUTION = PASS_REAL_SQLITE_C2` dans
ce lot. La réouverture d'une runtime existante et les options version/include
restent hors périmètre ; aucune réussite n'est revendiquée pour elles.
