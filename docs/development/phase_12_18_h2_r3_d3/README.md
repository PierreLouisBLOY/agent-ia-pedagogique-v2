# R3 D3 — incrément synthétique

Restauration authentifiée de deux versions existantes, refus E08 précis, projection et contrat HARDEN dédiés. Le chemin conserve inbound → Application → AG03/CAP-G02 → port → M04 → CAP-A01 → publication M08. Aucune nouvelle route ni activation fournisseur par défaut.

Les contrats de ce dossier sont génériques. Aucun export du pilote, grant réel, credential, sortie ou donnée privée ne fait partie du dépôt. Le profil pur ne fournit aucun budget. Une exécution réelle exige un accord distinct et des identités exactes, un reçu durable one-shot et une capture avant parsing/fermeture.

Les 36 fichiers de tests sont listés dans IMPLEMENTATION_SCOPE.json. Exécuter pytest sans cache et avec basetemp externe ; Ruff sans cache sur le delta ; mypy backend puis strict sur les nouveaux fichiers ; compileall avec pycache externe ; git diff --check. Les preuves d'exécution et JUnit restent hors dépôt. Aucun statut PASS n'est présumé par ce document. La dette archivée mentionne 476 diagnostics. Le contrôle strict des 21 fichiers Python historiques modifiés reproduit 220 erreurs sur 10 fichiers, identiques avant/après avec les dépendances verrouillées ; il reste NOT_PASS et ne constitue pas une reproduction du chiffre 476.

Les champs source_text et dependency_refusal des contrats conservent le texte de conception minimisé comme provenance, y compris ses mentions d'autorisation alors en attente. Le statut d'adoption du successeur et l'ADR ci-dessus définissent l'accord synthétique actuel ; aucune mention de conception ne donne une permission live.

Le pilote reste inchangé ; A16 reste un avertissement et une review du parent ne vaut jamais review du successeur. Aucun E06, COUNT, LIVE, R4 ou H3 n'est lancé par cet incrément.
