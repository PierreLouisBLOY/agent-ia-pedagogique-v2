# Phase 12.16-E — OpenAI Review + Anthropic EvaluationScorer baseline

Date de calibration : 2026-08-28.

## 1. Parent D

Le lot part du commit D exact
`943e2aa72ad7a7a43d6f3cd6b08a708485c6e9e9`, sur la branche
`phase12/12-16-provider-model-calibration`. `main` et `origin/main` étaient à
`7ae02ee109bcc6399ec0f71616da6aef07abda81`, la relation `main...HEAD` était
`0 3`, le merge-base était `main` et le worktree était propre.

## 2. Sources officielles revalidées

OpenAI a été revalidé par les fiches officielles
[`gpt-5.6-sol`](https://developers.openai.com/api/docs/models/gpt-5.6-sol) et
[`gpt-5.6-terra`](https://developers.openai.com/api/docs/models/gpt-5.6-terra),
la [Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create),
les [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
et le [SDK Python](https://developers.openai.com/api/reference/python). Sol et
Terra conservent un contexte annoncé de 1 050 000 tokens, un maximum de sortie
de 128 000 tokens et le support Responses/Structured Outputs.

Anthropic a été revalidé par la fiche officielle
[`claude-sonnet-5`](https://platform.claude.com/docs/en/docs/about-claude/models/whats-new-sonnet-5),
la [Messages API Python](https://platform.claude.com/docs/en/api/python/messages/create),
les [Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
le [SDK Python](https://platform.claude.com/docs/en/api/sdks/python) et les
[erreurs API](https://platform.claude.com/docs/en/api/errors). Le modèle exact
reste `claude-sonnet-5`, avec contexte 1M, sortie maximale 128K, structured
outputs supportés et tarif public constaté de 2 USD/MTok input et 10 USD/MTok
output. Sonnet 5 utilise l'adaptive thinking ; E n'envoie aucun bloc `thinking`
manuel ni `temperature`, `top_p` ou `top_k` non défaut.

## 3. Ownership Review

`OpenAIReviewAdapter`, sous
`backend/adapters/outbound/review/openai/`, implémente directement le
`ReviewPort` existant. L'adaptateur reste un reviewer technique : il ne possède
ni validation domaine, ni gate, ni promotion, ni retry, ni fallback. Les six
types `ReviewPort*` demandés restent byte-unchanged dans leur owner souverain :
`REVIEW_PORT_CONTRACT_DELTA = 0`.

## 4. Décision de transport OpenAI

L'audit a conclu que les DTO/status/usage/erreurs et le transport D étaient
provider-generic, mais mal localisés sous `generation.openai`. E applique donc
l'extraction minimale admise vers `backend/adapters/outbound/openai/`.
Generation/Correction et Review utilisent désormais le même seam et l'unique
`OpenAISDKResponsesTransport`. Le seul enrichissement du DTO request est le
`schema_name` technique : D continue d'envoyer `pedagogical_generation`, tandis
que Review envoie `technical_pedagogical_review`. Les comportements GENERATE,
CORRECT et TRANSFORM restent inchangés.

## 5. Mapping, schema, status et erreurs Review

Le mapper transmet explicitement step, opération, cible/version, dimensions,
contenu/payload, critères, références de preuve, contexte de couverture,
inputs résolus et contrat de sortie. Ces éléments sont décrits au modèle comme
des données non autoritatives. `SEMANTIC_REVIEW` et `ASSESS_FINDINGS` reçoivent
des instructions distinctes.

Le schema strict porte `outcome`, `structured_payload`,
`technical_findings`, `limitations`, `warnings`, `uncertainties` et
`evidence_refs_used`. Les références retournées sont résolues vers les objets
originaux à partir d'une allowlist canonique ; les findings, diagnostics,
payloads et vocabulaires interdits sont post-validés avant construction du
`ReviewPortResult`.

Le mapping est : output complet valide sans diagnostic → `SUCCEEDED`; output
valide limité/incomplet → `PARTIAL`; refus explicite → `REFUSED`; panne provider
→ `ReviewPortError.UNAVAILABLE`; réponse malformée → `INVALID_RESPONSE`; rejet
de borne request → `REQUEST_REJECTED`. Les metadata sont limitées à provider et
model codes/profile IDs, status et compteurs de tokens. Aucun texte cible,
prompt, secret, response ID ou objet SDK n'est exposé.

## 6. Ownership du scorer Anthropic

`AnthropicEvaluationScorer` vit exclusivement sous
`tests/providers/anthropic/`. Il implémente l'`EvaluationScorerPort` offline
existant et retourne uniquement `ScorerOutcome`. Aucun backend n'importe le
harness ou ce scorer ; le scorer ne devient jamais un composant runtime.
`EVALUATION_HARNESS_CORE_DELTA = 0` : contracts, ports, evaluator et runner du
harness ne sont pas modifiés.

## 7. Décision `tests/providers`

L'owner `tests/providers` est retenu parce qu'il peut combiner les value objects
du harness, la configuration provider-neutral et la frontière de secret sans
inverser les dépendances produit. Le SDK Anthropic n'est importé que dans
`tests/providers/anthropic/transport.py` et son test de transport colocalisé.
Cette décision est formalisée par ADR-P12-060.

## 8. Audit de suffisance de l'entrée scorer

La réponse est `SCORER_INPUT_SUFFICIENCY = YES`. Un
`EvaluationObservationValue` supporte déjà une algèbre fermée scalar, sequence
et object, avec codes de champs, profondeur, cardinalité, taille de chaîne et
nombre total de nœuds bornés. Un `ObservationObject` peut donc expliciter le
critère et les données nécessaires sans passer `criterion_ref` au port ni
créer un canal metadata caché.

## 9. Sérialiseur d'observations

Le sérialiseur est déterministe et accepte uniquement les classes exactes
`ObservationScalar`, `ObservationSequence` et `ObservationObject`. Chaque valeur
porte un discriminant `kind`; les `Decimal` deviennent une chaîne décimale
exacte, jamais un float. Les fields conservent leur ordre canonique et leur
`EvaluationObservationFieldCode`. Mapping arbitraire, `repr`, exception et objet
runtime sont rejetés.

## 10. Handoff du shape qualité vers G

Les observers G devront produire un `ObservationObject` synthétique/canonique
borné comprenant les codes de champs suivants : `criterion-code`,
`candidate-projection`, `pedagogical-level`, `task-kind` et
`reference-constraints`. Le critère doit être explicite dans l'observation ; le
contenu ne doit porter aucune donnée privée. E fournit la capacité de transport
et scoring, mais ne crée ni corpus ni observer G.

## 11. SDK Anthropic et dépendance

La dépendance runtime reste exactement `openai>=3.5,<4`. Le SDK Anthropic est
déclaré uniquement dans l'extra `calibration` comme `anthropic>=1.2,<2`. La
version publiée, installée et testée est `1.2.0`. Son nouveau top-level direct
est `docstring-parser 0.18.0`; les autres dépendances nécessaires étaient déjà
présentes via le SDK OpenAI (`anyio`, `httpx2`, `jiter`, `pydantic`, `sniffio`,
`typing-extensions`). Le dépôt n'étant historiquement pas installable comme
distribution editable en flat-layout, le SDK a été installé directement dans
le venv avec la borne exacte de l'extra ; cette limitation packaging préexiste
et ne change pas la séparation runtime/calibration.

## 12. Transport Anthropic

`AnthropicSDKScoringTransport` utilise le SDK officiel et
`client.messages.create`. Le client reçoit le secret uniquement via
`ProviderSecretValue.reveal_for_transport()`, le timeout exact du profil et
`max_retries=0`. L'appel est non streaming, sans outils, sans thinking manuel,
sans sampling non défaut, avec `output_config.format` JSON Schema et
`model=claude-sonnet-5`. Les refus, auth/permission, rate limit, timeout,
connexion, serveur et erreurs API deviennent des erreurs privées fermées sans
payload brut.

## 13. Schema de score

Le schema exige exactement `status`, `score_numerator` et
`score_denominator`. `SCORED` exige deux integers Python exacts, denominator
strictement positif et `0 <= numerator <= denominator`; `NormalizedScore`
applique la réduction canonique. `INCONCLUSIVE` exige deux valeurs nulles. Un
float, JSON incomplet, status inconnu, denominator nul ou score hors borne
devient `AnthropicScorerError.INVALID_RESPONSE`.

## 14. Intégration ScoreEvaluator

Les tests injectent le scorer Anthropic concret, avec transport fake, dans le
vrai `ScoreEvaluator`. `SCORED` devient un `ScoreResult` exact,
`INCONCLUSIVE` devient `SCORER_INCONCLUSIVE`, et toute erreur provider/malformed
privée devient `SCORER_EVALUATION_ERROR`. Aucune metadata provider n'est ajoutée
à `ScorerOutcome`; G/J porteront la provenance via la configuration du run et
les artefacts de reporting.

## 15. Indépendance cross-provider

Les factories prouvent la séparation suivante : Generation/Correction =
OpenAI, Review primary = `gpt-5.6-sol`, EvaluationScoring primary =
Anthropic `claude-sonnet-5`. Les routes déclarées peuvent conserver leurs
candidats fallback C, mais E ne lit ni n'exécute `fallback_model_profile_ids`.
Aucun scorer OpenAI dégradé n'est implémenté.

## 16. Live smoke

`LIVE_PROVIDER_CALIBRATION = NOT_YET_EXECUTED`. Aucun appel OpenAI ou Anthropic
réel n'est requis ou déclenché par pytest. Les tests utilisent uniquement des
données synthétiques et des transports fakes.

## 17. Gates et politique de dépendance

La sélection E passe à `49 passed`; la régression D ciblée à `144 passed`; les
fitness architecture complets à `713 passed`. La suite globale passe à
`4006 passed, 21 skipped`. Les 21 skips sont exclusivement les gates SQLite
réelles conditionnées par `PEDAGOGICAL_CANONICAL_SEED_PATH`; le seed canonique
105 553 920 octets attendu n'était pas configuré après redémarrage, et aucun
code SQLite/database n'a été modifié, ce qui applique la politique D. Les tests
provider Anthropic ont été exécutés explicitement avec le SDK installé, sans
skip. Ruff, mypy backend/harness, compileall et diff-check font partie de la
clôture E.

## 18. Handoffs F/G/H

F peut réutiliser la configuration provider-neutral sans coupler embeddings et
scoring. G doit construire les observers/corpus bornés et la provenance de run,
sans modifier `ScorerOutcome`. H/J pourront calibrer les candidats et traiter
explicitement toute perte d'indépendance d'un fallback. E n'exécute ni F, ni G,
ni calibration live, ni embeddings.

Après clôture : `NEXT_GATE = 12.16-F_READY`.
