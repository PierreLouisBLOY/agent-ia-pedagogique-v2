# Phase 12.17.6 — Cartographie des surfaces runtime

| Surface | Atteignable maintenant | Local-only | Entrée / frontière | Gardes observés |
|---|---:|---:|---|---|
| Startup applicatif | Non matérialisé | Oui par cible | Aucun composition root exécutable | N/A |
| CLI de calibration | Oui, uniquement par injection explicite | Oui | `CalibrationCliInvocation` | commande exacte `run`, runtime/invocation/output obligatoires, erreurs fermées |
| Serveur HTTP / routes | Non | Cible oui | Aucun serveur, route ou framework | aucune exposition actuelle |
| Agent tools / filesystem | Contrats et routeur, pas d'adaptateur filesystem concret | Oui | chemins relatifs non fiables vers port résolveur de confiance | allowlist outils, profil sandbox, limites, refus traversal/absolu/réseau/symlink, post-validation |
| SQLite runtime | Oui via factories appelables | Oui | chemins absolus injectés | seed/runtime distincts, seed authentifié en lecture seule, migrations allowlistées, runtime WAL |
| Backup / restore SQLite | Oui via fonctions appelables | Oui | chemins `Path` fournis par composition propriétaire | destination fraîche, copie temporaire, hash et manifest, restauration authentifiée |
| OpenAI generation/review/embedding | Adaptateurs actifs mais sans démarrage autonome | Non après composition explicite | DTO bornés + secret resolver | SDK `max_retries=0`, timeout, sortie structurée, `store=False` pour Responses, erreurs fermées |
| Anthropic calibration | Runtime actif mais désactivé par défaut | Non après autorisation explicite | plan, allowlist, budget, projection source | one-shot, budget, ledger, arrêt sur erreur, aucun retry dans runner/transport |
| Import/export produit | Non matérialisé | Cible oui | module structurel uniquement | garde sandbox contractuelle, pas encore de chaîne I/O concrète |
| Observabilité | Contrats et wrappers atteignables par injection | Oui par cible | événements techniques structurés | taille bornée, données sensibles rejetées, buffer borné, sink failure-isolated |

## Synthèse

La surface réseau réellement exposée par le dépôt est nulle : les seules sorties réseau possibles passent par des adaptateurs fournisseurs explicitement composés. Les principaux risques sont donc de préparation à la livraison plutôt que d'exploitation immédiate : contrat HTTP futur non matérialisé, adaptateur filesystem de production absent, et observabilité non câblée à une destination locale persistante.
