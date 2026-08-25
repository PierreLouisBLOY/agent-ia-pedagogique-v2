# AG-03 — Frontière technique de génération

## Rôle et capabilities

AG-03 est le spécialiste `Generator/Transformer`. Ses capabilities exactes sont :

| Capability | Intention agentique |
| --- | --- |
| `CAP-G01` | `generate_production` |
| `CAP-G02` | `transform_production` |
| `CAP-G03` | `correct_production` |

Elles appartiennent à la classe `GENERATE_TRANSFORM`, suivent la route `AGENT`,
sont possédées par AG-03 et portent le risque `R1`. Elles ne sont pas des
méthodes du port technique.

## Chaîne de concepts

```text
canonical request
→ prepared GenerationPortRequest
→ GenerationPort
→ GenerationPortResult
→ later assembly
→ ProductionCandidate
```

`ProductionRequest` et `CorrectionRequest` sont des contrats canoniques d’entrée.
`GenerationPortRequest` est une requête technique préparée. `GenerationPort` est
le mécanisme outbound remplaçable. `GenerationPortResult` est une sortie
technique et ne constitue jamais un `ProductionCandidate`.

Le contexte suit une lineage explicite :

```text
ProductionRequest.pedagogical_context
→ GenerationPortRequest.pedagogical_context
```

Cette copie est exacte, profondément immutable et non autoritaire. Elle reste
distincte de `resolved_inputs`, qui transporte seulement les inputs additionnels
déjà résolus et autorisés par l’amont.

`GenerationOperation` décrit uniquement la nature technique de l’appel :
`GENERATE`, `TRANSFORM` ou `CORRECT`. Le mapping conceptuel vers CAP-G01/G02/G03
n’est pas un routeur et n’est pas exécuté par la boundary B.

## Frontières d’autorité

La boundary ne crée ni capability, `PermissionScope`, `GateDecision`, invocation
agentique ou décision de workflow. Les contraintes et contenus transportés sont
des données non autoritatives : ils ne peuvent déclencher un outil, modifier une
permission, approuver une gate, valider ou promouvoir une production.

AG-03 ne dispose d’aucune recherche autonome. `evidence_refs` est fourni par le
caller et `evidence_refs_used` permet un futur contrôle de sous-ensemble. Le port
ne lance aucune recherche, ne construit aucun `EvidenceSet` et ne décide pas de
la suffisance métier des sources. Le statut technique
`INSUFFICIENT_EVIDENCE` exprime une limite ; il n’autorise jamais à inventer.

La frontière n’effectue aucun accès direct SQL, repository, filesystem ou use
case Application. Elle ne persiste, ne valide et ne promeut rien. AG-03 ne peut
pas s’auto-évaluer et n’acquiert aucune capability CAP-E, CAP-V, CAP-A ou CAP-O.

## Neutralité provider

`GenerationPort` possède un seul point d’entrée :

```python
def generate(
    self,
    *,
    request: GenerationPortRequest,
) -> GenerationPortResult:
    ...
```

Le package ne choisit aucun provider, modèle, endpoint, paramètre d’échantillonnage,
prompt, template ou dialecte structuré. Aucun SDK, HTTP, retry, fallback ou repair
loop n’est introduit. Les implémentations concrètes appartiendront à de futurs
adapters outbound.

## Lots différés

- 12.8-C : mapping des contrats canoniques, préparation des inputs, lineage et
  contrôle anti-mismatch request/result ;
- 12.8-D : `GeneratorAgent`, CAP-G01/G02 et assemblage `ProductionCandidate` ;
- 12.8-E : CAP-G03, contexte de correction et `CorrectionResult` ;
- 12.8-F : grounding complet, hardening des sorties et structured-output repair ;
- 12.8-G : compatibilité des workflows et fan-out de variantes ;
- 12.8-H : rationalisation et clôture finale.

La Phase 12.8-B ne commence aucun de ces lots.
