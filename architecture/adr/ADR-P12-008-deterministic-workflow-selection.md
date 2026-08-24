# ADR P12-008 - Sélection déterministe des workflows

## Statut

Accepté.

## Contexte

Le catalogue 12.6-B fige douze topologies provider-neutral, mais ne choisit pas
laquelle employer. La Phase 12.6-C doit produire une décision déclarative à
partir de besoins déjà normalisés sans interpréter de texte, appeler un modèle,
compiler un plan ou acquérir une autorité métier.

## Décision

`backend/agent_runtime/orchestration/selection/` contient un selector pur et
déterministe. Son entrée `WorkflowRequirements` porte seulement des faits
explicites et strictement typés. Sa sortie immutable contient des stages, un
éventuel overlay WF-10 et des reason codes fermés, sans rationale libre, score ou
confidence artificielle.

`WorkflowCatalog` reste l'unique source des descriptors. Le selector consulte le
catalogue pour chaque kind choisi et refuse un kind absent ou une responsabilité
optionnelle incompatible. Il ne recopie pas les douze descriptors et ne crée
aucun workflow supplémentaire.

La sélection préfère le chemin canonique minimal. Le parallélisme evidence exige
au moins deux branches réellement indépendantes ; sinon le chemin reste
séquentiel. Les variantes exigent une pluralité explicitement utile. WF-10 reste
un overlay et une ambiguïté bloquante arrête la décision avant tout stage métier.
WF-11 est terminal et unique lorsqu'une promotion est demandée.

Les compositions telles que WF-8 → WF-4/WF-6, WF-9 → WF-0 → WF-3 ou evidence →
WF-7 sont déclaratives. Elles ne créent ni branches, ni handoff, ni DAG. Le
selector ne construit aucun `Plan` ou `StepSpec`, n'évalue aucune permission et
ne route vers aucun agent, provider, handler ou use case.

## Conséquences

- une même entrée explicite produit toujours les mêmes stages et reasons ;
- les ambiguïtés bloquantes ne déclenchent aucune spéculation ;
- le caller doit normaliser toute action Application générique combinée à un
  workflow agentique ;
- la compilation reste 12.6-D, les agents spécialisés 12.7-12.9, le routing et
  les gates 12.10, et le recovery 12.11 ;
- `AccessMatrix`, `PermissionScope` et les policies conservent seuls leurs rôles
  d'autorisation : la sélection n'accorde aucune permission.
