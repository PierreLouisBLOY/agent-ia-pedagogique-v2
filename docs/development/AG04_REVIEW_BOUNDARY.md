# AG-04 — Frontière technique provider-neutral de review

## Responsabilité

AG-04 est le Reviewer/Critic sémantique indépendant. Il produit une critique et
des findings structurés sur une version exacte. Il n'est pas le Validator
canonique et ne possède aucune autorité de validation, promotion, correction ou
persistance.

Les deux capabilities existantes restent inchangées :

| Capability | Opération technique B |
|---|---|
| `CAP-V01 semantic_review` | `SEMANTIC_REVIEW` |
| `CAP-V02 assess_findings` | `ASSESS_FINDINGS` |

Cette correspondance est documentaire. Le lot B ne crée aucun dispatcher et ne
décide pas encore comment un futur coordinator prépare chaque capability.

## Frontière 12.9-B

`ReviewPortRequest` transporte exclusivement des données déjà résolues par le
caller : source step, opération, capability opaque, `ObjectVersionRef` cible,
contenu ou payload cible, dimensions, critères, evidence refs autorisées,
contexte de couverture, resolved inputs, output contract et budget éventuel.

`ReviewPort` expose une unique méthode synchrone provider-neutral :

```text
review(request=ReviewPortRequest) -> ReviewPortResult
```

`ReviewPortResult` transporte seulement un statut technique, un payload
structuré, des findings techniques non canoniques, les evidence refs déclarées
utilisées, limitations, warnings, uncertainties et metadata d'exécution.
Il n'est ni `ReviewResult`, ni `Finding`, ni décision de validation.

## Données caller-supplied

Le port ne résout aucune référence, ne charge aucune production et ne recherche
aucune evidence. Le contenu cible, les criteria, les evidence refs, le contexte
de couverture, les resolved inputs et l'output contract sont fournis en amont.
Le futur coordinator devra lier ces données au snapshot canonique et vérifier le
résultat retourné contre ce snapshot.

## Review distincte de validation

Les statuts `SUCCEEDED`, `PARTIAL`, `REFUSED` et `FAILED` décrivent uniquement
l'appel technique. Aucun statut `PASS`/`FAIL`, `validated`, `promoted`,
`canonical`, `trusted` ou `safe` n'est créé. L'`overall_assessment` canonique et
les règles de promotion restent hors B et sous leurs autorités respectives.

## Sécurité et limites

- les mappings réutilisent `freeze_agent_safe_mapping` ;
- les surfaces de résultat refusent les clés privées, sensibles et d'autorité ;
- les erreurs utilisent des codes et messages fermés, sans contenu brut ;
- aucune URL n'est suivie et aucun réseau, fichier, tool ou repository n'existe ;
- `GenerationOutputGuard` et `EvidenceSecurityScanner` ne deviennent pas des
  moteurs de review ;
- les metadata techniques restent non autoritatives et devront être revalidées.

Le fake `RecordingReviewPort` est strictement test-only. Il enregistre un appel,
retourne un résultat configuré ou propage une erreur configurée, sans routage,
retry ou effet externe.

## Responsabilités différées C→H

- C : préparation, résolution, coordinator et contrôle source step/opération ;
- D : reviewer et matérialisation des contrats canoniques existants ;
- E : assessment des findings, blocking et handoff vers AG-01 ;
- F : sécurité complète, locator/evidence lineage et anti-forgery ;
- G : preuves WF-3/5/6/7/10/11 et fitness d'autorité ;
- H : rationalisation et clôture canonique.

La proximité formelle des ports evidence, génération et review ne justifie pas
leur fusion : aucune consolidation sûre n'est disponible dans ce lot.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
