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
C-05 EvidenceRequest
        ↓ CAP-E01
RetrievalCoordinationResult + RetrievalCandidate fusionné
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

Le caller fournit un `evidence_id` stable, le C-05 `EvidenceRequest`, le
`RetrievalCoordinationResult` produit pour cette demande et le candidat
fusionné à matérialiser. `EvidenceFetchRequest` ne possède aucun champ
`source_policy` indépendant.

Avant tout appel de contenu, la lignée impose l'égalité exacte de
`search_goal`, `scope`, `source_policy`, `filters` et `required_authority` entre
C-05 et la query du retrieval. Si le C-05 borne `max_items`, la query doit
rester bornée à une valeur inférieure ou égale ; si le C-05 ne le borne pas, le
bornage technique du coordinator est accepté. Un C-05 à zéro item exige un
retrieval vide. Toute divergence produit `RETRIEVAL_LINEAGE_MISMATCH`.

Le candidat doit appartenir exactement à `retrieval.ranked_candidates` avec la
même identité et le même rang technique. Une égalité de candidate ID ne suffit
pas. L'agent utilise alors uniquement le représentant déjà classé et construit
`DocumentContentRequest` avec ses candidate ID, source et locator exacts. Sa
`source_policy` est héritée de `retrieval.query.source_policy`, déjà prouvée
égale à celle de C-05 : elle ne peut pas être élargie par le caller.

Le résultat du port doit reproduire ces trois valeurs. Ce contrôle
anti-confused-deputy échoue avec `CONTENT_RESULT_MISMATCH` en cas de divergence.
Une `EvidenceContentUnavailable` qui cite un autre candidate ID échoue avec le
même code au lieu d'être traitée comme une indisponibilité normale.
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

`MaterializedEvidence.provenance` conserve sous forme immutable et agent-safe :

- le candidate ID, la clé d'identité et les canaux du retrieval ;
- la provenance et les metadata du candidat ;
- la provenance et les metadata du contenu ;
- la source, le locator et la version/checksum résolue.

Les mappings vides sont conservés tels quels. Le contenu complet et l'extrait
ne sont jamais recopiés dans ce mapping. `source_kind` demeure la qualification
retournée par l'accès de contenu ; elle n'est pas forcée à égaler celle du
candidat.

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
`EvidenceSetBuildRequest` réapplique aussi la validation C-05 → retrieval et
refuse ainsi un résultat provenant d'une autre demande. L'agent ne fabrique ni
timestamp ni identité.

Le set ordonne les items par rang technique et expose :

- `coverage` : statut, comptes, IDs manquants, dégradation et assessment flags ;
- `conflicts` : divergences de versions structurées ;
- `limitations` : mappings contenant uniquement un code stable ;
- `provenance_summary` : AG-02, capabilities, mode/canaux, versions, fraîcheur
  et `item_lineage` ordonnée par rang technique ;
- `retrieval_metrics` : comptes de candidats, matérialisations et résultats par canal.

Chaque entrée `item_lineage` conserve evidence ID, rang, source, locator,
version, canaux et provenances candidat/contenu. Elle n'embarque ni contenu ni
`excerpt_or_summary`. Les mappings ouverts de C-06 suffisent ; aucun contrat
C-06 n'est modifié.

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
