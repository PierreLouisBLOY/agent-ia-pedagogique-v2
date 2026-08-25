# Phase 12.7 — Baseline Evidence Retrieval AG-02

## Statut canonique du lot

La phase 12.7 ferme la frontière Search/RAG d’AG-02 sans fournisseur réel, sans accès direct aux données métier et sans dispatcher de production. Les capacités restent exactement `CAP-E01`, `CAP-E02` et `CAP-E03`, avec une séparation explicite entre recherche, matérialisation contrôlée et évaluation de couverture.

Le lot F est exclusivement un lot d’intégration, de fitness tests et de documentation. Il ne modifie aucun fichier sous `backend/`.

## Incréments B à E

- B fixe la frontière de retrieval provider-neutral : requête bornée, candidats techniques, résultats par canal et ports inbound contrôlés.
- C introduit le coordinateur déterministe : ordre `STRUCTURED`, `LEXICAL`, `RELATIONAL`, `SEMANTIC`, admissibilité structurée obligatoire, fusion RRF déterministe et dégradation explicite d’un canal optionnel.
- D matérialise un candidat par appel explicite au port documentaire et construit un `EvidenceSet` traçable, avec couverture structurelle, versions, conflits et provenance par item.
- D-correctif garantit que la source, la version et la provenance restent liées au candidat et au contenu effectivement matérialisés.
- E traite le contenu comme non fiable : scanner déterministe, signaux attribués, absence d’autorité documentaire, aucun suivi de lien et advisor d’expansion borné à trois tours.
- E-correctifs imposent l’attribution exacte des signaux de sécurité et vérifient la lineage de sécurité avant toute décision, dans un ordre sûr.

## Pipeline intégré Search/RAG

Le chemin testé utilise les objets de production réels et uniquement des adaptateurs de test déterministes :

`EvidenceRequest → EvidenceAgent.search_evidence → RetrievalCoordinator → EvidenceSearchPort fake → RetrievalCoordinationResult → EvidenceAgent.fetch_evidence_item (un appel explicite par candidat) → EvidenceDocumentContentPort fake → MaterializedEvidence → assess_evidence_coverage → build_evidence_set → EvidenceSecurityScanner → EvidenceExpansionAdvisor`.

Les scénarios couvrent le mode complet, la dégradation sémantique, le filtre dur d’admissibilité, les versions divergentes, l’injection documentaire, la matérialisation partielle, le résultat vide et les arrêts d’expansion. Les fakes enregistrent les appels et n’effectuent ni I/O, ni retry, ni appel fournisseur.

## Compatibilité avec les workflows

La sélection canonique, le compilateur de plan, le scheduler et le runtime déterministes sont exercés avec des runners et évaluateurs de complétion de test :

- WF-1 contient un unique step AG-02 / `CAP-E01` avec une référence opaque de permission.
- WF-4 enchaîne AG-02 puis AG-03 fake. Une association test-only peut relier un `result_ref` opaque à un `EvidenceSet` réel sans créer de dispatcher.
- WF-6 conserve l’ordre AG-02 → AG-03 → Application / `CAP-A01` → AG-04 et exclut `CAP-A02`.
- WF-8 matérialise cinq branches AG-02 d’indices 0 à 4, limitées à quatre lancements par cycle, puis un join `CAP-O04` dépendant des cinq branches. Une continuation WF-4 ou WF-6 commence après le join sans second step AG-02.
- Le scénario Search/RAG multi-branche conserve trois `EvidenceRequest` et trois sorties distinctes. Le join de test agrège seulement des références et résumés ; il ne fusionne pas des `EvidenceSet` canoniques et ne déclare aucune corroboration.

## Topologie et dispatch

Ces tests prouvent la compatibilité de topologie : sélection, compilation, dépendances, fan-out/fan-in, ordre déterministe et complétion via fakes. Ils ne prouvent pas et n’introduisent pas un dispatch de production. En particulier, aucun router, handler, store, moteur de workflow persistant ou boucle d’exécution métier n’est ajouté. Les capacités E02 et E03 ne sont jamais exécutées secrètement sous le seul libellé `CAP-E01` ; le pipeline de test les appelle explicitement.

## Garanties de sécurité et de lineage

L’admissibilité structurée précède toute matérialisation. Un score lexical, relationnel ou sémantique ne peut pas rendre une source admissible. Les identités incluent la version, les conflits restent visibles et aucun élément n’est supprimé automatiquement. Les instructions présentes dans un document restent des données : elles ne créent ni politique, ni permission, ni décision de gate, ni appel externe. L’expansion conserve le scope, la source policy, les filtres, l’autorité requise et le plafond initial ; elle propose seulement un prochain tour.

## Éléments différés

Restent hors de la phase 12.7 : adaptateurs de recherche ou de contenu réels, configuration fournisseur, persistance, dispatcher/worker de production, promotion et fusion sémantique de plusieurs `EvidenceSet`. Le séquencement canonique différé reste AG-03 en 12.8, AG-04 en 12.9, routing et gates en 12.10, résilience en 12.11, hardening global en 12.12, observabilité en 12.13 et E2E en 12.15. Toute évolution de ces sujets exige un lot canonique ultérieur et les décisions architecturales applicables.

## Rationalisation

Les incréments B à E composent déjà une frontière cohérente : les responsabilités sont séparées, les contrats sont réutilisés tels quels et les tests F exercent le chemin cumulé sans wrapper de production supplémentaire. Aucun renommage ou déplacement n’améliorerait la sûreté du lot de clôture.

`NO_SAFE_CONSOLIDATION_REQUIRED`
