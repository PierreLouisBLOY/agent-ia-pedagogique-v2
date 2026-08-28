# Phase 12.16-C — Recherche actuelle providers et modèles

## 1. Portée et date

`RESEARCH_AS_OF = 2026-08-28`

`PROVIDER_FACT_SNAPSHOT_AS_OF = 2026-08-28`

Ce lot est exclusivement documentaire. Il n'installe aucun SDK, n'appelle
aucune API provider depuis le produit, ne configure aucun secret et ne modifie
aucun code, test, registry ou dépendance. Les faits ci-dessous proviennent de
documents publics officiels consultés le 28 août 2026. Les appréciations de
qualité pédagogique restent provisoires jusqu'aux calibrations G/H.

## 2. Baseline Git d'entrée

- branche : `phase12/12-16-provider-model-calibration` ;
- `HEAD` et upstream : `51f909d9082ea4ed452405255a1452fa6d4fd638` ;
- `main` et `origin/main` : `7ae02ee109bcc6399ec0f71616da6aef07abda81` ;
- relation `main...HEAD` : `0/1` ;
- merge-base : `7ae02ee109bcc6399ec0f71616da6aef07abda81` ;
- worktree d'entrée : propre.

## 3. Méthode de recherche

La hiérarchie appliquée est : documentation API, catalogue de modèles,
structured outputs, prix, quotas, confidentialité, régions, cycle de vie puis
niveau de service. Les affirmations marketing ne valent pas benchmark. Aucun
benchmark tiers n'a été utilisé : `SECONDARY_SOURCE_COUNT = 0`.

Quatre providers cloud sont audités : OpenAI, Anthropic, Google Gemini et
Mistral AI. Mistral Small 4 est aussi étudié séparément comme baseline
open-weight ; cette classe de déploiement n'est pas assimilée à une API cloud.

Règles de normalisation :

- prix en `USD per 1M tokens`, hors taxes et outils facturés séparément ;
- `context_window_tokens` désigne la fenêtre totale annoncée ;
- `max_input_tokens` et `max_output_tokens` ne sont renseignés que s'ils sont
  publiés explicitement ;
- une donnée non publiée est `UNKNOWN` ;
- une option contractuelle ou soumise à approbation n'est pas traitée comme une
  garantie standard ;
- `STREAMING_REQUIRED = NO`.

## 4. Records de faits officiels

Chaque record suit exactement le schéma demandé. `YES_WITH_LIMITATIONS` indique
un support officiel assorti de restrictions documentées.

### 4.1 OpenAI — GPT-5.6 Terra

```yaml
provider: OpenAI
model_id: gpt-5.6-terra
model_family: GPT-5.6
model_status: CURRENT
official_model_page: https://developers.openai.com/api/docs/models/gpt-5.6-terra
verified_at: 2026-08-28
context_window_tokens: 1050000
max_input_tokens: UNKNOWN
max_output_tokens: 128000
structured_output_support: YES
json_schema_support: YES
tool_function_support: YES
batch_support: YES
prompt_cache_support: YES
input_price: 2.00
cached_input_price: 0.20
output_price: 12.00
price_unit: per 1M tokens
currency: USD
rate_limit_public_info: Tier 1 500 RPM/500000 TPM; tiers rise to Tier 5 15000 RPM/40000000 TPM; account tier applies
service_tier_info: Standard public tiering; other service modes require separate verification before activation
data_used_for_training_default: NO, unless customer explicitly opts in
retention_default: Abuse-monitoring logs up to 30 days; Responses application state 30 days by default unless store=false
zero_data_retention_option: YES, eligible customers subject to approval and endpoint restrictions
regional_processing_option: YES, eligible regional projects
eu_data_residency_option: YES, EEA and Switzerland storage/processing subject to approval and ZDR/modified-abuse-monitoring requirements
embedding_models_available: YES, text-embedding-3-large and text-embedding-3-small
embedding_dimension_info_if_official: UNKNOWN in the selected official model card; verify before F
sdk_required: NO
raw_http_api_available: YES
python_sdk_available: YES
deprecation_policy: Public deprecations page and model catalogue; revalidate on notice
model_snapshot_or_alias_semantics: gpt-5.6-terra is the selected explicit model ID; do not replace with gpt-5.6 alias
official_notes: Balance of intelligence and cost; cache writes are billed at 1.25x uncached input
unknowns: Exact max input; standard SLA; post-change pricing horizon; embedding dimensions on the cited card
```

