# Phase 12.16-D — OpenAI generation/correction adapter baseline

Date de calibration : 2026-08-28.

## 1. Parent C

Le lot part du commit C exact `a272888acbde2120ea201891921959cc72a3baef`, sur la branche `phase12/12-16-provider-model-calibration`. Les refs `main` et `origin/main` étaient toutes deux à `7ae02ee109bcc6399ec0f71616da6aef07abda81`, avec une relation `main...HEAD` de `0 2` et un worktree propre.

## 2. Sources officielles revalidées

Les sources officielles suivantes ont été revalidées le 2026-08-28 :

- fiches modèles [`gpt-5.6-terra`](https://developers.openai.com/api/docs/models/gpt-5.6-terra) et [`gpt-5.6-sol`](https://developers.openai.com/api/docs/models/gpt-5.6-sol) ;
- [création d'une Responses API response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) ;
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) ;
- [SDK Python officiel](https://developers.openai.com/api/reference/python) ;
- [codes d'erreur API](https://developers.openai.com/api/docs/guides/error-codes) ;
- [politique de rétention par endpoint](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint).

Terra et Sol restent des modèles actuels, compatibles Responses API et Structured Outputs, avec un contexte annoncé de 1 050 000 tokens et un maximum de sortie annoncé de 128 000 tokens. Le choix de profil demeure exclusivement celui de la configuration canonique établie en C.

## 3. Décision de transport

Le transport utilise le SDK Python officiel et `client.responses.create`. Aucun client HTTP maison ni framework LLM n'est introduit. Le helper SDK `response.output_text` est utilisé pour le texte ; les items typés sont parcourus pour détecter un refus sans dépendre de `output[0]`.

## 4. Décision de dépendance

La seule dépendance runtime directe ajoutée est `openai>=3.5,<4`. La version vérifiée et installée pour la calibration est `3.5.0`, compatible avec Python 3.12. Cette borne accepte les correctifs et évolutions compatibles de la majeure 3 et ferme toute migration majeure implicite. Les dépendances de développement restent inchangées. Aucun SDK d'un autre fournisseur, LangChain, LlamaIndex ou LiteLLM n'est ajouté.

Arbre top-level observé dans le venv de validation : `openai 3.5.0` → `anyio 4.14.2`, `httpx2 2.12.0`, `jiter 0.16.0`, `pydantic 2.13.5`, `sniffio 1.3.1`, `typing-extensions 4.16.0`.

## 5. Carte des packages

- `backend/adapters/outbound/generation/openai/contracts.py` : seam et DTO privés du transport ;
- `backend/adapters/outbound/generation/openai/mapping.py` : mapper borné request/schema ;
- `backend/adapters/outbound/generation/openai/transport.py` : SDK officiel et normalisation de response ;
- `backend/adapters/outbound/generation/openai/adapter.py` : implémentation du `GenerationPort` ;
- `backend/infrastructure/composition/factories/openai.py` : composition depuis la route primaire effective.

Le SDK n'est importé directement que par le transport concret.

## 6. Chaîne du secret

La chaîne est : `ProviderProfileConfig.credential_ref` → `ProviderSecretResolver.resolve` → `ProviderSecretValue` → `reveal_for_transport()` dans le constructeur du transport SDK → `OpenAI(api_key=...)`. L'adaptateur, les erreurs, les métadonnées et les snapshots du fake ne contiennent jamais la valeur brute. Les `repr` du secret et du transport sont redacted.

## 7. Request mapper

Le mapper sérialise explicitement l'opération, l'identifiant d'étape, le type de production, l'objectif, le format, le contexte pédagogique, les inputs résolus, les contraintes, les références de preuve, la cible/version, les sections attendues et le contrat de sortie. Les mappings gelés et références typées V2 sont convertis en objets JSON publics ; aucune dataclass n'est sérialisée naïvement. L'entrée est bornée à 250 000 caractères sans inventer de comptage de tokens.

## 8. Structured output schema

Le schema strict exige `outcome`, `sections`, `warnings` et `uncertainties`, avec `additionalProperties=false`. Les sections sont une liste bornée de couples `code`/`text`, les codes attendus sont énumérés quand ils existent, et les limitations sont des couples structurés `code`/`message`. Le validator V2 revérifie après le fournisseur : clés exactes, sections attendues dans l'ordre, absence de doublons ou d'inconnues, textes non vides, limitations bornées et cohérence de l'outcome.

## 9. GENERATE

`GenerationOperation.GENERATE` utilise le workload technique `GENERATION`. L'instruction d'opération limite la production au brouillon pédagogique demandé à partir des seules données fournies. Le modèle exact provient du profil primaire sélectionné.

## 10. CORRECT

`GenerationOperation.CORRECT` utilise le workload `CORRECTION` dans la même famille d'adaptateur. La référence de version exacte est transmise. L'instruction demande de préserver le contenu non concerné et de signaler les constats non résolus, sans acquérir d'autorité de validation ou de promotion.

## 11. Décision TRANSFORM

`TRANSFORM_SUPPORTED = TRUE`. `GenerationOperation.TRANSFORM` réutilise le workload `GENERATION`, transmet la cible et les preuves explicites, et demande une transformation bornée au format requis sans ajouter de faits non supportés.

## 12. Status mapping

- response complète et output valide sans limitation → `SUCCEEDED` ;
- output exploitable avec warning, incertitude ou response `incomplete` → `PARTIAL` ;
- refus explicite détecté dans les items typés → `REFUSED` ;
- outcome structuré explicite `INSUFFICIENT_EVIDENCE`, sans section et avec incertitude → `INSUFFICIENT_EVIDENCE` ;
- response `failed` → erreur fermée `UNAVAILABLE`.

## 13. Error mapping

Les erreurs SDK d'authentification/permission, rate limit, timeout, connexion, serveur et API générique sont converties en catégories transport fermées, puis en `GenerationPortError(UNAVAILABLE, safe_reason)`. Un JSON invalide, un schema incohérent ou une section manquante devient `GenerationPortError(INVALID_RESPONSE, "OPENAI_RESPONSE_DOES_NOT_MATCH_CONTRACT")`. Aucun message brut du SDK ou du fournisseur ne traverse la frontière.

## 14. Timeout et retry

Le timeout est dérivé exactement de `call_timeout_milliseconds`. Le client SDK est construit avec `max_retries=0`. L'adaptateur effectue un seul appel, même si `max_attempts` est supérieur à 1. Il n'implémente ni boucle de retry, ni backoff, ni replay, ni fallback. `store=false`, `stream=false`, `background=false`, `tools=[]` et `tool_choice=none` sont explicites. `max_output_tokens` applique le minimum entre la limite d'invocation configurée et la réserve de sortie du contexte.

## 15. Métadonnées sûres

L'allowlist est limitée à `provider_code`, `provider_profile_id`, `model_profile_id`, `model_code`, `response_status`, `input_tokens`, `cached_input_tokens`, `output_tokens` et `total_tokens`. Les compteurs absents ne sont pas inventés. Aucun identifiant brut de response, prix, coût calculé, prompt, secret ou payload fournisseur n'est exposé. L'enforcement du plafond monétaire reste différé à un lot disposant d'une source de prix canonique.

## 16. Composition

`build_openai_generation_adapter` reçoit l'`EffectiveProviderConfiguration`, le workload et le resolver. Il sélectionne uniquement `primary_model_profile_id`, retrouve le provider associé et construit l'adaptateur. Une route absente, un workload non supporté, un provider autre qu'OpenAI ou un profil non structuré échoue avec `INVALID_PROVIDER_CONFIGURATION`. Les fallbacks déclarés ne sont pas exécutés dans D.

## 17. Tests offline

Les tests utilisent un fake transport local et ne réalisent aucun appel réseau OpenAI. Ils couvrent GENERATE, CORRECT, TRANSFORM, modèle exact, request mapper, schema, succès, partial/incomplete, refus, insuffisance de preuve, JSON invalide, sections manquantes/inconnues, auth/rate-limit/timeout/connexion/serveur, secret absent, appel unique, configuration SDK, redaction, factory primaire et fitness d'architecture. La sélection D ciblée passe à `38 passed`; les régressions ciblées passent à `547 passed` (avec 20 gates seed conditionnelles exécutées séparément), les 20 gates SQLite/scénarios réels passent à `20 passed`, et la suite pédagogique canonique réelle passe à `1 passed`.

## 18. Live smoke optionnel

`LIVE_PROVIDER_CALIBRATION = NOT_YET_EXECUTED`. Aucun appel fournisseur réel n'est déclenché automatiquement et aucun secret réel n'est requis par les gates D.

## 19. Handoff E

Le `GenerationPort` existant est réutilisé sans modification, les frontières agent/domain/Application restent provider-neutral, et D ne touche ni recovery, observability, registry, review, base de données ni evaluation harness. Après succès de toutes les gates, le handoff attendu est `NEXT_GATE = 12.16-E_READY`. Aucun ADR supplémentaire n'est requis : `ADR_REQUIRED = NO`, car le lot implémente les décisions canoniques C/ADR-P12-059 avec les mécanismes standards du SDK officiel.
