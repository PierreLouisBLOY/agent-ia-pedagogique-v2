# ADR — Compatibilité courante découverte par le rejeu global R2

Statut : analyse et revue technique locale préalables à l'implémentation.
La revue indépendante de PR reste requise ; aucune approbation humaine n'est
présumée. Entrée source : 5907fdb ; candidate combinée immuable : 0a7b2f8.

## Contre-exemples effectivement reproduits

Quatre FAIL sont reproduits sans fournisseur dans une extraction qualifiée :
le contrôle architectural du serveur, les deux routages de médias AG-04 et le
contrôle des champs sémantiques du serializer R3. Les résultats bruts restent
privés et immuables. Ils ne sont pas classés comme préconditions privées.

## Décisions et limites relues avant correction

1. L'API HTTP ne doit pas importer directement un contrat sous backend/modules.
   La validation fermée SEARCH-SOURCE-STATUS-1.0 passe par le bridge inbound
   Application existant. Le DTO, ses six champs, les refus de substitution et
   le scanner architectural ne changent pas. L'API projette la copie validée.
2. L'ADR OPERATION-IDENTITY-1.0 conserve les appels techniques historiques sans
   enveloppe. Le review adapter reconnaît donc explicitement la forme exacte
   historique à cinq champs (production, bundle_sha256, plan, evidence_pack,
   validation), ainsi que les enveloppes fermées 1.0 à six et 1.1 à sept champs.
   Aucune clé supplémentaire, version inconnue ou identité incomplète n'est
   admise. La forme historique reçoit une identité technique locale unique ;
   elle n'acquiert pas de corrélation métier ni d'autorité. Les tests de médias
   existants restent inchangés. Les schémas de résultat et uncertainties restent
   inchangés ; le service Application continue d'émettre l'enveloppe 1.1.
3. Le test de variation du seul plafond sérialise deux plafonds d'une même
   requête technique. Construire deux requêtes indépendantes crée désormais
   deux identités d'opération différentes, conformément à AA11. Réutiliser la
   requête puis remplacer uniquement max_output_tokens conserve l'assertion
   exacte et ses contrôles COUNT/hash, sans figer les identités de production.

## Preuves requises et succession des gardes

- Les quatre contre-exemples deviennent PASS ; les assertions de médias,
  d'autorité, de plafond et de COUNT ne sont pas modifiées.
- Les trois formes de revue et les mutations de champs/version/identité sont
  testées avant les doubles de ports, avec refus des formes inconnues.
- Le statut natif traverse le HTTP ; les quatre substitutions existantes et
  le contrôle architectural actuel sont rejoués.
- Tous les propriétaires modifiés/ajoutés sont liés à un successeur exact du
  manifeste R6, avec contrôles positifs et mutations actuelles. Les anciennes
  empreintes, tests et preuves restent dans Git. Aucune exclusion globale.
- Ruff, mypy, compilation et qualification du successeur empaqueté sont requis.

Aucun nouveau fournisseur, COUNT, credential, donnée originale, migration,
framework, media généré ou décision pédagogique. La candidate 0a7b2f8 reste
immuable pendant son rejeu ; les corrections restent dans cette continuation R2.