### 4.2 OpenAI — GPT-5.6 Sol

```yaml
provider: OpenAI
model_id: gpt-5.6-sol
model_family: GPT-5.6
model_status: CURRENT
official_model_page: https://developers.openai.com/api/docs/models/gpt-5.6-sol
verified_at: 2026-08-28
context_window_tokens: 1050000
max_input_tokens: UNKNOWN
max_output_tokens: 128000
structured_output_support: YES
json_schema_support: YES
tool_function_support: YES
batch_support: YES
prompt_cache_support: YES
input_price: 4.00
cached_input_price: 0.40
output_price: 20.00
price_unit: per 1M tokens
currency: USD
rate_limit_public_info: Tier 1 500 RPM/500000 TPM; tiers rise to Tier 5 15000 RPM/40000000 TPM; account tier applies
service_tier_info: Standard public tiering; fast or contractual modes must be priced and calibrated separately
data_used_for_training_default: NO, unless customer explicitly opts in
retention_default: Abuse-monitoring logs up to 30 days; Responses application state 30 days by default unless store=false
zero_data_retention_option: YES, eligible customers subject to approval and endpoint restrictions
regional_processing_option: YES, eligible regional projects
eu_data_residency_option: YES, EEA and Switzerland storage/processing subject to approval and ZDR/modified-abuse-monitoring requirements
embedding_models_available: YES, text-embedding-3-large and text-embedding-3-small
embedding_dimension_info_if_official: UNKNOWN in the selected official model card; verify before F
sdk_required: NO
raw_http_api_available: YES
python_sdk_available: YES
deprecation_policy: Public deprecations page and model catalogue; revalidate on notice
model_snapshot_or_alias_semantics: gpt-5.6 is an alias routing to gpt-5.6-sol; pin gpt-5.6-sol in the C profile
official_notes: Frontier member of GPT-5.6; promotional price stated as available at least through 2026-11-21; requests above 272K input have long-context multipliers
unknowns: Exact max input; standard SLA; price after the stated promotional horizon; embedding dimensions on the cited card
```

### 4.3 OpenAI — GPT-5.6 Luna

```yaml
provider: OpenAI
model_id: gpt-5.6-luna
model_family: GPT-5.6
model_status: CURRENT
official_model_page: https://developers.openai.com/api/docs/models/gpt-5.6-luna
verified_at: 2026-08-28
context_window_tokens: 1050000
max_input_tokens: UNKNOWN
max_output_tokens: 128000
structured_output_support: YES
json_schema_support: YES
tool_function_support: YES
batch_support: YES
prompt_cache_support: YES
input_price: 0.20
cached_input_price: 0.02
output_price: 1.20
price_unit: per 1M tokens
currency: USD
rate_limit_public_info: Tier 1 500 RPM/500000 TPM; tiers rise to Tier 5 30000 RPM/180000000 TPM; account tier applies
service_tier_info: Standard public tiering; exact capacity remains account-dependent
data_used_for_training_default: NO, unless customer explicitly opts in
retention_default: Abuse-monitoring logs up to 30 days; Responses application state 30 days by default unless store=false
zero_data_retention_option: YES, eligible customers subject to approval and endpoint restrictions
regional_processing_option: YES, eligible regional projects
eu_data_residency_option: YES, EEA and Switzerland storage/processing subject to approval and ZDR/modified-abuse-monitoring requirements
embedding_models_available: YES, text-embedding-3-large and text-embedding-3-small
embedding_dimension_info_if_official: UNKNOWN in the selected official model card; verify before F
sdk_required: NO
raw_http_api_available: YES
python_sdk_available: YES
deprecation_policy: Public deprecations page and model catalogue; revalidate on notice
model_snapshot_or_alias_semantics: Explicit model ID; no broader alias selected
official_notes: Cost-sensitive/high-volume member; requests above 272K input have long-context multipliers; cache writes cost 1.25x input
unknowns: Exact max input; standard SLA; pedagogical quality relative to Terra/Sol; embedding dimensions on the cited card
```

