# ADR P12-013 - Matérialisation canonique des preuves par AG-02

## Statut

Accepté.

## Contexte

Les lots 12.7-B et 12.7-C séparent les candidats de recherche, l'accès
documentaire contrôlé et la coordination hybride. Aucun de ces objets n'est une
preuve C-06. Il manque la responsabilité AG-02 qui matérialise explicitement un
contenu récupéré en `EvidenceItem`, évalue la couverture structurelle puis
assemble un `EvidenceSet` canonique.

Cette matérialisation doit conserver les frontières de Phase 9 : un contenu
documentaire reste une donnée non fiable, un score de retrieval n'établit ni
vérité ni autorité, et une version incompatible ne peut être masquée. Elle doit
aussi rester read-only et ne recevoir aucune autorité métier ou d'exécution.

## Décision

`EvidenceAgent` matérialise trois capabilities du registry canonique, sans
registry locale : CAP-E01 `search_evidence`, CAP-E02 `fetch_evidence_item` et
CAP-E03 `assess_evidence_coverage`, toutes possédées par AG-02.

Ces responsabilités restent séparées. `search_evidence` délègue une fois au
`RetrievalCoordinator`. `fetch_evidence_item` utilise le représentant déjà
classé, construit une demande documentaire bornée et appelle une fois
`EvidenceDocumentContentPort`. `assess_evidence_coverage` mesure uniquement la
correspondance entre candidats classés et preuves matérialisées.
`build_evidence_set` assemble le contrat public sans appeler de port. Aucune
méthode automatique n'enchaîne les capabilities.

Le résultat documentaire doit correspondre exactement au candidate ID, à la
source et au locator demandés. Une divergence est rejetée comme
`CONTENT_RESULT_MISMATCH`. Lorsque versions candidate et contenu sont toutes
deux connues, elles doivent être égales. La version du contenu est retenue si
elle existe, sinon celle du candidat ; l'absence des deux reste explicite.

La fraîcheur est seulement rapportée depuis `candidate.metadata.freshness`.
Elle n'est jamais inférée depuis `retrieved_at`. L'autorité du représentant est
copiée sans calcul de véracité, conformité, confiance ou satisfaction de
`required_authority`.

Le contenu est conservé verbatim. La baseline borne l'extrait à 4000 caractères
et utilise le préfixe exact en cas de dépassement. `max_excerpt_chars=4000` est
un default technique remplaçable, pas un invariant métier. Aucun résumé LLM,
nettoyage heuristique, suivi d'URL ou interprétation d'instruction n'est permis.

La couverture `COMPLETE`, `PARTIAL` ou `EMPTY` est strictement structurelle.
L'adéquation sémantique et l'exigence d'autorité restent toujours non évaluées.
Un résultat vide est un succès valide sans preuve synthétique. Un échec de
contenu ne provoque aucun retry et peut conduire le caller à assembler un set
`PARTIAL`.

Les conflits regroupent uniquement les preuves ayant le même objet canonique de
base et au moins deux versions/checksums non nuls distincts. Toutes les versions
et preuves sont conservées dans `EvidenceSet.conflicts`; fallback identities,
versions inconnues et simple similarité ne créent aucun conflit.

Le `ContractMeta[AgentResultStatus]` est fourni par le caller. Run, step,
correlation, acteur AG-02 et statut doivent être cohérents ; l'agent ne lit
aucune horloge.

## Conséquences

- les contrats C-05/C-06 existants suffisent et ne sont pas modifiés ;
- le chemin candidat → contenu → `EvidenceItem` → `EvidenceSet` est explicite ;
- les avertissements de sécurité restent descriptifs dans les limitations ;
- le prompt injection reste du texte sans side effect ;
- aucun provider, SQL, filesystem, vector store, retry ou wiring runtime n'est
  introduit ;
- le durcissement expansion/sécurité est différé à 12.7-E ;
- les scénarios runtime/Search/RAG sont différés à 12.7-F.
