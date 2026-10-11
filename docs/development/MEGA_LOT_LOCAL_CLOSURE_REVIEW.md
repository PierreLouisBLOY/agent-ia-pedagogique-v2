# Clôture locale post-d20857e — revue préalable des corrections

Entrée immuable : `d20857e88c1a82d3cd274fb0d1456e45782db9b2`.
Branche successeure : `codex/mega-lot-cloture`. Mandat propriétaire : clôture
hors ligne des réserves du même méga-lot. Aucun transport ni credential.

## Revue technique préalable, 4 octobre 2026

Les corrections ci-dessous restent dans les adaptateurs existants. Aucune
frontière de Phase 6/11, DTO, autorité, promotion ou garde canonique ne change.
Il ne s'agit pas d'une adoption pédagogique ni d'une autorisation fournisseur.

### M06 — complétude du résultat technique et limites de connaissance

Le mapper OpenAI assimile toute limitation déclarée à un résultat PARTIAL.
Une réponse completed qui couvre toutes les dimensions demandées, sans warning
ni uncertainty, peut pourtant porter une limitation descriptive. C10 interdit
un résultat INCOMPLETE déclaré acceptable. Le raccordement doit distinguer ces
deux notions, sans réécrire l'appréciation ni enlever la limitation.

Décision de correction ordinaire : SUCCEEDED seulement si la réponse est
completed, toutes les dimensions demandées sont couvertes, sans warning ni
uncertainty. INCOMPLETE reste PARTIAL. Couverture manquante reste PARTIAL.
Toutes les limitations et métadonnées restent identiques. Le statut qualité P0
reste RESERVE en présence de limitations ; aucune promotion n'est effectuée.
La garde C10, y compris le refus INCOMPLETE/acceptable, est inchangée.

Vérifications prévues : réponse complète avec limitation conservée ; mutations
incomplete, dimensions manquantes, warnings, uncertainties ; refus fournisseur ;
régression C10 et qualité P0 conservatrice.

### M07 — localisation de constat sur une cible P0 entièrement structurée

Le contrat canonique possède déjà `allow_whole_target_locator`. Le raccordement
P0 fournit une seule cible structurée versionnée et aucun target_content.
Activer cette option uniquement pour la matérialisation P0 conserve la
validation canonique du locator, son schéma fermé et la cible exacte.
Le défaut global demeure False ; une cible textuelle + structurée ambiguë,
un locator enrichi, hors cible ou porteur d'autorité restent refusés.

Vérifications prévues : whole_target P0 conservé, schéma modifié refusé,
json_path hors cible refusé, injection d'autorité refusée, aucune autorité
restaurée ni appel supplémentaire. Les refus historiques restent historiques.

### M01/M03 — absence d'autorité détectée comme revendication

Les diagnostics exacts restent conservés. Le garde lexical réagit notamment
aux codes NO_AUTHORITATIVE_ORACLE / NO_AUTHORITATIVE_BASIS_PROVIDED.
Modifier sa politique de négation affecterait une frontière canonique. Ce
mandat ne rouvre pas l'architecture. Aucun filtrage ou renommage des sorties
reçues, aucun faux PASS, aucun rattachement du reçu M01 à une autre version.
La proposition précise d'un éventuel successeur est soumise dans la décision
groupée finale ; le garde reste actif en attendant.

## Conservation et couverture

Les sorties, réservations, reçus, parents et exports historiques restent
immuables et hors Git. Les preuves nouvelles sont dans le dossier unique.
L'inventaire actif R6 reçoit un successeur explicite limité aux propriétaires
effectivement modifiés, avec contrôles positifs et de mutation. Les cinq FAIL
historiques restent identifiés par node_id et signature ; aucun skip/xfail.

Revue préalable réalisée par inspection des contrats C10, du mapper, de la
politique de locator et du calcul de qualité P0. Les assertions positives et
de refus ci-dessus sont les critères de réception technique du correctif.