### 4.4 Anthropic — Claude Sonnet 5

```yaml
provider: Anthropic
model_id: claude-sonnet-5
model_family: Claude Sonnet 5
model_status: ACTIVE
official_model_page: https://platform.claude.com/docs/en/docs/about-claude/models/whats-new-sonnet-5
verified_at: 2026-08-28
context_window_tokens: 1000000
max_input_tokens: UNKNOWN
max_output_tokens: 128000
structured_output_support: YES
json_schema_support: YES_WITH_LIMITATIONS
tool_function_support: YES
batch_support: YES
prompt_cache_support: YES
input_price: 2.00
cached_input_price: 0.20
output_price: 10.00
price_unit: per 1M tokens
currency: USD
rate_limit_public_info: Standard tier shown at up to 1000 RPM/2000000 ITPM/400000 OTPM for Sonnet 5; actual organization tier applies
service_tier_info: Standard available; Priority Tier is explicitly unavailable for Claude Sonnet 5
data_used_for_training_default: NO for commercial/API traffic unless explicit opt-in or feedback
retention_default: API inputs and outputs deleted within 30 days, subject to policy/legal exceptions
zero_data_retention_option: YES, approved enterprise API customers; exclusions apply
regional_processing_option: LIMITED; documented inference geography does not establish an EU-only guarantee
eu_data_residency_option: UNKNOWN
embedding_models_available: NO native Anthropic embedding model documented in the audited catalogue
embedding_dimension_info_if_official: UNKNOWN
sdk_required: NO
raw_http_api_available: YES
python_sdk_available: YES
deprecation_policy: Active; not sooner than 2027-06-30; at least 60 days notice for public model retirement
model_snapshot_or_alias_semantics: Dateless 4.6+ IDs are pinned releases, not evergreen aliases
official_notes: 1M context is default/max; adaptive thinking defaults on; strict structured outputs use a documented JSON Schema subset
unknowns: Exact max input; standard SLA; EU-only processing/residency; native embeddings
```

### 4.5 Google — Gemini 3.7 Flash

```yaml
provider: Google Gemini
model_id: gemini-3.7-flash
model_family: Gemini 3 Flash
model_status: STABLE_GA
official_model_page: https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash
verified_at: 2026-08-28
context_window_tokens: 1048576
max_input_tokens: 1048576
max_output_tokens: 65536
structured_output_support: YES_WITH_LIMITATIONS
json_schema_support: YES_WITH_LIMITATIONS
tool_function_support: YES
batch_support: YES
prompt_cache_support: YES
input_price: 0.75
cached_input_price: 0.075
output_price: 3.75
price_unit: per 1M tokens
currency: USD
rate_limit_public_info: Account/tier-dependent RPM, TPM and RPD; Tier 1 batch queue publicly lists 3000000 tokens for this model
service_tier_info: Standard, Batch, Flex and Priority consumption documented; capacity is not guaranteed
data_used_for_training_default: NO on paid services; YES/possible human review on unpaid services
retention_default: LIMITED_PERIOD_UNKNOWN for abuse logs; feature-specific storage may be 24 hours or 30 days
zero_data_retention_option: YES_WITH_ACTIONS_AND_APPROVAL; store=false and feature exclusions apply
regional_processing_option: UNKNOWN for the audited Gemini Developer API offer
eu_data_residency_option: UNKNOWN; EEA clients require Paid Services but that is not an EU-residency guarantee
embedding_models_available: YES, gemini-embedding-2
embedding_dimension_info_if_official: 128 to 3072; recommended 768, 1536 or 3072; max input 8192
sdk_required: NO
raw_http_api_available: YES
python_sdk_available: YES
deprecation_policy: Stable IDs usually do not change; deprecations page lists earliest shutdown dates; latest aliases hot-swap
model_snapshot_or_alias_semantics: gemini-3.7-flash is stable; do not use gemini-flash-latest
official_notes: Introductory price ends 2026-12-31, then 1.50 input/0.15 cached/7.50 output; JSON Schema subset only
unknowns: Standard SLA; exact abuse-log duration; EU processing/residency; pedagogical suitability under the age restriction
```

