# R4 — Sauvegarde, réouverture et Word

Décision de réalisation sous P_R4_SAVE_REOPEN_WORD_GROUPED_DELIVERY, baseline
f4ba498ba001dfcae44d76d1a430405cbaf32b3f. Aucun changement de règle CAP-A01.

M08 conserve une enveloppe documentaire versionnée : vue CAP-R02, bundle facultatif,
rapports strictement liés et provenance. Les octets canoniques JSON (UTF-8, clés triées,
séparateurs compacts, sans NaN) sont immuables. Les états de conservation, nouvelles
validations et promotions sont séparés. Une sauvegarde n'est pas une publication
pédagogique et ne change jamais l'identité, le contenu, la limite de trois versions
ou la rétention historiquement déclarée dans une vue importée.

La persistance utilise les primitives filesystem privées existantes : les enregistrements
documentaires sont immuables, leur catalogue est remplacé atomiquement après fsync.
Un verrou interprocessus sérialise les transactions ; aucun écrasement de version.
Aucun accès implicite au seed,
runtime, SQLite, environnement, fournisseur ou credential. Une racine neuve doit
être créée explicitement ; une reprise exige son marqueur R4 exact.

Les imports sont passifs : uniquement données typées, rapports et provenance
documentaire. Aucune désérialisation de grants, sessions, sceaux ou jobs. La promotion
des imports est refusée dans R4. CAP-A01 reste une action nouvelle explicite, datée.
CAP-A02 appartient à M11 : décision humaine fraîche et liée à l'empreinte exacte,
validation exacte sans FAIL, absence de finding bloquant ; A16 WARNING demeure
visible et doit être reconnu explicitement. L'autorité ne provient jamais d'un
rapport importé. Le pilote historique n'est pas promu.

M12 porte CAP-A03. Sa projection fermée distingue sujet, corrigé et barème ; un
adaptateur OOXML standard produit des DOCX éditables sans installation. Le sujet
ne reçoit jamais le bundle complet ni ses réponses. Les textes complets sont repris,
sans découpage ou attribution fondés sur les locators. Les réserves restent visibles
côté enseignant. La prévisualisation utilise la même projection que l'export.

L'API locale conserve les protections Host/Origin/nonce, les erreurs fermées, les
limites d'entrée et les assets locaux. Le mode R4 seul ne configure aucune bibliothèque.
Les capacités existantes CAP-R02/A01/A02/A03 sont réutilisées, sans nouvel identifiant.

Les guards R3 restent des preuves historiques. Un successeur R4 vérifie ses fichiers
exacts et deltas bornés avant de fournir une projection baseline aux oracles historiques.
Une mutation de fichier, de manifeste ou une extension non inventoriée échoue ; aucune
exemption globale de l'API ou des guards n'est permise. Les tests de mutation le vérifient.

Recette : artificiel d'abord, panne/conflit/idempotence, nouveau processus, routes et
sécurité HTTP, DOCX XML + séparation et rendu si disponible. Les copies pédagogiques
privées et exports restent hors Git. Publication et intégration protégées seulement
après validation. Aucune suite R5–R8/H3 ni effet fournisseur.
