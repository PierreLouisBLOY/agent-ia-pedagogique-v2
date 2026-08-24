# Agent IA pédagogique — Projet V2

Nouvelle implémentation du projet d'agent IA pédagogique.

## Principe fondateur : non-héritage de V1

V2 repart d'une base propre.

**Aucun fichier, code, configuration, dépendance, choix d'architecture ou règle technique provenant de V1 n'est repris automatiquement.**

Toute réutilisation d'un élément de V1 doit être :

1. identifiée explicitement ;
2. auditée ;
3. justifiée par les besoins et livrables canoniques de V2 ;
4. validée avant intégration ;
5. tracée dans `docs/legacy-review/`.

### Exception initiale explicitement autorisée

La base pédagogique SQL canonique est l'actif métier destiné à être conservé. Elle doit néanmoins faire l'objet d'un audit d'intégrité, de structure et de compatibilité avant son intégration opérationnelle dans V2.

Le fichier de base de données n'est pas ajouté par ce commit initial.

Aucun fichier de base de données runtime n'est stocké dans ce dépôt. `database/reference/` pourra contenir des manifests, checksums et documents validés, jamais la base binaire elle-même.

## Sources de vérité

Les spécifications et livrables canoniques validés de Projet V2 gouvernent la reconstruction. L'ancien dépôt V1 constitue uniquement une référence historique et ne doit pas servir de source implicite de code.

## Structure cible initiale

- `docs/architecture/` — architecture validée de V2
- `docs/decisions/` — décisions d'architecture et de conception
- `docs/phases/` — livrables et traçabilité des phases
- `docs/legacy-review/` — audits explicites des éléments éventuellement repris de V1
- `database/reference/` — actifs de données de référence validés
- `database/schema/` — schéma reproductible
- `database/migrations/` — migrations versionnées
- `database/validation/` — contrôles et audits de données
- `backend/` — nouvelle implémentation backend
- `frontend/` — nouvelle implémentation frontend
- `agents/` — nouvelle architecture agentique
- `tests/` — tests V2
- `scripts/` — scripts d'administration et de développement validés

Les répertoires seront matérialisés lorsqu'ils contiendront leur premier artefact validé ; aucun code squelette V1 n'est importé pour les créer.

## Baseline Phase 12.2

- `backend/` contient le code source Python et les frontières Phase 6.15 ;
- `tests/` contient les gardes architecturales et les futurs niveaux de test ;
- `architecture/adr/` contient les décisions d'architecture ;
- `docs/development/` contient la documentation de développement ;
- les données runtime, bases, logs, exports et artefacts restent hors du dépôt ;
- les futurs outils agents entreront par `backend/adapters/inbound/agent_tools/` et consommeront les use cases Application ;
- la base pédagogique fera l'objet d'une intégration future, auditée et distincte de cette baseline.

Aucun agent, framework, provider LLM, ORM, vector store ou mécanisme de secrets n'est implémenté en Phase 12.2.

## Démarrage

La baseline requiert Python 3.12. Les instructions Windows, Linux et macOS ainsi que les commandes de contrôle sont décrites dans `docs/development/ENVIRONMENT.md`.

La structure détaillée et sa correspondance avec la Phase 6.15 sont documentées dans `docs/development/REPOSITORY_STRUCTURE.md`.
