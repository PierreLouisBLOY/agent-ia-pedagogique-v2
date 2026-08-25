# ADR P12-014 - Hardening et expansion bornée des preuves AG-02

## Statut

Accepté.

## Contexte

La matérialisation 12.7-D conserve désormais la lignée C-05, la source policy
et la provenance détaillée. Les contenus documentaires restent cependant des
données non fiables : ils peuvent contenir des instructions, des URL, des
tentatives d'escalade ou des copies qui ressemblent artificiellement à une
corroboration. Par ailleurs, une couverture insuffisante peut justifier une
nouvelle recherche, mais Phase 11.15 interdit toute récursion ouverte d'AG-02.

Phase 11.14 définit les principes de sécurité globaux et le concept de
`SecurityEvent`. Les lots 12.12/12.13 traiteront leur application transverse et
leur observabilité. Le présent lot doit donc rester evidence-local, sans créer
un événement concurrent, un bus ou un nouveau mécanisme d'autorité.

## Décision

### Indicateurs de sécurité evidence-locaux

`EvidenceSecurityScanner` est un scanner pur et déterministe. Il évalue un
`EvidenceSet` sans port, réseau, filesystem ou provider. Des patterns fermés
FR/EN et insensibles à la casse signalent les textes ressemblant à des
instructions, escalades, exfiltrations ou actions d'outil/fichier. La présence
textuelle de `http://` ou `https://` est signalée, jamais parsée ou suivie.

Les dix `EvidenceSecuritySignalCode` sont des indicateurs. Ils ne déclarent ni
`SAFE`, ni `TRUSTED`, ni `MALICIOUS`, ne retirent aucun item et ne changent
aucune policy, permission, capability ou gate. Le texte source reste inchangé.
Les avertissements upstream restent des reason codes sans severity inventée.
Un `SECURITY_WARNING:<CODE>` ne produit un signal item-level que si ses evidence
IDs sont explicitement attribuables. Sans ID, il devient uniquement la
limitation globale `UNATTRIBUTED_UPSTREAM_SECURITY_WARNING:<CODE>` : il n'est
jamais attribué artificiellement à tous les items. Une staleness globale non
attribuable suit la même règle de non-invention et ne produit aucun signal.

Les divergences de version sont signalées sans supprimer de version. Deux
items de même source, locator et version/checksum appartiennent au même groupe
de corroboration indépendante et produisent `DUPLICATE_CORROBORATION`. Deux
sources différentes ayant exactement le même contenu non vide et la même
version produisent `CROSS_SOURCE_DUPLICATE_CONTENT`, tout en restant dans des
groupes indépendants distincts. Aucune similarité fuzzy, sémantique ou par
embedding n'est calculée.

### Historique minimal et proposition d'expansion

`EvidenceRoundRecord` conserve uniquement la demande, les clés d'identité de
retrieval, les evidence IDs, la couverture et les codes de sécurité. Il ne
stocke aucun contenu, excerpt, prompt ou payload fournisseur. Sa factory valide
la lignée demande/retrieval et les run/correlation IDs de l'EvidenceSet.

`EvidenceExpansionHistory` exige des rounds contiguës à partir de 1, le même
run/correlation, scope, source policy, filtres et autorité requise. Le step ID et
le search goal peuvent évoluer. La borne `max_items` initiale ne peut jamais
être élargie.

`EvidenceExpansionAdvisor` consomme un `EvidenceExpansionNeed` explicite fourni
par le caller. Il ne déduit jamais un besoin depuis le contenu documentaire. La
baseline est liée à `AgentRuntimePolicy.max_evidence_rounds`, soit trois rounds,
et borne chaque proposition à 12 items ou à la borne initiale plus étroite.
Une valeur demandée supérieure échoue avec `MAX_ITEMS_WIDENING`; elle n'est pas
tronquée silencieusement.

Avant toute branche de décision, l'advisor lie l'assessment de sécurité à la
dernière round. Les evidence IDs reconstruits depuis les groupes de
corroboration doivent correspondre exactement, dans le même ordre, aux IDs du
record courant. Les codes dédupliqués des signaux doivent être identiques aux
codes snapshotés. Toute divergence échoue avec
`SECURITY_ASSESSMENT_LINEAGE_MISMATCH`, y compris lorsque la décision aurait été
`NO_EXPANSION`, `STOP_MAX_ROUNDS` ou `STOP_NO_PROGRESS`. Une proposal propage
uniquement les codes déjà liés au record courant.

L'ordre de décision est fermé : absence de besoin, maximum de rounds,
no-progress par absence de nouvelle identité, search goal inchangé, validation
du nombre d'items, puis proposition. `EvidenceExpansionProposal` copie scope,
source policy, filtres et autorité depuis la première round ; seul le nouveau
search goal vient du besoin explicite. Elle ne contient ni `ContractMeta`, ni
step ID, ni permission ou capability.

La proposition est destinée à AG-01. AG-02 n'exécute aucune nouvelle round,
n'appelle aucun coordinator et ne crée aucune boucle E01→E02→E03→E01.

## Conséquences

- les instructions documentaires restent des données non autoritatives ;
- les URL ne sont jamais suivies en 12.7-E ;
- duplication et corroboration indépendante sont distinguées sans suppression ;
- versions conflictuelles et staleness restent traçables ;
- trois rounds et douze items sont des garde-fous techniques configurables ;
- no-progress arrête l'expansion malgré un budget restant ;
- aucune modification C-05/C-06, runtime, orchestration ou adapter n'est requise ;
- aucun `SecurityEvent`, EventBus, provider, retry ou wiring n'est introduit ;
- l'intégration runtime/Search/RAG reste réservée à 12.7-F ;
- le hardening global et l'observabilité restent réservés à 12.12/12.13.
