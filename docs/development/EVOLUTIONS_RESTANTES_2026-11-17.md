# Évolution locale conservée séparément

Cette branche conserve le delta de recadrage des chapitres réels relevé dans
la copie de travail depuis le 27 octobre, au-dessus de la consolidation V2.
Elle n'est pas destinée à être fusionnée dans le même lot.

Le seul delta de production ajoute REAL_CHAPTER aux contrats de chapitres
rattachés aux notions dans ReframeCourseCommand. Il conserve le contrat de
production correspondant lors d'une correction locale explicitement demandée.
Le parent, la provenance, la validation et la séparation des responsabilités
restent conservés. Aucune génération ni nouvelle autorité n'est créée.

La copie du service utilisée comme référence ne comportait pas ce delta ;
les autres évolutions fonctionnelles relevées ont été reprises dans la branche
de consolidation. Les anciennes variantes supplantées restent dans la copie
de travail d'origine. Bases et documents d'exécution ne sont pas versionnés.

Un test synthétique passe par ReframeCourseInbound et vérifie le descendant,
la conservation du parent et l'absence d'une seconde génération. Les tests de
chapitres existants restent applicables. Aucun service réel n'est rechargé.
