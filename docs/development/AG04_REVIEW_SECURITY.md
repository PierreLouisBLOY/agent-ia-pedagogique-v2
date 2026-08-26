# AG-04 — Sécurité review et lineage

## Portée 12.9-F

La sécurité AG-04 est une frontière descriptive et déterministe. Elle protège
CAP-V01 et CAP-V02 contre les locators obsolètes, les snapshots forgés, les
evidence security hors scope et l'authority-smuggling. Elle n'accorde aucune
permission métier.

## Policy caller-supplied

`ReviewSecurityPolicy` est frozen/slotted. Ses defaults imposent :

- validation locator obligatoire ;
- assessment evidence optionnel, activable strictement par le caller ;
- blocage privilege escalation, exfiltration et tool/file action ;
- instruction-like et URL conservées comme données avec warnings ;
- `whole_target` désactivé ;
- warning evidence non bloquant, sauf policy explicite.

Les dispositions techniques sont `ALLOW`, `ALLOW_WITH_WARNINGS`,
`REPAIR_REQUIRED` et `REJECT`. Les deux dernières empêchent une sortie review,
sans statut métier PASS/FAIL et sans retry automatique.

## Locators supportés

### Texte

```python
{
    "kind": "text_span",
    "start": 0,
    "end": 5,
    "quote": "Exact",
}
```

Les indices sont des entiers stricts, bornés par `target.content`, et la quote
doit correspondre exactement à la tranche.

### Payload structuré

```python
{
    "kind": "json_path",
    "path": ("sections", 0, "title"),
}
```

La résolution se fait uniquement dans `target.structured_payload`. Les segments
sont des clés ou indices exacts. Wildcards, expressions, CSS, XPath et regex
exécutables sont interdits.

### Cible entière

```python
{"kind": "whole_target"}
```

Ce locator exige `allow_whole_target_locator=True` et une seule représentation
de cible, afin d'éviter toute ambiguïté.

## Evidence security AG-02

Les requests de matérialisation et d'assessment acceptent :

```python
evidence_security_by_ref: Mapping[ContractRef, EvidenceSecurityAssessment]
```

Le mapping est copié dans une vue immutable. Chaque assessment est reconstruit
et revalidé. Sa clé et tous ses IDs doivent appartenir aux evidence C-09. Quand
`require_evidence_security_assessment=True`, chaque evidence effectivement
utilisée doit être couverte.

Les signaux AG-02 ne deviennent jamais des instructions. Ils produisent au plus
un warning sûr `EVIDENCE_SECURITY_WARNING_PRESENT`, sans contenu evidence brut.
Les flags authoritative/actions/links doivent rester `False`.

## Scanner cible

`ReviewSecurityGuard` parcourt seulement le texte et le payload déjà résolus par
le caller. Il détecte des marqueurs fermés d'instruction, escalade, exfiltration,
tool/file, URL et claim d'autorité.

Il ne fait aucun I/O :

- aucune URL suivie ;
- aucun fichier ouvert ;
- aucun tool exécuté ;
- aucun réseau ;
- aucun contenu brut dans erreur, warning ou limitation.

## CAP-V01

Avant l'appel provider, `semantic_review()` contrôle la cible et les inputs
techniques. Avant C-10, `build_review_result()` :

1. revalide Prepared/result ;
2. refuse les metadata d'autorité ou activables ;
3. résout chaque locator contre la cible exacte ;
4. lie les assessments evidence ;
5. bloque `REPAIR_REQUIRED`/`REJECT` ;
6. propage uniquement diagnostics sûrs.

## CAP-V02

Avant l'assessment, chaque finding C-10 est revalidé contre la cible. Le snapshot
contient un fingerprint target et un fingerprint par finding. Le signal final
conserve ces fingerprints ainsi que les codes security.

Le handoff AG-01 reste non canonique. Il conserve blocking/correction/evidence
et diagnostics security, mais ne contient ni URL activable, instruction brute,
capability CAP-G03, C-11, handler, tool, permission ou décision de promotion.

## Lineage garanti

```text
target ref + target snapshot fingerprint
request run/step/correlation
capability + operation
review_id + review_ref
finding fingerprints
finding evidence ⊆ C-10 used evidence ⊆ C-09 evidence
assessment evidence ⊆ C-09 evidence
handoff evidence = union déterministe des findings concernés
```

Toute dérive échoue avec un code fermé et une raison agent-safe qui ne reprend
jamais le texte cible ou evidence.

## Frontières conservées

La sécurité review n'importe aucun runtime/orchestration/provider. Elle ne
réutilise ni `GenerationOutputGuard` ni `EvidenceSecurityScanner`. Elle ne suit
aucun lien, ne charge aucun filesystem métier, ne construit aucun C-11 et ne
modifie aucun statut métier.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