Important eligibility fact: the Gemini API Additional Terms effective
2026-03-23 prohibit an API Client directed toward, or likely to be accessed by,
people under 18. Projet V2 étant pédagogique, Gemini est donc exclu du chemin
d'implémentation initial tant qu'une revue juridique n'établit pas que le public
et le mode de déploiement sont compatibles.

### 4.6 Mistral AI — Mistral Medium 3.5

```yaml
provider: Mistral AI
model_id: mistral-medium-3-5
model_family: Mistral Medium 3
model_status: GA
official_model_page: https://docs.mistral.ai/models/mistral-medium-3-5-26-04
verified_at: 2026-08-28
context_window_tokens: 256000
max_input_tokens: UNKNOWN
max_output_tokens: UNKNOWN
structured_output_support: YES_WITH_LIMITATIONS
json_schema_support: YES_WITH_LIMITATIONS
tool_function_support: YES
batch_support: YES
prompt_cache_support: YES
input_price: 1.50
cached_input_price: 0.15
output_price: 7.50
price_unit: per 1M tokens
currency: USD
rate_limit_public_info: ACCOUNT_DEPENDENT; per-organization RPS and TPM, current values visible in the account limits page
service_tier_info: Standard; Priority Tier by agreement at 1.75x list price and 99.5% SLA; regional inference at 1.1x
data_used_for_training_default: NO for API data
retention_default: UNKNOWN for stateless chat content in the audited public docs; uploaded files are retained 30 days unless deleted sooner
zero_data_retention_option: YES, paid plans and approved organizations for supported stateless endpoints
regional_processing_option: YES, explicit EU and US endpoints
eu_data_residency_option: PARTIAL; EU inference processing is supported, but control-plane metadata may be handled elsewhere
embedding_models_available: YES, mistral-embed and codestral-embed
embedding_dimension_info_if_official: mistral-embed 1024; codestral-embed default 1536 and maximum 3072
sdk_required: NO
raw_http_api_available: YES
python_sdk_available: YES
deprecation_policy: GA has six-month notice; no silent updates for fixed GA IDs
model_snapshot_or_alias_semantics: Fixed major-minor ID; -latest and -major aliases can move and are rejected for the selected profile
official_notes: Modified MIT open weights; total context includes prompt plus output; structured output limitations require application validation
unknowns: Max input; max output; default stateless-content retention; standard SLA; pedagogical quality
```

### 4.7 Mistral AI — Mistral Small 4

