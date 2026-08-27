# Baseline Phase 12.12-F — Secrets, exfiltration et limites

## Périmètre livré

Le lot F part directement du commit E
`1942a4017524d11ee4782116a20fbdce1fbdb0e7` sur
`phase12/12-12-security-hardening`.

Il livre :

```text
audit des surfaces de fuite contractuelles
+ classification locale de valeurs sensibles
+ isolation raw-free et mappings SecurityEvent fermés
+ minimisation ErrorEnvelope et SecurityEvent
+ sécurité par valeur des sorties Tool/Application/Agent
+ limites profondeur/cardinalité/string/refs/nœuds
+ contrôle des chemins privés et refs d'artifact
+ tests synthétiques d'exfiltration et d'épuisement
+ fitness d'architecture
```

Il ne livre ni infrastructure de stockage de secrets, ni intégration globale
runtime/recovery G, ni observabilité 12.13, ni calibration 12.16.

## Audit des surfaces

| Surface | Texte/valeur | Structure/refs | Décision F |
| --- | --- | --- | --- |
| `freeze_safe_mapping` | valeurs auparavant non inspectées | gel et clés privées déjà canoniques | prévalidation générique, owner de gel conservé |
| `freeze_agent_safe_mapping` | raisonnement privé déjà rejeté par clé | mappings récursifs | profil agent + profils Error/Event |
| `ErrorEnvelope` | message libre, details | refs non bornées | message 1 024, details stricts, refs 16 |
| `SecurityEvent` | metadata sous clé neutre | refs 16, top keys 32 | contrôle des valeurs/nesting, refs opaques |
| `ApplicationFailure` / `BusinessError` | cause ref et details | mappings | valeur safe, gel existant conservé |
| `ToolCallResult` | output, metrics, error | artifact refs | contrôle F, maximum 64 artifacts |
| `ApplicationOutcome` / `UseCaseResult` | data, validation, failures | events, side effects, refs | contrôle F et cardinalités explicites |
| `AgentResult` | payload/dataclass, warnings, stop reason, error | artifact/Evidence refs | contrôle F, texte/refs bornés |
| délégation/handoff | contexte, contraintes, traces | Evidence refs | gel value-safe et maximum 64 refs |
| contenu/Evidence | texte, excerpt, locator | source/content refs | limites historiques et path safety |
| recovery | facts fermés, refs/fingerprints typés | checkpoint/snapshot/ledger | audit seulement, aucun changement |

Les surfaces `config/secrets` restent structurelles et ne gagnent aucun loader
concret. Aucun fichier `.env`, credential ou donnée runtime n'entre dans Git.

## Clés, valeurs et exfiltration

Le rejet de noms de clés reste chez `freeze_safe_mapping` et le rejet des clés
de raisonnement privé chez `freeze_agent_safe_mapping`. Le classifieur D reste
responsable des clés d'autorité. Le signal C `EXFILTRATION_TEXT` décrit une
demande présente dans un contenu.

F ajoute séparément `SensitiveValuePolicy`, qui détecte une valeur ressemblant
fortement à un credential, token d'authentification, clé privée, secret de
connexion ou chemin privé. Son résultat ne contient que la classe et une
position logique sûre. Aucun extrait ou fingerprint n'est produit.

```text
request "send secrets"       -> signal C, contenu isolé
valeur synthétique détectée  -> rejet F, aucun raw propagé
combinaison explicite        -> SECRET_EXFILTRATION_ATTEMPT minimisé
```

## Matrice des limites

