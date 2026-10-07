# ADR — Complément des propriétaires R2 dans le garde courant

Date : 7 octobre 2026. Statut : décision locale de stabilisation ; revue indépendante requise avant intégration.

## Constat exact

Le rejeu complet de `fbffe20fd534d79f5994193f7a652ad818f643b0` conserve les anciens tests et leurs échecs privés. Son rapprochement montre que les 381 propriétaires du garde R6 courant ne comprennent pas 40 chemins du périmètre R2 corrigé (`R2_PATHS ∪ CORRECTION_PATHS`), dont les modules OpenAI partagés `contracts.py` et `transport.py`.

Les trois assertions anciennes de mutation OpenAI contrôlent aussi 21 préparations privées. Leur FAIL dans le clone propre ne suffit donc pas à démontrer le refus courant de toutes les substitutions. Aucun compagnon absent de la collecte ne peut être annoncé PASS. Les originaux, assertions, résultats et commits historiques sont conservés.

## Décision minimale

Ajouter au manifeste authentifié courant les propriétaires R2 publics manquants et le présent ADR, aux SHA des fichiers réellement présents dans la candidate. Conserver chaque propriétaire déjà protégé, les 27 exclusions privées exactes, la baseline et l'historique des successeurs. Le garde reste fermé ; aucune exemption ni modification du scanner partagé n'est introduite.

Compléter l'ensemble `HISTORICAL_OWNERS` du test courant avec le périmètre R2 corrigé, sans préparations privées. Les mutations existantes s'appliquent alors à chacun des propriétaires ajoutés : substitution et retrait du fichier, substitution au même chemin, remplacement de l'objet dans l'index réel et retrait de l'index. Le retour à l'état initial est contrôlé. La couverture doit être vérifiée à partir des node_ids réellement collectés.

Ce complément protège les bytes courants. Il n'admet pas automatiquement un changement métier par rapport à un ancien pin et ne constitue ni une attestation privée, ni une dérogation pour les FAIL historiques. Le test historique qui exige une copie d'originaux privés dans sa fixture reste inchangé et son incompatibilité avec l'ADR R3 portable reste visible.

## Qualification et publication

Sauvegarder avant le changement, exécuter les mutations concernées, les contrôles du garde et les validations statiques applicables. Produire un commit local cohérent, préserver `c7aca1d` et `fbffe20`, puis qualifier une nouvelle candidate combinée et son package exact. La PR doit présenter cet ADR, les preuves de mutation et toutes les réserves conservées.

La relecture auteur précède l'implémentation ; elle ne vaut pas la revue indépendante exigée par CONTRIBUTING avant merge. Aucun appel fournisseur, donnée runtime dans Git, copie de préparations privées, modification de seed, changement de lock ou merge de main n'est autorisé par cet ADR.
