# ADR — réparation des frontières Application et AG02 du raccord normal

Statut : IMPLÉMENTÉ HORS ACTIVATION après revue préalable distincte favorable limitée du 11 octobre 2026. Avis privé SHA-256 7fdd3b10e01fbe9b395ccbda5aae997469439e66c9b1bd9299c1af16d29702a3, six prototypes exacts relus et 18 témoins réellement rejoués ; deux témoins distincts supplémentaires couvrent les bornes 2 et 8. Les preuves privées ne sont pas des dépendances des tests versionnés. Les corrections portent sur les défauts réellement constatés au global de 30bab7a, conservé. Aucun scanner/assertion historique n'est assoupli.

## Défauts et correction

1. `api/p0_creation.py` construit directement la query métier ProposeP0Intention. Injecter `intention_execute` depuis la factory ; son absence refuse explicitement l'opération. Le transport JSON et les protections HTTP/nonce ne changent pas. La query déterministe reste le use case Application existant, sans intelligence fournisseur présumée.
2. `p0_normal_agents.py` construit EvidenceItem hors AG02 et les labels de sécurité hors frontière approuvée. Réutiliser EvidenceAgent **inchangé** et ses ports search/admissibility/content existants sur un snapshot fermé en mémoire de la préparation reçue d'Application. Les deux canaux techniques requis ne recherchent que ces mêmes références exactes ; ils ne consultent ni SQLite, repository, filesystem, réseau, secret ni autre contenu. Ce snapshot n'atteste ni l'authenticité Application ni une admission : les revalidations source/permission existantes restent nécessaires avant envoi. Aucun EvidenceItem/EvidenceSet n'est construit dans l'adaptateur.
3. Construire les labels et évaluations restrictives dans `security/tool_application.py`, owner de sécurité déjà approuvé. Deux helpers génériques acceptent EvidenceItem existants ou données Application et composent les primitives actuelles sans nouvelle autorité. Aucun scanner, pattern, disposition, garde partagé ni contrat historique n'est modifié. Le raccord fournisseur importe ces fonctions, plus aucun contracts.security.

Le snapshot valide 1 à 8 références fermées de six champs, IDs/locators/versions uniques, SHA d'extrait réel, ensemble d'evidence exact sans ajout/omission, et texte complet non vide ≤4000 caractères. Toute substitution de query/port/candidat/source/locator/version/extrait provoque refus. EvidenceAgent coordonne, vérifie la filiation et matérialise les mêmes textes avec borne4000 ; l'adaptateur vérifie l'équivalence de sortie, absence de troncation et conflits. La fraîcheur/autorité restent UNKNOWN/NONE selon le contrat actuel, jamais CURRENT/OFFICIAL ajoutés pour résoudre un test.

## Périmètre exact

- backend/adapters/inbound/api/p0_creation.py
- backend/infrastructure/composition/factories/p0_creation.py
- backend/adapters/outbound/generation/openai/p0_normal_agents.py
- nouveau backend/adapters/outbound/evidence/p0_prepared_snapshot.py
- backend/agent_runtime/security/tool_application.py
- nouveau tests/unit/test_p0_prepared_evidence_boundary.py
- tests intention HTTP et query existants : fixtures nominales injectent explicitement le callback Application ; le nouveau test shipping conserve le refus d'absence du callback
- ce nouvel ADR après avis préalable effectif.

Le déplacement projection notion/routes est un complément coordonné de S3 dans ses owners et son ADR, pas un changement couvert implicitement ici. Aucun contrat métier, agent registry, ancien grant, security scope, garde Git, DDL ou seed n'est touché. EvidenceAgent public et privé restent byte-identiques.

## Vérification et retour arrière

Avant implémentation : prototypes exacts et témoins purs lus/rejoués par S5. Après : nominal snapshot→AG02→AG03, mutations fermées d'identités/texte/injection et politique source, absence d'effet/provider ; producteurs normal/profile2, consommateurs HTTP intention ; assertions historiques EvidenceItem constructeur unique et approved security owner ; Ruff/mypy ciblés. Les suites historiques et FAIL initiaux restent conservés. Le retour arrière local reprend les devowners précédents et retire le nouveau snapshot seulement sur la candidate isolée, sans action runtime ou base. Aucun rollback propriétaire.

Les prototypes ne produisent ni admission, ni permission active, ni grant, ni credential, ni appel. La revue permet seulement les changements hors activation et ne qualifie pas un futur résultat pédagogique.
