# Agent IA pedagogique - Projet V2

Nouvelle implementation du projet d'agent IA pedagogique.

## Principe fondateur : non-heritage de V1

V2 repart d'une base propre.

**Aucun fichier, code, configuration, dependance, choix d'architecture ou regle technique provenant de V1 n'est repris automatiquement.**

Toute reutilisation d'un element de V1 doit etre :

1. identifiee explicitement ;
2. auditee ;
3. justifiee par les besoins et livrables canoniques de V2 ;
4. validee avant integration ;
5. tracee dans `docs/legacy-review/`.

### Exception initiale explicitement autorisee

La base pedagogique SQL canonique est l'actif metier destine a etre conserve. Elle doit neanmoins faire l'objet d'un audit d'integrite, de structure et de compatibilite avant son integration operationnelle dans V2.

Aucun fichier de base de donnees runtime n'est stocke dans ce depot. `database/reference/` pourra contenir des manifests, checksums et documents valides, jamais la base binaire elle-meme.

## Sources de verite

Les specifications et livrables canoniques valides de Projet V2 gouvernent la reconstruction. L'ancien depot V1 constitue uniquement une reference historique et ne doit pas servir de source implicite de code.

## Organisation de la baseline

- `backend/` contient le code source Python et les frontieres Phase 6.15 ;
- `tests/` contient les gardes architecturales et les futurs niveaux de test ;
- `architecture/adr/` contient les decisions d'architecture ;
- `docs/development/` contient la documentation de developpement ;
- les donnees runtime, bases, logs, exports et artefacts restent hors du depot ;
- les futurs outils agents entreront par `backend/adapters/inbound/agent_tools/` et consommeront les use cases Application ;
- la base pedagogique fera l'objet d'une integration future, auditee et distincte de cette baseline.

Aucun agent, framework, provider LLM, ORM, vector store ou mecanisme de secrets n'est implemente en Phase 12.2.

## Demarrage

La baseline requiert Python 3.12. Les instructions Windows, Linux et macOS ainsi que les commandes de controle sont decrites dans `docs/development/ENVIRONMENT.md`.

La structure detaillee et sa correspondance avec la Phase 6.15 sont documentees dans `docs/development/REPOSITORY_STRUCTURE.md`.
