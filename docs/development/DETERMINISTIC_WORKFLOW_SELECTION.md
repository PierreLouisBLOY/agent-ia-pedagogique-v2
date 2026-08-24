# Sélection déterministe des workflows

## Portée

`WorkflowSelector` transforme uniquement des exigences déjà explicites en une
composition de topologies WF-0 à WF-11. Il ne lit ni texte utilisateur ni
intention libre, n'appelle aucun LLM et ne produit aucun raisonnement privé. Les
reason codes fermés rendent la décision descriptive et auditable.

Le catalogue 12.6-B demeure l'unique source des topologies. Chaque stage retenu
est résolu dans `WorkflowCatalog` et toute responsabilité optionnelle
matérialisée doit appartenir au descriptor correspondant.

## Chemin canonique minimal

| Exigences explicites | Sélection |
| --- | --- |
| Action Application ou validation seule | WF-0 |
| Evidence seule | WF-1 |
| Production seule | WF-2 |
| Review seule | WF-3 |
| Evidence + production | WF-4 |
| Production + review | WF-5 |
| Evidence + production + review | WF-6 |
| Evidence + review sans production | WF-1 puis WF-3 |
| Correction | WF-7 |
| Variantes utiles | WF-9 |
| Promotion seule | WF-11 |

Une validation déterministe explicite matérialise
`DETERMINISTIC_VALIDATION` dans WF-2, WF-4 ou WF-5. WF-6 et WF-11 la portent
déjà comme responsabilité requise. Une validation d'artefact existant ajoute
WF-0 avant WF-3. Après WF-7 ou WF-9, WF-0 représente la validation Application
sans modifier leurs descriptors.

Une action Application générique combinée à du travail agentique est refusée :
le caller doit normaliser l'effet concret au lieu de transformer WF-0 en
fourre-tout caché.

## Parallélisme et compositions

WF-8 n'est retenu que si au moins deux branches evidence sont demandées et
explicitement indépendantes. Sinon, evidence reste séquentielle et le reason
`PARALLEL_EVIDENCE_NOT_ADMISSIBLE` explique le fallback. Pour une continuation
de production, les compositions WF-8 → WF-4 et WF-8 → WF-6 indiquent que le
JOIN satisfait l'entrée evidence ; le futur compilateur ne devra pas relancer
AG-02.

WF-9 n'est retenu que pour `variant_count >= 2` avec pluralité explicitement
utile. Il reste un unique stage de topologie : le selector ne crée ni N branches
ni N WF-2. Une validation suit WF-9 via WF-0 et une review indépendante suit la
Production sélectionnée via WF-3.

WF-7 exprime correction puis review optionnelle sans cycle. Le selector
n'appelle pas `PlanRevisionEngine`; les nouvelles étapes et versions de plan
restent différées.

## Gates et promotion

Une gate humaine non bloquante ajoute uniquement l'overlay WF-10 au chemin
normal. WF-10 n'est jamais un moteur autonome. Son placement précis dans le DAG
relève de 12.6-D.

Une ambiguïté bloquante arrête la sélection avant tout workflow métier : la
décision passe à `waiting_human`, sans stage, avec le seul overlay WF-10 et des
reasons explicites d'ambiguïté et de gate humaine.

Une promotion ajoute WF-11 exactement une fois et en dernier. Sa validation, sa
gate policy et sa promotion restent des responsabilités Application ; aucune
`GateDecision` n'est évaluée par le selector.

## Frontières différées

La sélection ne construit aucun `Plan` ni `StepSpec`. La compilation commence en
12.6-D. Les agents spécialisés restent 12.7 à 12.9, les permissions, le routing
concret et les gates d'exécution restent 12.10, et le recovery reste 12.11.
