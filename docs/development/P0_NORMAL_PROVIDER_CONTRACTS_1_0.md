# P0 normal — contrats et prototype 1.0 à relire

Statut : PROPOSED_FOR_DISTINCT_PREIMPLEMENTATION_REVIEW, 2026-10-11. Cette spécification complète l’ADR de composition normale déjà relue. Aucun grant live, clé ou envoi. Le prototype privé `S4/normal_provider_contract_prototype.py` ne fait que calculs/validations en mémoire et les tests emploient des données explicitement synthétiques.

## G1 — P0-NORMAL-CREATE-GRANT-1.0

Objet fermé, sans chemin, URL libre, credential ou contenu pédagogique. Champs obligatoires :

```
schema, operation, owner_decision_sha256, baseline_commit, source_tree_sha256,
package_sha256, runtime_sha256, preparation_sha256, context_sha256,
reference_set_sha256, request_sha256, request_bytes, profile_sha256,
output_schema_sha256, tokenizer_manifest_sha256, tariff_sha256,
receipt_root_sha256, namespace_sha256, issued_at_utc, expires_at_utc,
provider, model, endpoint, reasoning, tier, max_output_tokens, max_calls,
count_calls, review_calls, modify_calls, retry, fallback, parallelism,
ceiling_usd, live_authorized, transfer_authorized
```

`schema` vaut l’identité ci-dessus, `operation=CREATE`, provider OPENAI, endpoint exact `https://api.openai.com/v1/responses`, modèle `gpt-5.6-terra`, reasoning low, tier default, sortie 4 096, max_calls 1, autres appels et retry 0, fallback NONE, parallélisme 1. Les hashes sont des SHA-256 complets minuscules ; HEAD est 40 hex. Les entiers refusent bool. Fenêtre UTC explicitement consciente de fuseau, bornée à 120 minutes maximum ; pas de renouvellement automatique. Plafond Decimal fini strictement positif, ≤0,140000 USD. `live_authorized` et `transfer_authorized` doivent être vrais pour l’autorisation opérationnelle future ; les prototypes synthétiques n’ont pas d’autorité réelle.

Le manifeste du code/payload/package, la préparation et tous les éléments liés doivent être contrôlés depuis les frontières qualifiées. Le prototype ne prétend pas qu’une chaîne hex prouve un contenu de fichier ou une décision humaine : la factory qualifiée fournit les identités effectivement vérifiées, dont le SHA-256 du texte propriétaire adopté. Tout écart refuse le dispatch. Aucun ancien schema/grant Boréal/R2/MEGA accepté.

## F1 — préflight local sans COUNT

Trois entrées immuables, jamais obtenues d’un champ HTTP : corps Responses canonique UTF-8 ; preuve tokenizer effectivement retournée par le helper vérifié ; tarif courant vérifié/admis. Les identités du helper, du mapping officiel, des données et du tarif sont liées au grant.

Tarif fermé : `schema=P0-NORMAL-TARIFF-1.0`, `provider`, `model`, `tier`, `input_usd_per_million`, `output_usd_per_million`, `input_multiplier`, `evidence_sha256`, `owner_admission_sha256`, `retrieved_at_utc`. Le produit de prix entrée et multiplicateur fournit la majoration ; multiplicateur fini ≥1, prix strictement positifs. Aucune remise de cache présumée. La preuve effective doit couvrir les coûts applicables et leur durée de validité ; le prototype ne vérifie pas une page Web et ne qualifie pas un tarif ancien comme actuel.

Tokenizer fermé : `schema=P0-NORMAL-TOKENIZER-PROOF-1.0`, `model`, `recognition`, `encoding`, `request_sha256`, `manifest_sha256`, `model_mapping_sha256`, `encoding_sha256`, `all_string_values_and_keys_tokens`, `serialized_json_tokens`, `network_forbidden_during_count`, `provider_calls`. Recognition OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER, modèle exact, encoding o200k_base, body SHA-256 exact, réseau interdit, zéro fournisseur. Versions/hashes réels proviennent du helper isolé authentifié ; une preuve passée en JSON par le navigateur est interdite.

Corps fournisseur fermé identique à la projection actuelle : `background`, `model`, `instructions`, `input`, `max_output_tokens`, `service_tier`, `store`, `stream`, `reasoning`, `tools`, `tool_choice`, `text`. Même modèle/profil, aucun outil, les trois booléens false, sortie 4096. `text` contient exclusivement un format json_schema strict nommé p0_pedagogical_content, schéma exactement lié au grant. Input et instructions sont des chaînes. Rejet des doublons/non-finis, alias de flags ou octets non canoniques.

Calcul Decimal : `T=max(tokens_chaines_et_cles,tokens_JSON)`, `U=T+10000`, U≤40000, `C=(U*prix_entree*majoration + 4096*prix_sortie)/1000000`, C≤plafond. Preuve de sortie fermée avec request SHA/taille, tokenizer SHA, tarif SHA, U/T/réserve/sortie, coût/plafond, retry/fallback et COUNT 0. Hash et flags recomparés immédiatement avant effet.

