# R5 — Références locales réelles, préparation sans envoi

Le contrat `CONVERSATION-REFERENCE-PROVENANCE-1.1` conserve le label synthétique R2
et ajoute `REFERENCE_LOCALE_R5_V1 — aucune autorité officielle attestée`.
Il ne modifie ni les routes HTTP ni les anciens grants et profils live.

Le chemin livré est : recherche M03 existante, sélection de passages canoniques,
relecture OP-13 dans un snapshot read-only, Application M04, AG02, puis préparation
AG03. Aucun générateur n'est invoqué. Le résultat est `READY_NOT_SENT`, pas une
production validée, une autorisation de transfert ou un contrat fournisseur prêt.

## Entrée privée explicite

Depuis une copie de travail privée déjà vérifiée, hors dépôt, sans migration :

```text
python -m backend.adapters.inbound.cli.local_references --runtime <copie-absolue> --data-root <racine-absolue> --runtime-sha256 <sha256> --request <requete-json-privee> --output <repertoire-neuf-prive>
```

Le JSON comporte `brief`, `context` (les neuf champs M07 confirmés), `queries`
(une à trois recherches distinctes), et facultativement `selection` : une entrée
par recherche avec exactement `query`, `passage_ref`, `version_or_checksum`.
Sans sélection explicite, le résultat est une **proposition technique**, non une
sélection pédagogique approuvée. La fenêtre de vingt résultats ne représente pas
la couverture totale du corpus. Aucun texte de recherche ne remplace le passage
OP-13 intégral ; un passage dépassant 1 000 caractères est refusé, jamais tronqué.

Les exports locaux `projection.json`, `references.md` et leur manifeste SHA-256
restent privés hors Git. La console n'émet aucun extrait. Un échec ne publie pas de
manifeste complet et n'autorise aucune réutilisation automatique du répertoire.
Le runtime est relu read-only, empreinte vérifiée avant et après ; aucun seed ni
chemin documentaire n'est suivi. Utiliser uniquement les copies expressément
autorisées, jamais un original en usage.

Les métadonnées documentaires liées sont indicatives : un lien n'atteste ni un
document complet, ni son autorité officielle, ni une validation pédagogique.
Les restrictions, la provenance et les références restent dans l'export privé.
R4 sauvegarde/réouverture/Word reste inchangé ; aucun nouvel export du pilote
historique n'est créé par cette commande. R6–R8/H3 ne sont pas démarrés.

## Vérification

Tests : `test_r5_local_reference`, `test_r5_scope_guard`, `test_r5_product_boundary`,
non-régressions conversation/recherche/R3/R4 et boundaries historiques concernés.
Utiliser le Python 3.12 et les dépendances déjà disponibles, un `--basetemp` neuf
hors dépôt, sans cache pytest, puis Ruff et mypy selon `ENVIRONMENT.md`.
Les résultats réels et diagnostics sont livrés séparément hors dépôt ; ce fichier
ne constitue pas une déclaration anticipée de réussite.
