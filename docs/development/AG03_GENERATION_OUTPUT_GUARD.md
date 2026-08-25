# AG-03 — Guard déterministe des sorties de génération

La Phase 12.8-F impose un assessment explicite avant toute matérialisation
G01/G02/G03 :

```text
Prepared call + GenerationPortResult
+ policy technique caller-supplied
+ attributions de claims déclarées
→ GenerationOutputGuard.assess()
→ GenerationGuardAssessment
→ revalidation déterministe
→ ProductionCandidate / CorrectionResult seulement si autorisé
```

## Dispositions

La priorité est fermée :

```text
REJECT > ABSTAIN > REPAIR_REQUIRED > ALLOW_WITH_WARNINGS > ALLOW
```

Seuls `ALLOW` et `ALLOW_WITH_WARNINGS` autorisent la matérialisation.
`REPAIR_REQUIRED` contient une proposition structurelle sans méthode
d'exécution. `ABSTAIN` couvre notamment l'absence de preuve utilisée lorsque le
grounding est requis ainsi que les statuts techniques sans sortie. `REJECT`
couvre les incohérences non réparables et l'élargissement du corpus déclaré.
Une lineage Prepared/résultat incohérente échoue plus tôt avec
`GenerationGuardError`; aucun assessment exploitable n'est alors émis.

## Grounding structurel, pas sémantique

Les classes de claims sont `DETERMINISTIC`, `GROUNDED`, `SYNTHESIZED`,
`GENERATED_PEDAGOGICAL`, `UNKNOWN` et `CONFLICTED`. Les classes liées aux preuves
imposent seulement une forme et des références dans le corpus utilisé.

```text
NO_EVIDENCE_NO_GROUNDED_CLAIM = enforced structurally
SOURCE_MATCH = deferred to review/validation mechanisms
```

Une référence ne prouve donc ni support sémantique, ni autorité, ni qualité.

## Structure et signaux de contenu

La policy peut exiger un payload, des clés top-level ou un mapping de sections
nommé explicitement. Le guard n'implémente ni JSON Schema général ni CAP-T01.
Pour G03, il ne déduit aucune section de C-11.

Le scanner recherche des patterns FR/EN fermés pour : instruction, escalade de
privilège, exfiltration, action outil/fichier, URL et revendication d'autorité.
Il scanne `content` et toutes les feuilles string de `structured_payload`, sans
suivre l'URL, lire de fichier ou appeler d'outil. Un signal contient seulement
son code et un chemin logique. Il ne qualifie jamais le contenu de malicious,
safe, trusted ou validated.

Les fragments fermés sont définis dans `_SECURITY_PATTERNS` : variantes de
`ignore previous/all instructions`, `system prompt`, `ignore les instructions`,
`disregard prior instructions`, `administrator/admin/elevated privileges`,
`root access`, `bypass permissions`, `sudo`, `droits administrateur`,
`exfiltrate`, `send secrets`, `upload credentials`, `send data to`,
`exfiltrer/envoyer les secrets`, `run/execute command`, `read/write/delete file`,
`open file`, leurs équivalents français, et les formulations
`validated/approved/trusted/safe/canonical output`, `authoritative`, `officially
approved`, `this is validated`, `fait autorité`, `source officielle` ou `sortie
validée/approuvée/sûre/canonique`. Les URL sont
détectées uniquement par les préfixes `http://`, `https://` et `www.`.

Pour `ALLOW_WITH_WARNINGS`, chaque signal devient :

```text
{"code": <code>, "origin": "AG03_OUTPUT_GUARD", "location": <chemin>}
```

Ces warnings s'ajoutent aux warnings techniques de C-08 et, pour G03, à
`CorrectionResult.new_warnings` sans modifier les findings déclarés.

## Frontières

Le guard est stateless et sans port. Il ne recherche aucune evidence, n'importe
pas AG-02, ne suit aucune URL et n'effectue aucun provider, I/O, retry, repair,
review, validation, promotion ou persistance. Le contrôle authority-free D sur
les metadata reste séparé car il bloque, tandis que les signaux de contenu F
restent des indicateurs non autoritatifs.
