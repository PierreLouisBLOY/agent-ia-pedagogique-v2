# ADR P12-015 — Frontière provider-neutral de génération AG-03

## Statut

Accepté.

## Contexte

AG-03 porte les responsabilités de génération, transformation et correction sous
les capabilities `CAP-G01`, `CAP-G02` et `CAP-G03`. Les contrats canoniques
`ProductionRequest`, `ProductionCandidate`, `CorrectionRequest` et
`CorrectionResult` existent déjà, mais ils ne définissent pas la frontière
technique entre une demande agentique préparée et un mécanisme génératif
remplaçable.

Sans frontière dédiée, une implémentation pourrait coupler le runtime à un SDK,
un modèle ou un dialecte de prompts, confondre une réponse technique avec une
production candidate, ou attribuer au mécanisme outbound des droits de
validation et de promotion.

## Décision

Le package `backend/agent_runtime/agents/generation/` définit une frontière
technique immutable et provider-neutral composée de :

- `GenerationOperation`, limité à `GENERATE`, `TRANSFORM` et `CORRECT` ;
- `GenerationPortRequest`, qui transporte uniquement des inputs déjà résolus,
  le `pedagogical_context` canonique, des contraintes déclaratives, références
  d’evidence fournies par le caller et forme de sortie attendue ;
- `GenerationPortResult`, qui transporte une sortie technique nominale, ses
  limitations et ses métadonnées neutres ;
- `GenerationPortError`, limité aux erreurs techniques `UNAVAILABLE` et
  `INVALID_RESPONSE` ;
- un unique Protocol runtime-checkable `GenerationPort.generate()`.

`GenerationPortResult` n’est pas un `ProductionCandidate`. Il ne contient ni
identité de production, ni lineage canonique, ni état de validation, ni décision
de gate ou permission. L’assemblage futur d’une sortie technique vers un contrat
agentique restera une responsabilité distincte.

Les concepts demeurent séparés :

```text
CAP-G01/G02/G03 = droit et intention agentiques
GenerationOperation = nature technique de l’appel préparé
GenerationPort = mécanisme outbound remplaçable
ProductionRequest/CorrectionRequest = contrats canoniques d’entrée
GenerationPortResult = sortie technique
ProductionCandidate = sortie agentique non canonique
```

Un seul `generate()` est retenu parce que les trois opérations partagent le même
mécanisme technique et sont distinguées explicitement dans la requête. Trois
ports identiques dupliqueraient la boundary et risqueraient de transformer les
capabilities en API fournisseur.

La boundary n’importe aucun SDK provider, framework, module métier, adapter ou
infrastructure. Elle ne choisit ni modèle, endpoint, prompt renderer ou template.
Elle n’effectue aucun HTTP, SQL, accès repository ou filesystem, retry, fallback
ou repair loop.

Les références d’evidence sont exclusivement fournies par le caller. La
boundary ne recherche rien, ne construit aucun `EvidenceSet` et ne décide pas de
l’autorité d’une source. Elle ne valide, ne promeut et ne persiste aucune
production, et n’appelle aucun use case Application.

Le mapping actif de C-07 `ProductionRequest` et C-11 `CorrectionRequest`, la
préparation d’inputs et les contrôles anti-mismatch request/result sont différés
à 12.8-C/E. L’agent et l’assemblage `ProductionCandidate` sont différés à 12.8-D,
la correction complète à 12.8-E, le hardening à 12.8-F, l’intégration workflow à
12.8-G et la rationalisation finale à 12.8-H. Les adapters provider, le choix de
modèle et le prompt renderer restent différés à leurs lots dédiés.

`GenerationPortRequest.pedagogical_context` transporte explicitement le contexte
pédagogique de C-07 comme donnée immutable et non autoritaire. Il reste distinct
de `resolved_inputs`, qui contient uniquement des inputs additionnels déjà
résolus par l’amont ; aucun des deux champs ne remplace ou ne fusionne l’autre.

## Conséquences

- le runtime canonique reste indépendant des providers génératifs ;
- une sortie technique ne peut représenter une validation ou une promotion ;
- AG-03 ne gagne aucun accès autonome aux données ou à la recherche ;
- la suffisance d’evidence peut être signalée sans autoriser l’invention ;
- les adapters futurs pourront être remplacés sans modifier les contrats
  agentiques ;
- la cohérence `evidence_refs_used ⊆ evidence_refs` pourra être contrôlée par le
  coordinator futur qui connaît simultanément requête et résultat.

## Alternatives rejetées

- utiliser directement `ProductionCandidate` comme résultat du provider : cela
  fusionnerait sortie technique et sortie agentique ;
- créer un port par capability : cela dupliquerait le même mécanisme outbound ;
- placer le SDK ou le prompt renderer dans `agent_runtime` : cela violerait la
  neutralité provider ;
- autoriser AG-03 à chercher ses propres sources : cela contournerait AG-02 et
  les frontières d’autorité ;
- valider ou promouvoir automatiquement la sortie : cela violerait la séparation
  génération, validation et promotion.
