# AgentRegistry

`backend/agent_runtime/registry/agents.py` expose le catalogue runtime immutable
des quatre agents canoniques :

| ID | Nom canonique | Role | Capabilities primaires |
| --- | --- | --- | --- |
| AG-01 | AG-01 — Orchestrateur | ORCHESTRATOR | CAP-O01..CAP-O06 |
| AG-02 | AG-02 — Evidence/Retrieval | EVIDENCE_RETRIEVAL | CAP-E01..CAP-E03 |
| AG-03 | AG-03 — Generator/Transformer | GENERATOR_TRANSFORMER | CAP-G01..CAP-G03 |
| AG-04 | AG-04 — Reviewer/Critic semantique | REVIEWER_CRITIC | CAP-V01..CAP-V02 |

AG-01 est l'unique orchestrateur. Le Boss Agent est ce role d'AG-01, pas un
cinquieme agent. AG-04 est un reviewer/critic et ne devient pas un agent
`Validator`.

Le registry fournit uniquement `get`, `contains` et `all`. Il decrit le runtime,
mais n'est jamais une source d'autorite metier. Il ne peut executer ni capability,
ni tool, ni use case.