```yaml
provider: Mistral AI
model_id: mistral-small-2603
model_family: Mistral Small 4
model_status: GA_OPEN_WEIGHT
official_model_page: https://docs.mistral.ai/models/mistral-small-4-0-26-03
verified_at: 2026-08-28
context_window_tokens: 256000
max_input_tokens: UNKNOWN
max_output_tokens: UNKNOWN
structured_output_support: YES_WITH_LIMITATIONS
json_schema_support: YES_WITH_LIMITATIONS
tool_function_support: YES
batch_support: YES
prompt_cache_support: YES
input_price: 0.15
cached_input_price: 0.015
output_price: 0.60
price_unit: per 1M tokens for Mistral-hosted API
currency: USD
rate_limit_public_info: ACCOUNT_DEPENDENT; per-organization RPS and TPM
service_tier_info: Hosted Standard; contractual Priority and regional options; self-hosted service level is operator-owned
data_used_for_training_default: NO for Mistral API; NOT_APPLICABLE to offline self-hosting
retention_default: UNKNOWN for hosted stateless content; operator-defined for self-hosting
zero_data_retention_option: YES for eligible hosted stateless calls; inherent control is deployment-dependent when self-hosted
regional_processing_option: YES for hosted regional endpoints; operator-defined when self-hosted
eu_data_residency_option: PARTIAL for hosted EU inference; operator-defined when self-hosted
embedding_models_available: YES, separate mistral-embed and codestral-embed offerings
embedding_dimension_info_if_official: mistral-embed 1024; codestral-embed default 1536 and maximum 3072
sdk_required: NO for hosted API; self-hosting runtime is a separate future decision
raw_http_api_available: YES for hosted API
python_sdk_available: YES for hosted API
deprecation_policy: GA hosted ID has six-month notice; Apache 2.0 weights remain separately usable
model_snapshot_or_alias_semantics: Explicit release ID; do not use moving aliases
official_notes: Apache 2.0, 119B parameters/6.5B active; official comparison lists roughly 60-238 GB GPU RAM depending on deployment
unknowns: Max input/output; hosted default retention; real local throughput/cost; schema reliability; French pedagogical quality
```

## 5. Confidentialité et fiabilité — conclusions factuelles

- OpenAI, Anthropic et Mistral annoncent que le trafic API commercial n'est pas
  utilisé pour entraîner les modèles par défaut. Gemini offre cette garantie
  uniquement sur les services payants.
- Les options ZDR des quatre providers ne sont pas une propriété implicite de
  tout appel : approbation, paramètres et exclusions de fonctionnalités
  s'appliquent.
- OpenAI documente une option EEA/Suisse avec stockage et traitement régionaux,
  mais elle impose des contrôles contractuels supplémentaires. Mistral documente
  un endpoint d'inférence UE, sans régionaliser tout le control plane.
  Anthropic et Gemini ne fournissent pas, dans les documents audités, une
  garantie standard équivalente : `EU_DATA_RESIDENCY = UNKNOWN`.
- Les quotas sont liés au compte ou au tier. Les tableaux publics sont des
  plafonds, pas une capacité garantie.
- Une SLA standard publique n'est pas retenue pour OpenAI, Anthropic ou Gemini.
  Mistral publie 99,5 % uniquement pour son Priority Tier contractuel.

## 6. Transport recommandé pour D/E

`TRANSPORT_DECISION = DEFER_EXACT_LIBRARY_TO_D`

Les quatre providers documentent un endpoint HTTPS brut et un SDK Python ; un
SDK n'est donc pas requis par le protocole. D doit comparer le SDK officiel
OpenAI au plus petit client HTTP déjà admissible par la politique de dépendance,
avec une décision explicite avant installation. E doit faire la même revue pour
Anthropic. Aucun SDK, client HTTP ni secret n'est ajouté en C. Le streaming ne
participe pas à la sélection initiale.

## 7. Baseline local/open-weight distincte

`LOCAL_OR_OPEN_WEIGHT_BASELINE = MISTRAL_SMALL_4_RESEARCHED_ONLY`

Mistral Small 4 apporte contrôle offline et licence Apache 2.0, mais son coût
local n'est pas nul : l'offre officielle indique 60 à 238 GB de mémoire GPU
selon la configuration. La fiabilité JSON, la qualité française/pédagogique, le
débit, la supervision et le coût complet restent `MEASURE_LATER`. Aucun runtime
Ollama/vLLM n'est installé et cette option n'est ni primary ni fallback cloud.

## 8. Embeddings — handoff F

