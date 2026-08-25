# ADR-P12-020 — Frontière provider-neutral de review AG-04

## Statut

Accepté pour la Phase 12.9-B.

## Contexte

AG-04 possède les capabilities canoniques `CAP-V01 semantic_review` et
`CAP-V02 assess_findings`, mais la baseline 12.8 ne contient encore aucune
frontière de provider pour les exécuter. Les contrats C-09 `ReviewRequest` et
C-10 `ReviewResult`/`Finding` existent déjà et ne doivent être ni dupliqués ni
matérialisés directement par un provider.

## Décision

Le package `backend.agent_runtime.agents.review` introduit uniquement :

- `ReviewOperation`, avec `SEMANTIC_REVIEW` et `ASSESS_FINDINGS` ;
- `ReviewPortRequest`, snapshot technique immutable entièrement résolu par le caller ;
- `ReviewPortResult`, sortie technique non canonique ;
- des statuts et erreurs techniques fermés ;
- l'unique Protocol outbound `ReviewPort.review()`.

La capability reste un identifiant opaque dans cette frontière. Aucun mapping,
routage ou dispatcher CAP-V01/CAP-V02 n'est ajouté en B. Les dimensions viennent
du vocabulaire canonique existant. Les mappings réutilisent les primitives
agent-safe existantes.

## Schéma conceptuel

```text
caller / futur coordinator
        |
        v
ReviewPortRequest
        |
        v
ReviewPort (Protocol)
        |
        v
provider concret — DIFFÉRÉ
        |
        v
ReviewPortResult technique
        |
        v
revalidation/coordinator — DIFFÉRÉ 12.9-C+
```

## Invariants

- la cible est un `ObjectVersionRef` exact et sa représentation est caller-supplied ;
- les dimensions sont non vides, uniques et issues de `ReviewDimension` ;
- les evidence refs sont déjà résolues/autorisées et le port n'en élargit pas le scope ;
- requêtes et résultats sont frozen, slotted et profondément immutables ;
- les résultats sont techniques et ne contiennent aucun statut PASS/FAIL métier ;
- le vocabulaire d'autorité est refusé dans le contrat de sortie demandé et dans
  toutes les surfaces structurées du résultat ;
- les erreurs exposent uniquement un message fermé, sans contenu de production,
  evidence, secret ou raisonnement privé.

## Frontières d'autorité

Le lot B n'ajoute aucun provider concret, `ReviewerAgent`, coordinator, runtime
dispatch, recherche evidence, chargement de production, réseau, fichier métier,
SQL, ORM, vector store ou tool call. Il ne construit aucun `Finding`,
`ReviewResult` ou `CorrectionRequest` canonique. Il ne valide, ne promeut, ne
persiste et ne corrige aucune production.

Le contenu cible et les resolved inputs restent des données non fiables. La
présence d'une affirmation `validated`, `safe`, `trusted` ou `canonical` dans la
cible ne lui confère aucune autorité.

## Conséquences

Un futur coordinator peut injecter une implémentation de `ReviewPort` sans que le
core connaisse un SDK fournisseur. Le résultat conserve suffisamment de données
techniques pour une revalidation ultérieure, mais ne peut pas être confondu avec
C-10. `execution_metadata` est explicitement non autoritative et sera liée puis
revalidée avant toute matérialisation future.

La similarité avec les frontières evidence et génération ne justifie aucune
factorisation : leurs opérations, données et réactions de sécurité restent
distinctes.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```

## Responsabilités différées

- 12.9-C : préparation, résolution et coordinator ;
- 12.9-D : `ReviewerAgent` et matérialisation C-10 ;
- 12.9-E : assessment de findings et handoff de correction ;
- 12.9-F : sécurité, anti-forgery et lineage locator/evidence ;
- 12.9-G : intégration workflows et fitness ;
- 12.9-H : audit cumulatif et clôture.
