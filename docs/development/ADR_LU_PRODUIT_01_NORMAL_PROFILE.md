# ADR LU-PRODUIT-01 — composition normale explicite P1

Statut : PROPOSE POUR REVUE PREALABLE. Aucun accord fournisseur actif produit.
Portée : rendre les contrats P1/G1 déjà relus accessibles par le lanceur normal,
sans JSON de grant libre dans HTTP, sans installation et sans ancien accord.

## Contrat fermé de fichier

L'option CLI `--p0-normal-profile` est absente par défaut. Son fichier UTF-8
canonique est `P0-NORMAL-PROFILE-ENVELOPE-1.0` et contient exactement
`schema`, `profile`, `permission`, `decision`. Les deux derniers objets sont des
descripteurs `path` absolu / `sha256` binaire. Ils désignent une nouvelle P1 et
sa décision propriétaire effectivement adoptée, jamais des modèles livrés.

Le core `profile`, schéma `P0-NORMAL-PROFILE-1.0`, contient exactement :
`schema`, `baseline_commit`, `source_manifest`, `package`, `runtime`,
`saved_root`, `receipt_root`, `source_admission_manifest`,
`operator_delegation`, `tokenizer_manifest`, `tariff`, `tariff_evidence`,
`institutional_catalog_sha256`, `credential_ref`.

Chaque pièce sauf les chemins de racine et `runtime` est un descripteur
`path`/`sha256`. `runtime` contient `path`, `data_root`, `sha256`. Le profile SHA
est celui du core canonique, qui ne contient ni P1 ni décision : pas de cycle.
Le SHA de la politique P1 est calculé sur la P1 sans `owner_decision_sha256`.
La décision `P0-NORMAL-OWNER-DECISION-1.0` contient exactement `schema`,
`status=ADOPTED`, `profile_sha256`, `permission_policy_sha256`,
`source_admission_manifest_sha256`, `operator_delegation_sha256`,
`tokenizer_manifest_sha256`, `tariff_sha256`,
`excluded_oracles_and_private_evidence=true`,
`source_authority_unknown_preserved=true`, `local_operator_delegation_accepted=true`.
Son SHA binaire est `P1.owner_decision_sha256`. Cela consigne un accord local,
sans prétendre constituer une authentification cryptographique humaine.

La délégation `P0-LOCAL-OPERATOR-DELEGATION-1.0` contient exactement
`schema`, `windows_sid`, `windows_profile`, `credential_ref`,
`local_operator_delegation_accepted=true`. SID et répertoire de profil proviennent
du token Windows actuel, pas de nonce HTTP ni de variables d'identité libres.
Le compte et le profil doivent être ceux explicitement délégués par le propriétaire.

## Identités vérifiées

Le manifeste source `P0-NORMAL-SOURCE-MANIFEST-1.0` contient `schema` et `files`
(mapping chemin relatif -> SHA binaire). Il doit couvrir exactement les fichiers
applicatifs `.py`, `.js`, `.css`, `.html`, `.ps1`, `.json` sous backend/frontend/
tools/config, hors caches. Chaque entrée est vérifiée par lecture sans suivi de
lien. Le package ZIP doit contenir les mêmes chemins applicatifs et octets,
éventuellement sous un seul préfixe racine ; une divergence ferme le binding.
Le Git HEAD courant doit être la baseline P1 ; aucune mise à jour automatique.
Le profil est lié à une copie runtime identifiée, à la bibliothèque Application
et à une racine technique déjà existante hors Git. Aucune création d'ACL,
provision de base, migration ou copie métier ne fait partie de ce chargeur.

À chaque préflight et avant l'effet, relire les descripteurs et vérifier
source/package/runtime/delegation/catalogue/tokenizer/tarif. Le catalogue
institutionnel est relu par le use case Application existant. Les passages sont
toujours relus par la query d'admission Application, avec UNKNOWN conservé.
L'exclusion des oracles/pièces privées exige la décision liée au manifeste exact ;
l'absence de drapeau natif ne constitue pas une preuve négative d'autorité.

## Tokenizer local isolé

Le tokenizer officiel acquis historiquement peut être réutilisé dans son venv
privé, sans introduire le paquet dans les locks V2. Un helper technique borné
reçoit seulement les octets de la requête par stdin et restitue F1 ; aucune clé,
base, oracle ou grant ne lui est envoyé. L'environnement enfant est réduit aux
paramètres Windows/temporaires nécessaires et à un cache local explicitement
désigné. Aucun proxy ni variable OpenAI n'est hérité.

Le manifeste `P0-LOCAL-TOKENIZER-MANIFEST-1.0` contient exactement `schema`,
`python_path`, `python_sha256`, `package_root`, `package_version`, `files`,
`model_mapping_sha256`, `encoding_path`, `encoding_sha256`, `cache_root`.
`files` couvre exactement les sources/binaires importables des distributions
locales tiktoken/tiktoken_ext/regex/requests/urllib3/certifi/charset_normalizer/idna,
hors pycache. Ces versions et empreintes font l'objet de l'admission du manifeste.
Le helper refuse un import hors de ce package_root vérifié, une version changée,
ou une reconnaissance autre que le resolver officiel inchangé
`encoding_name_for_model(gpt-5.6-terra) == o200k_base`.

Le fichier de cache officiel correspondant à l'URL o200k_base est vérifié et
retenu par handle Windows interdisant WRITE/DELETE, ainsi que ses parents,
avant `get_encoding`. Le SHA attendu officiel est
`446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`.
Le helper n'installe et ne télécharge rien. Cache absent/modifié, paquet absent,
resolver refusant Terra ou résultat invalide => STOP avant tout secret/transport.

## Raccord produit et secret

Le lanceur transmet uniquement le chemin de ce profil explicitement sélectionné.
La factory construit P1/G1, le broker, la query d'admission et le callback
Application de consentement ; la reprise confirmée et la publication Application
existantes restent actives. Une option normale exige saved_root et product-v7,
refuse les voies R2/R5 live, review ou saved-only en même temps.

Le resolver local utilise le contrat ProviderSecretResolver existant. Après les
préflights et réservations, une saisie native masquée fournit la clé une fois
pour la session ; mémoire privée uniquement, jamais HTTP, env, argument ou fichier.
Console non interactive ou fallback non masqué => refus fermé. La valeur opaque
est effacée au shutdown. Le transport SDK existant utilise sa destination stricte
OpenAI, retry=0, pas de proxy/redirection/headers ambiants. Il ne se construit
qu'après les contrôles, avec zéro effet à l'import ou au démarrage.

## Qualification / retour arrière

Tests : enveloppe et décision non adoptées, hash cycles évités, données libres
refusées, mutation source/package/runtime/delegation/tokenizer/tarif, absence de
paquet/cache, import changé, resolver officiel réel local, Host/Origin/nonce,
consent exact, sérialisation interprocess et budget pessimiste, reprise sans
secret/transport. Les modèles de qualification sont déclarés synthétiques.
Aucun grant actif ni credential réel n'est créé par la qualification.
Retour arrière : retirer l'option de profil ; le mode local demeure sans port
fournisseur. Les preuves et réservations historiques ne sont ni effacées ni modifiées.