- OpenAI : `text-embedding-3-small` à 0,02 USD/MTok et
  `text-embedding-3-large` à 0,13 USD/MTok ; dimensions à revalider dans la
  documentation de F avant configuration.
- Google : `gemini-embedding-2`, input maximal 8 192 tokens, dimensions 128 à
  3 072, recommandations 768/1 536/3 072.
- Mistral : `mistral-embed`, contexte 8K et dimension 1 024, et
  `codestral-embed`, dimension par défaut 1 536/maximale 3 072.
- Anthropic : aucune offre d'embedding native n'a été trouvée dans le catalogue
  officiel audité.

`EMBEDDING_PROVIDER_OPTIONS_RESEARCHED = TRUE`

`SEMANTIC_ACTIVATION_DECISION = DEFERRED_TO_12_16_F`

## 9. OFFICIAL_SOURCE_REGISTER

Toutes les sources ont été vérifiées le 2026-08-28.

| ID | Provider | URL officielle | Objet / faits supportés |
|---|---|---|---|
| OAI-01 | OpenAI | https://developers.openai.com/api/docs/models/compare | IDs, prix, contexte, output, features, tiers |
| OAI-02 | OpenAI | https://developers.openai.com/api/docs/models/gpt-5.6-sol | Sol, alias, prix promotionnel, long context |
| OAI-03 | OpenAI | https://developers.openai.com/api/docs/models/gpt-5.6-terra | Terra, endpoints, features, quotas |
| OAI-04 | OpenAI | https://developers.openai.com/api/docs/models/gpt-5.6-luna | Luna, prix, quotas, features |
| OAI-05 | OpenAI | https://developers.openai.com/api/docs/guides/latest-model | positionnement et prompt cache GPT-5.6 |
| OAI-06 | OpenAI | https://platform.openai.com/docs/models/default-usage-policies-by-endpoint | training, rétention, ZDR, régions |
| OAI-07 | OpenAI | https://developers.openai.com/api/docs/models/text-embedding-3-large | embeddings et prix |
| OAI-08 | OpenAI | https://developers.openai.com/api/docs/deprecations | dépréciations et migrations |
| ANT-01 | Anthropic | https://platform.claude.com/docs/en/models/overview | catalogue, contextes et outputs |
| ANT-02 | Anthropic | https://platform.claude.com/docs/en/docs/about-claude/models/whats-new-sonnet-5 | ID, contexte, output, features |
| ANT-03 | Anthropic | https://www.anthropic.com/research/claude-sonnet-5 | lancement et prix Sonnet 5 |
| ANT-04 | Anthropic | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | JSON Schema et limites |
| ANT-05 | Anthropic | https://platform.claude.com/docs/en/api/rate-limits | RPM, ITPM, OTPM, tiers |
| ANT-06 | Anthropic | https://platform.claude.com/docs/en/api/service-tiers | Standard/Priority et exclusion Sonnet 5 |
| ANT-07 | Anthropic | https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions | IDs, snapshots et aliases |
| ANT-08 | Anthropic | https://platform.claude.com/docs/en/about-claude/model-deprecations | statut et cycle de vie |
| ANT-09 | Anthropic | https://docs.anthropic.com/en/docs/about-claude/pricing | cache et batch pricing |
| ANT-10 | Anthropic | https://privacy.anthropic.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data | rétention API |
| ANT-11 | Anthropic | https://privacy.anthropic.com/en/articles/7996885-how-do-you-use-personal-data-in-model-training | usage training commercial |
| ANT-12 | Anthropic | https://privacy.anthropic.com/en/articles/8956058-i-have-a-zero-data-retention-agreement-with-anthropic-what-products-does-it-apply-to | ZDR et exclusions |
| ANT-13 | Anthropic | https://privacy.anthropic.com/en/articles/7996890-where-are-your-servers-located-do-you-host-your-models-on-eu-servers | localisation de traitement |
| GOO-01 | Google | https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash | ID, contexte, output, features |
| GOO-02 | Google | https://ai.google.dev/gemini-api/docs/latest-model | statut GA et migration |
| GOO-03 | Google | https://ai.google.dev/gemini-api/docs/pricing | prix, cache, batch, training tiers |
| GOO-04 | Google | https://ai.google.dev/gemini-api/docs/rate-limits | quotas et tiers |
| GOO-05 | Google | https://ai.google.dev/gemini-api/docs/structured-output | JSON Schema subset |
| GOO-06 | Google | https://ai.google.dev/gemini-api/docs/zdr | rétention et mesures ZDR |
| GOO-07 | Google | https://ai.google.dev/gemini-api/terms | âge, régions et usage des données |
| GOO-08 | Google | https://ai.google.dev/gemini-api/docs/models | versions stable/preview/latest |
| GOO-09 | Google | https://ai.google.dev/gemini-api/docs/deprecations | calendrier de dépréciation |
| GOO-10 | Google | https://ai.google.dev/gemini-api/docs/embeddings | offre et dimensions embeddings |
| MIS-01 | Mistral | https://docs.mistral.ai/models/mistral-medium-3-5-26-04 | Medium ID, contexte, prix, features |
| MIS-02 | Mistral | https://docs.mistral.ai/models/mistral-small-4-0-26-03 | Small ID, contexte, licence, features |
| MIS-03 | Mistral | https://docs.mistral.ai/inference/pricing | prix input/cache/output |
| MIS-04 | Mistral | https://docs.mistral.ai/studio/conversations/structured-output | JSON/custom schemas |
| MIS-05 | Mistral | https://docs.mistral.ai/resources/known-limitations | contexte total, quotas, batch, JSON |
| MIS-06 | Mistral | https://docs.mistral.ai/admin/monitor-comply/privacy-data-controls | training et privacy API |
| MIS-07 | Mistral | https://docs.mistral.ai/admin/monitor-comply/zero-data-retention | ZDR et exclusions |
| MIS-08 | Mistral | https://docs.mistral.ai/inference/regional-inference | endpoints UE/US et limites |
| MIS-09 | Mistral | https://docs.mistral.ai/inference/model-lifecycle | GA, aliases et préavis |
| MIS-10 | Mistral | https://docs.mistral.ai/inference/priority-tier | SLA et prix Priority |
| MIS-11 | Mistral | https://docs.mistral.ai/api | API HTTP, max_tokens et cURL |
| MIS-12 | Mistral | https://docs.mistral.ai/resources/sdks | SDK Python/TypeScript |
| MIS-13 | Mistral | https://docs.mistral.ai/models/mistral-embed-23-12 | embedding, contexte et prix |

`OFFICIAL_SOURCE_COUNT = 44`

`SECONDARY_SOURCE_COUNT = 0`

## 10. Staleness et revalidation

Revalidation obligatoire :

- avant D si ce snapshot a plus de 30 jours ;
- immédiatement lors de toute notification de dépréciation ou changement de
  conditions d'utilisation ;
- avant K1 si prix, IDs, lifecycle, ZDR ou disponibilité régionale ont changé ;
- au plus tard le 2026-11-20 pour le prix promotionnel de Sol et le 2026-12-15
  pour le changement tarifaire Gemini du 2027-01-01.

Une revalidation ne promeut pas automatiquement un nouveau modèle : elle met à
jour la matrice et passe par la gouvernance du lot concerné.

## 11. Gaps conservés

Les principaux `UNKNOWN` sont les maxima d'input OpenAI/Anthropic/Mistral, les
maxima d'output Mistral, les SLA standard, la rétention stateless Mistral et les
garanties UE standard Anthropic/Gemini. La qualité française, STMG/BTS, la
latence, la répétabilité du scoring, le taux de validité schema et le coût réel
ne sont pas des faits de catalogue : ils sont `MEASURE_LATER`.