| Surface | Limite | Owner | Pertinence sécurité | Verdict |
| --- | --- | --- | --- | --- |
| structured data générique | depth 16, mapping 256, sequence 512, string 65 536, nodes 4 096 | shared validation appelée par safe mapping | bombes et valeurs sur Tool/Application/Agent | nouveau profil F partagé |
| `ErrorEnvelope.details` | depth 8, mapping 64, sequence 64, string 2 048, nodes 1 024 | contrat Error | diagnostic borné | profil F spécialisé |
| `ErrorEnvelope.message/refs` | 1 024 caractères / 16 refs | contrat Error | leak et amplification | ajouté F |
| `SecurityEvent.metadata` | depth 8, mapping 32, sequence 64, string 512, nodes 512 | contrat Event | événement minimal | top 32 historique conservé, nesting ajouté |
| `SecurityEvent` refs/IDs | 16 refs, ref 256, ID 128 | contrat Event | pas de path/raw/amplification | conservé et durci par valeur |
| Tool result | profil générique, 64 artifact refs | contrat Tool | output/path leakage | ajouté F |
| Application outcome | 128 errors/warnings, 512 side effects/subjects | core outcome | output amplification | ajouté F, unités distinctes |
| Use-case result | 64 domain events | contrat Application | propagation inter-boundary | ajouté F |
| Agent result | 64 artifacts, 64 Evidence refs, 64 warnings, stop 1 024 | contrat Agent | handoff/output leakage | ajouté F |
| délégation | depth spécialiste 1, runtime max 2, 64 Evidence refs | E + runtime policy | scope et amplification | profondeur conservée, refs ajoutées |
| contenu labellisé | 65 536 caractères | contrat Content | texte boundary | aligné profil F |
| Evidence | max 12/set, excerpt 4 000 | policy/contrat Evidence | coût et citation | conservé, non fusionné |
| runtime | 24 steps/run | runtime policy | coût d'exécution | conservé, hors profil F |
| sandbox | 25 MiB input, 50 MiB output, 20 fichiers, path 1 024 | SandboxPolicy/profile | filesystem/resource | conservé, non fusionné |
| snapshot fingerprint | entrée 65 536 octets | recovery snapshot | hash déterministe | conservé, non fusionné |

Les limites de tokens, secondes, coût, contexte modèle et fournisseur restent
hors du profil structurel F.

## Minimisation des erreurs et événements

Un `ErrorEnvelope` agent-safe refuse désormais une valeur synthétique dans son
message, ses détails ou ses refs. Le rejet est borné et ne renvoie jamais la valeur.
`ApplicationFailure` et `BusinessError` conservent catégories, retry et effect
state ; seules leurs données libres sont inspectées.

Un `SecurityEvent` refuse une valeur sensible même sous une clé neutre telle
que `note`. Les factories F réutilisent `SECRET_EXPOSURE`,
`SECRET_EXFILTRATION_ATTEMPT` et `INPUT_LIMIT_EXCEEDED`. Metadata et message
d'exception ne contiennent que codes, classes et locations logiques.

## Sorties et provenance

Tool, Application et Agent refusent les valeurs sensibles avant propagation
vers Generation, Review ou le prochain agent. La fonction de frontière D est
réutilisée ; les labels `TOOL_OUTPUT`, `APPLICATION_OUTPUT`, `AGENT_OUTPUT`,
`REVIEW_OUTPUT` et `CORRECTION_OUTPUT` restent inchangés. F n'autorise, ne
valide et ne promeut aucun contenu.

Les mappings imbriqués et les payloads dataclass sont inspectés. Warning,
message d'erreur, details, filename/ref d'artifact et chemin privé sont des
canaux testés. Les refs logiques opaques et chemins relatifs validés par le
sandbox restent permis.

## Faux positifs et fixtures

Les fixtures assemblent uniquement des marqueurs synthétiques de clé privée,
Bearer, API credential et connexion. Les tests prouvent l'absence du raw dans
les assessments, exceptions et événements.

Restent acceptés : SHA-256, UUID, `ContractRef`, code source parlant
d'`api_key`, `password = example`, texte légal/cyber, checksum/version et
fingerprint d'idempotence. Aucun score ML, dépendance DLP ou appel externe
n'est utilisé.

## Épuisement et fail-closed

Les tests couvrent profondeur, mapping keys, séquence, chaîne, total de nœuds,
cycle, refs, metadata Event et details Error. Le parcours itératif refuse avant
récursion incontrôlée ou invocation externe. Les erreurs exposent seulement le
code de limite et une position logique bornée.

## Recovery, architecture et dépendances

`RetryFailureFacts`, `RecoveryCheckpoint`, `StateSnapshot` et
`EffectLedgerRecord` conservent leurs projections fermées, refs typées et
fingerprints bornés. Aucun fichier recovery n'est modifié ; retry, replay,
reconciliation et circuit breaker sont inchangés.

Les fitness tests prouvent l'unicité du gel canonique, de la façade F et du
profil de limites, la réutilisation de C/D/E et l'absence de SecretStore,
Vault, KMS, provider SDK, réseau, sink, observabilité ou dépendance runtime.
`[project].dependencies` reste `[]`.

## Validations de clôture

```text
Python                          3.12.x
tests ciblés F                  36 passed
régressions B/C/D/E/recovery   255 passed
fitness ciblée                  24 passed
suite globale                 3284 passed
compileall backend              PASS
Ruff                            PASS
mypy backend                    PASS
git diff --check                PASS
```

La suite globale et les chiffres ci-dessus sont les preuves de la clôture F ;
ils sont rejoués après finalisation documentaire et avant commit.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
