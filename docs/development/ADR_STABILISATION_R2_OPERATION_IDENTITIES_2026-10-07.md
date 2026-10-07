# ADR — Identités d'opération aux dispatchs P0 et R3

## Décision et revue locale

Mandat R2, A06.2 / AA11 : transmettre les identités déjà détenues par
l'Application aux adaptateurs de revue et de transformation. Cette évolution
est limitée aux métadonnées techniques, sans nouvel agent, fournisseur ni tâche
persistante. La revue locale vérifie les contrats fermés, la séparation des
responsabilités et les gardes historiques et actives ; elle ne vaut pas une
approbation humaine de PR ou une autorisation live.

Un DTO neutre `OPERATION-IDENTITY-1.0` porte run, step, parent et corrélation.
P0 utilise la commande consommée, la conversation et le step source conservés.
R3 utilise l'opération réservée et sa conversation. L'enveloppe R3 conserve
l'identité jusqu'au dispatcher et aux ports existants. La revue matérialisée
conserve les mêmes métadonnées que sa préparation. Le bundle et sa filiation
restent liés aux mêmes production/version/empreintes.

Les appels directs historiques sans enveloppe restent compatibles. Ils
reçoivent une identité technique unique locale ; aucune corrélation métier ou
filiation absente n'est inventée. Les fixtures historiques attestent toujours
leurs commits historiques et leurs valeurs fixes d'origine.

Le DTO ne contient ni HTTP, SDK, SQL ni données pédagogiques. Il ne donne
aucune autorité et ne change pas les formats fermés des résultats. La demande
interne de revue P0 devient explicitement 1.1 lorsqu'elle porte cette identité ;
la forme 1.0 reste lisible par les appels directs de compatibilité. Les preuves
fournisseur antérieures ne qualifient pas ce nouveau dispatch.

## Contrôles requis

- Deux opérations réelles via Application/dispatcher portent des identités
  différentes jusque dans les doubles des ports et gardent leur corrélation.
- La filiation source P0 est propagée sans modification du bundle.
- Le rejeu d'une même commande ne redéclenche aucun port.
- Une identité malformed ou auto-parentée est refusée.
- Les gardes du commit historique restent inchangées ; le successeur actif
  inventorie et vérifie chaque fichier modifié par ce delta.

Aucun appel fournisseur n'est nécessaire pour ces preuves locales. La PR
technique doit relire cet ADR et les preuves avant l'intégration.
