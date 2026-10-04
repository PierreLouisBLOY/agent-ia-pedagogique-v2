# Compagnons techniques du pilote sans COUNT

Le produit reste celui de la baseline applicative `d7bae43c4791f706df859043efbc230076ee0884`. Cette candidate versionne les compagnons du pilote séparément : aucune modification des contrats métier, du prompt approuvé, des ports normaux ou des sources packagées.

L'autorisation propriétaire de campagne `79c46f0f9e538c4d864d0a880e0f1bef780304eaf8fec6247c1c99449eaa0732`, puis son amendement sans COUNT, permettent au plus sept créations et sept revues, zéro retry/fallback, 1,96 USD cumulés et 0,14 USD par réponse. Les conditions de transmission et d'arrêt restent applicables. Ce code ne constitue aucune nouvelle autorisation et n'ouvre aucun transport dans la composition normale.

## Raccordement et preuve

- `mega_content_ids.py` : normalisation de casse uniquement des IDs techniques avec refus des collisions et références incohérentes ; ajout explicite d'une mention du statut candidat local si absente, jamais attribution de cette mention au fournisseur. Texte du sujet, réponses, barème, sources, contexte et bindings conservés. Les préconditions originales manquantes ou la saturation des limitations restent bloquantes.
- `mega_no_count_gate.py` : préflight fermé, tokenizer déterministe ou refus, réserve structurelle 10 000, plafond entrée 40 000, sortie 4 096 ; prix majoré d'entrée couvrant l'écriture cache, ledger pessimiste cumulatif, consommation avant effet, aucune opération COUNT/MODIFY.
- `mega_tokenizer_count.py` : helper officiel isolé et vérifié, résolution officielle du modèle, tous textes/clés et JSON sérialisé, réseau interdit pendant le comptage. Les wheels, données et manifestes de l'environnement restent privés hors Git ; les locks du produit sont inchangés.
- `mega_tariff_fetch.py` : preuve publique officielle actuelle sans credential ni appel modèle ; refus d'un tarif différent ou illisible.
- `mega_f02_windows_handles.py` / `mega_retained_inputs.py` : reprise du mécanisme F02 qualifié, réservation atomique et handles retenus contre substitution ; preuves historiques immuables.
- `mega_no_count_continuation.py` : récupération déclarée du M01 réellement reçu, aucun second CREATE M01, consommation et réserve héritées, seules treize opérations restantes, expiration d'origine inchangée, namespace distinct protégé.

Le driver historique `mega_no_count_runner.py` contient la configuration privée du poste et reste un artefact opératoire extérieur au dépôt, identifié par SHA-256 `c7d8c652fbcad6b6ad123a7df3221b1e5b4fd5ad3d6033d3ef6bf88a31e92d79`. Le successeur l'utilise par composition explicite. Ces compagnons ne sont pas un lanceur portable autonome : les exécuter depuis le checkout échoue sans les entrées locales authentifiées. Leur copie opérationnelle qualifiée, les code pins, le driver, les grants et reçus figurent dans le dossier de preuve privé du même méga-lot. Aucun credential, payload généré, base ou chemin personnel n'est versionné ici.

La récupération M01 vérifie les empreintes de son reçu HTTP 200, de la réponse et du corps exact, puis repasse par Application et sa seed authentifiée en lecture. La réponse brute ne change pas. Un mapping et une annotation de provenance séparent le contenu fournisseur des identifiants et du statut locaux. La validation structurelle ne vaut pas évaluation pédagogique, promotion ni signature enseignante.

## Validation

Les tests portables `tests/unit/test_mega_no_count_content_successor.py` utilisent exclusivement les doubles explicitement déclarés existants et couvrent les six familles, les collisions, les références, les limitations, le barème incorrect, la réserve financière héritée et le refus COUNT/MODIFY. Ils ne dépendent d'aucune pièce privée. Les contrôles réels Windows/receipt/tokenizer et transport synthétique du pilote sont distincts : 58 PASS exécutés dans les preuves privées, sans les confondre avec une campagne fournisseur terminée ou les 424 PASS de phase A.

Aucun ancien FAIL ou précondition privée n'est masqué. Aucun push/merge. L'acceptation enseignante et la décision finale de livraison appartiennent au propriétaire.

## Identité des copies

Les copies opérationnelles actuellement pincées restent immuables. La version source ajoute les annotations exigées par le mypy strict du dépôt, emploie `datetime.UTC` (alias identique à `timezone.utc`) et importe directement les mêmes fonctions canoniques de projection/sauvegarde au lieu de leur réexport par le driver. Ces ajustements de source ne sont pas activés dans la campagne en cours. Le mécanisme F02 reste identique octet pour octet. Les résultats source et opérationnels sont conservés séparément ; le commit du compagnon ne remplace pas l'identité applicative d7bae43 adoptée.
