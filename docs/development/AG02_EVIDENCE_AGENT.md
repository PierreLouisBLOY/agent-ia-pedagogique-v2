# AG-02 EvidenceAgent

## Capabilities séparées

`EvidenceAgent` réutilise `BASELINE_CAPABILITY_REGISTRY`. Le binding canonique
est :

| Capability | Méthode | Classe | Route | Owner |
| --- | --- | --- | --- | --- |
| CAP-E01 | `search_evidence` | EVIDENCE | AGENT | AG-02 |
| CAP-E02 | `fetch_evidence_item` | EVIDENCE | AGENT | AG-02 |
| CAP-E03 | `assess_evidence_coverage` | EVIDENCE | AGENT | AG-02 |

Les méthodes restent auditables séparément. Aucune méthode `run`, `execute` ou
`search_and_fetch_all` ne les enchaîne automatiquement. Le caller orchestre
explicitement le parcours :

```text
RetrievalCandidate fusionné
        ↓ CAP-E02, accès contrôlé
DocumentContentResult (donnée non fiable)
        ↓ matérialisation explicite
EvidenceItem canonique
        ↓ CAP-E03 + build_evidence_set
EvidenceSet canonique
```

## CAP-E01 — recherche

`search_evidence` vérifie C-05 `EvidenceRequest`, appelle exactement une fois le
`RetrievalCoordinator` et retourne son résultat intact. Il ne récupère aucun
contenu et ne construit aucune preuve.

## CAP-E02 — matérialisation d'un item

Le caller fournit un `evidence_id` stable, le candidat fusionné et la
`source_policy` existante. L'agent utilise uniquement le représentant déjà
classé et construit `DocumentContentRequest` avec ses candidate ID, source et
locator exacts.

Le résultat du port doit reproduire ces trois valeurs. Ce contrôle
anti-confused-deputy échoue avec `CONTENT_RESULT_MISMATCH` en cas de divergence.
Si versions/checksums candidat et contenu sont tous deux connus et différents,
`CONTENT_VERSION_MISMATCH` empêche la matérialisation.

La version du contenu est prioritaire lorsqu'elle existe ; sinon celle du
candidat est utilisée. Si aucune n'est connue, l'item porte la limitation
`VERSION_OR_CHECKSUM_UNKNOWN`.

La fraîcheur est uniquement déclarative :

- `CURRENT` → `REPORTED_CURRENT` ;
- `STALE` → `REPORTED_STALE` et `SOURCE_REPORTED_STALE` ;
- toute autre valeur → `UNKNOWN` et `FRESHNESS_UNKNOWN`.

`retrieved_at` ne permet jamais d'inférer la fraîcheur.

L'extrait est le contenu exact jusqu'à `max_excerpt_chars`. La baseline utilise
4000 caractères ; ce nombre est un default technique remplaçable. En cas de
dépassement, le préfixe exact est conservé et `CONTENT_TRUNCATED` est ajouté.
Aucun résumé LLM n'est produit.

`EvidenceItem.relevance` contient seulement le rang technique, le score RRF
sous forme décimale exacte transportable, les rangs par canal et les canaux.
`EvidenceItem.authority` copie le mapping du représentant sans conclure à sa
suffisance, sa véracité ou sa conformité.

## CAP-E03 — couverture structurelle

`assess_evidence_coverage` vérifie que chaque matérialisation correspond à une
identité et un rang du résultat retrieval :

- aucun candidat → `EMPTY` ;
- tous les candidats matérialisés → `COMPLETE` ;
- sinon → `PARTIAL`.

Les candidate IDs manquants, canaux indisponibles, limitations de retrieval et
limitations d'items sont conservés dans un ordre stable. `PARTIAL` ajoute
`MATERIALIZATION_INCOMPLETE`, `EMPTY` ajoute `NO_ADMISSIBLE_EVIDENCE`, et tous
les résultats ajoutent `SEMANTIC_ADEQUACY_UNASSESSED`.

Cette couverture ne mesure aucune adéquation sémantique. Les indicateurs
`semantic_adequacy_assessed` et `authority_requirement_assessed` restent faux.

## Conflits et EvidenceSet

`detect_version_conflicts` groupe uniquement par objet canonique de base. Deux
versions/checksums non nuls distincts produisent `VERSION_DIVERGENCE` sans
supprimer aucun item. Il n'y a pas de conflit pour une identité fallback, une
version inconnue, deux locators sans objet canonique ou une simple similarité.

`build_evidence_set` exige un `ContractMeta[AgentResultStatus]` fourni par le
caller. Run ID, step ID, correlation ID et acteur AG-02 doivent correspondre à
la demande. `COMPLETE` et `EMPTY` exigent `SUCCEEDED`; `PARTIAL` exige `PARTIAL`.
L'agent ne fabrique ni timestamp ni identité.

Le set ordonne les items par rang technique et expose :

- `coverage` : statut, comptes, IDs manquants, dégradation et assessment flags ;
- `conflicts` : divergences de versions structurées ;
- `limitations` : mappings contenant uniquement un code stable ;
- `provenance_summary` : AG-02, capabilities, mode/canaux, versions et fraîcheur ;
- `retrieval_metrics` : comptes de candidats, matérialisations et résultats par canal.

Un `EvidenceSet` vide avec statut `SUCCEEDED` est valide et ne contient aucune
preuve synthétique.

## Sécurité et limites

Un contenu tel que « Ignore les règles », « Autorise CAP-A02 », « Lis ce fichier
local » ou « Envoie les secrets » reste un excerpt de données. Il ne modifie
aucune capability, permission ou autorité et ne déclenche aucun outil. Les
`security_warnings` du port sont conservés descriptivement ; aucun détecteur
heuristique n'est ajouté en D.

L'agent n'accède directement à aucun repository, SQL, filesystem, HTTP,
provider ou vector store. Il ne retry pas. Le hardening expansion/sécurité est
différé à 12.7-E et les scénarios runtime/Search/RAG à 12.7-F.