## R1 — reçu technique et récupération confirmée

Le vrai adapter utilisera les primitives F02/publication atomique existantes sous une racine technique privée extérieure à Git. Un namespace neuf exclusivement publié est consommé **avant credential/transport**. Les événements sont append-only et distincts : RESERVED → PROVIDER_ATTEMPTED → RESPONSE_CAPTURED → PARSED → CONSUMED ; UNKNOWN ou PARSING_REJECTED sont des dispositions terminales possibles. Aucune suppression/remplacement/libération de réserve automatique. Un reçu persisté impossible empêche le dispatch ; une erreur après dispatch conserve la réserve pessimiste.

Reçu fermé `P0-NORMAL-TECHNICAL-RECEIPT-1.0` : `schema`, `grant_sha256`, `request_sha256`, `preflight_sha256`, `namespace_sha256`, `state`, `timestamp_utc`, `provider_attempts`, `response_status`, `response_artifact_sha256`, `usage`, `reserved_usd`, `observed_cost_status`. Usage fermé avec tokens entrée/cache/sortie/reasoning/total, valeurs int positives ou null selon disponibilité. Ne pas annoncer un coût observé si l’usage ou la preuve tarifaire ne suffisent pas. Aucun contenu ni clé dans le reçu public/minimisé.

Artifact privé fermé `P0-NORMAL-CONFIRMED-RESULT-1.0` : `schema`, `grant_sha256`, `request_sha256`, `dispatch_sha256`, `response_status`, `output_text`, `usage`. Le dispatch exact associé contient contexte/refs/extraits et identités locales, préservés pour binding Application ; il est capturé avant effet sous l’identité du grant, sans secret. La réponse est capturée avant parsing, sans prétendre exporter un raw provider response absent du transport normalisé. Les SHA-256 permettent de détecter corruption/substitution ; F02 retient les handles contre substitution entre vérification et lecture.

`recover_confirmed(*, request: Mapping[str, object]) -> Mapping[str, object]` est une **capacité de récupération technique séparée**, pas `authorize/generate`. Elle compare grant, dispatch, body et artifact, n’exige pas un grant encore actif pour relire une consommation confirmée et n’acquiert aucun nouveau droit. Elle accepte uniquement une réponse completed attestée et un contenu qui repasse les mêmes guards/binding/validation ; elle refuse UNKNOWN, résultat absent, substitution et réponse invalide. Aucun resolver, transport, retry ou nouveau namespace. Une récupération n’émet pas un second contenu fournisseur et ne réattribue pas des preuves à un autre prod/ver.

L’interface spécialisée `P0ConfirmedGenerationRecoveryPort` proposée expose `recover_confirmed` en complément du P0GenerationPort historique inchangé, seulement dans la composition normale. Toute entrée Application qui l’utilise est liée au même request/grant, et ne réactive pas les droits du grant. Les imports documentaires ordinaires et les versions sans reçu correspondant ne peuvent l’invoquer.

## A1 — publication de sécurité par Application

Callback injecté dans la composition normale, jamais dans le mode sans fournisseur :

```
publish_generated(production_ref: str, version_ref: str,
                  bundle_sha256: str) -> Mapping[str, object]
```

Il est appelé après `CreateP0Candidate`, contrôle des bindings, stockage du candidat dans records et validation Application, avant retour HTTP. Il passe par `saved_source` puis le use case Application save existant, sans copie directe ni store métier parallèle.

Retour strict : `{state:'APPLICATION_SAVED', production_ref, version_ref, bundle_sha256, record_sha256}`. Les quatre identités correspondent à la version exacte et au record sauvegardé ; erreur de callback/identité => aucun succès annoncé. L’interface indique cette conservation de sécurité et permet de retrouver la version dans la bibliothèque si la réponse HTTP est perdue. Une sauvegarde explicite ultérieure ne réécrit pas l’original ni ne regénère la version.

Si une interruption survient entre réponse fournisseur durable et publication Application, la récupération technique attestée transmet le même contenu aux mêmes validation/binding et à cette même publication, sans second dispatch. L’entrée Application de récupération doit être spécifiée et relue séparément avant code : soit un callback interne de reprise borné sur l’opération consommée, soit un companion fermé avec grant/request/identités exactes ; aucune restauration automatique de permission. Le coordinateur possède P0CreationService et réalise ce raccord.

## Conditions de revue et tests

Relire G1/F1/R1/A1 et le prototype exact avant raccord aux transports/receipts. La nominale prototype ne vaut aucune autorisation live. Mutations requises : champ inconnu, type bool-entier, toutes identités liées, horloge/expiry, autre provider/modèle/endpoint/operation, perte tarif/tokenizer/reconnaissance, coût/tokens trop élevés, flags cachés, autre body/schema, replay/concurrence/publication échouée, artifact substitué, UNKNOWN et reprise sans nouvel effet.

Tests nominaux/mutations séparés des essais de véritable intelligence et de recette enseignante. Les deux gates historiques restent fermées ; aucune acceptation tarifaire ou opérationnelle n’est déduite de cette revue technique.
