# ADR-P12-024 — Sécurité et lineage de review AG-04

## Statut

Accepté pour la Phase 12.9-F.

## Contexte

Les lots B à E ont introduit la frontière provider-neutral, la coordination,
la matérialisation C-10 et l'assessment CAP-V02. Ils ont explicitement différé
la validation des locators, le traitement de cible hostile, la propagation des
assessments security evidence et le hardening global du lineage.

AG-04 reste un reviewer descriptif. Il ne valide pas canoniquement, ne possède
aucune `PromotionPolicy`, ne suit aucun lien et n'exécute aucune instruction
présente dans la cible ou les evidence.

## Décision

Une frontière pure et stateless est ajoutée dans le package review :

```text
ResolvedReviewTarget + ReviewSecurityPolicy
                    + EvidenceSecurityAssessment caller-supplied
                              |
                              v
                    ReviewSecurityGuard
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
     locator / lineage checks       bounded lexical target scan
             |                                 |
             +----------------+----------------+
                              |
                              v
                  ReviewSecurityAssessment
                              |
                ALLOW / ALLOW_WITH_WARNINGS
                REPAIR_REQUIRED / REJECT
```

La disposition est une gate technique de matérialisation review. Elle n'est ni
un PASS métier, ni une validation, ni une décision de promotion.

## Réutilisation evidence

F réutilise directement :

- `EvidenceSecuritySignalCode` ;
- `EvidenceSecuritySignal` ;
- `EvidenceSecurityAssessment`.

Le package review importe uniquement leur module de modèles. Il ne réutilise
pas `EvidenceSecurityScanner`, car celui-ci opère sur `EvidenceSet` sous la
frontière AG-02. Le transformer en reviewer déplacerait ses invariants et son
autorité.

Chaque assessment caller-supplied est reconstruit pour détecter un objet forgé.
Ses IDs doivent rester bornés aux evidence C-09 et la clé du mapping doit être
présente dans les groupes effectivement évalués. Les invariants
`document_instructions_authoritative=False`, `external_actions_allowed=False`
et `links_followed=False` restent obligatoires.

## Locator technique fermé

Le contrat canonique `Finding.target_locator` n'est pas modifié. À la frontière
AG-04, F accepte seulement :

```text
text_span = {kind, start, end, quote}
json_path = {kind, path}
whole_target = {kind}  # opt-in policy et cible non ambiguë
```

Un `text_span` doit être borné et sa quote doit correspondre exactement au
snapshot texte. Un `json_path` est un tuple non vide de segments `str | int`,
sans wildcard ni langage d'expression, résolu uniquement dans le payload déjà
fourni. `whole_target` est désactivé par défaut et interdit si les deux formes de
cible sont présentes.

Il n'existe ni fuzzy matching, CSS, XPath, regex exécutable, lecture de fichier
ou résolution distante.

## Intégration CAP-V01

`semantic_review()` scanne la cible et les metadata techniques avant l'appel
outbound. Une disposition bloquée empêche donc tout appel port.

`ReviewResultMaterializationRequest` reçoit une `ReviewSecurityPolicy` et un
mapping immutable d'assessments evidence. Avant C-10 :

1. le Prepared et le résultat technique sont revalidés ;
2. les surfaces techniques sont contrôlées contre authority-smuggling ;
3. chaque locator est résolu contre `PreparedReviewCall.target` ;
4. le guard recalcule le fingerprint de cible et le scope evidence ;
5. une disposition bloquée empêche la matérialisation ;
6. les warnings/limitations sûrs sont propagés sans texte hostile brut.

## Intégration CAP-V02

`FindingsAssessmentRequest` reçoit la même policy et le même mapping evidence.
Tous les locators C-10 sont revalidés contre la cible exacte avant l'appel.

Le snapshot provider-neutral conserve les dix champs publics E et ajoute :

- un fingerprint de snapshot target ;
- un fingerprint déterministe par finding.

Le fingerprint finding couvre ID, dimension, severity, locator normalisé,
flag de correction et evidence refs. Il exclut tout raisonnement privé.

`ReviewAssessmentSignal` conserve les fingerprints et les codes security.
`CorrectionHandoffSignal` transporte seulement ces codes et les diagnostics
sûrs. Aucune URL activable ni instruction brute n'est ajoutée au handoff.

## Scanner cible

Le scanner lexical borné détecte uniquement des catégories fermées :

- contenu instruction-like ;
- privilege escalation ;
- exfiltration ;
- action tool/file ;
- URL ;
- claim d'autorité.

Il analyse les chaînes déjà présentes dans le snapshot fourni. Il ne suit pas
les URL, ne charge aucun fichier et n'exécute rien. Les sorties contiennent des
codes et un locator minimal `text`, `payload` ou `evidence`, jamais le contenu
brut.

## Policy et dispositions

Les defaults sont conservateurs : locator obligatoire, privilege escalation,
exfiltration et tool/file action rejetés ; instruction-like autorisée avec
warning ; URL autorisée comme donnée avec warning ; assessment evidence
optionnel tant qu'aucune policy stricte ne l'exige.

La priorité est :

```text
REJECT > REPAIR_REQUIRED > ALLOW_WITH_WARNINGS > ALLOW
```

`REPAIR_REQUIRED` et `REJECT` empêchent une sortie review mais ne mutent aucun
statut métier et ne déclenchent aucun retry, tool ou workflow.

## Authority-smuggling

Le vocabulaire review est étendu avec `promotion_allowed` et
`validator_passed`. Les clés sont contrôlées récursivement. Les metadata
techniques sont également refusées lorsqu'une valeur tente de transporter une
URL activable, une pseudo-instruction, une demande tool/file, une escalade ou
une exfiltration.

Le texte cible reste une donnée : il est signalé selon policy, jamais interprété
comme commande.

## Frontières d'autorité

F n'ajoute aucun provider, I/O, réseau, SQL, ORM, vector store, filesystem
métier, runtime, orchestration, registry ou access matrix. AG-04 ne construit
pas C-11, n'appelle pas AG-03/CAP-G03 et ne décide aucune promotion.

## Rationalisation B→F

Les primitives de modèles evidence sont réutilisées. Le scanner evidence n'est
pas factorisé avec le scanner review, car leurs inputs, leur ownership et leur
lineage diffèrent. Le guard generation n'est pas réutilisé pour la même raison.
Les helpers authority déjà présents dans review sont étendus sans introduire de
second vocabulaire concurrent.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```

## Responsabilités différées

- 12.9-G : intégration workflow et décisions ultérieures AG-01 ;
- 12.9-H : audit cumulatif et clôture finale.
