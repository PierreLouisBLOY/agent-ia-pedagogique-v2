# R3 — Matérialisation déterministe des locators PREPARE

Statut : décision hors ligne approuvée sur `8b341b76b32c37a2232c053190b04b89cb5f6983`.

La frontière outbound OpenAI PREPARE reçoit des anchors fermés `section_id/exact_text`
pour les questions et l'unité, sous les clés existantes `locator` et
`source_unit_locator`. Les calculs ne contiennent aucun locator fournisseur.
Les anciennes formes avec offsets sont rejetées par le schéma, jamais réparées.

Après décodage et validation du schéma, un matérialiseur local pur construit le
locator canonique `section_id/start/end/exact_text`. Il ne possède aucune autorité
de validation, publication, réseau, stockage ou credential. Les sections proviennent
exclusivement du sujet déjà résolu dans GenerationPortRequest.

Un anchor sujet/unité exige une section unique et une citation exacte unique,
y compris les occurrences chevauchantes. Aucun trim, normalisation Unicode,
casefold, fuzzy match, clamp ou reformattage n'est admis. Les indices sont ceux
des chaînes Python décodées, fin exclusive, et le slice est immédiatement vérifié.

Pour chaque réponse, les calculs sont groupés par valeur canonique exacte.
Les occurrences non chevauchantes sont affectées de gauche à droite dans l'ordre
des calculs de cette valeur. Une occurrence ne peut être réutilisée, même entre
valeurs distinctes. Une insuffisance ou un chevauchement entre affectations échoue
sans chercher une affectation alternative. Les occurrences excédentaires et tout
le texte restent intacts : A16 conserve son rôle de diagnostic sémantique.

Le mapping ne s'applique qu'à PREPARE_SUPPLEMENTS. Le DTO canonique, le bundle,
les seize prédicats CAP-A01, R2, REVIEW, HARDEN et le serializer 8192 restent
inchangés. Cinq codes fermés complètent le diagnostic privé DOMAIN_MAP, sans texte
de l'ancre, payload, chemin ou exception brute.

Les tables et empreintes historiques des guards restent immuables. Un oracle
successeur authentifie les 22 fichiers préinventoriés, les symboles autorisés,
les bytes de travail et d'index. Les comparaisons AST historiques peuvent examiner
les bytes de la baseline uniquement après authentification du successeur exact ;
cette liaison ne constitue jamais une exemption du nouvel inventaire.

La requête PREPARE et sa projection COUNT doivent être reconstruites hors ligne.
Le comptage historique n'autorise pas le nouveau payload. Aucun nouveau comptage
ni live n'est autorisé. Le résultat live antérieur reste FAILED_OUTPUT et consommé.
